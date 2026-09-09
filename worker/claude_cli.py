"""Claude CLI 호출 계층 — 인증 격리·사용량 집계·점검.

`claude -p` 는 단순 모델 호출이 아니라 Claude Code 에이전트를 띄운다. 실측상 프롬프트가
10토큰이어도 시스템 프롬프트·툴 정의로 호출당 약 3만 토큰이 붙는다(대부분 캐시 읽기).
그래서 비용은 '프롬프트 길이'가 아니라 '호출 횟수'가 정한다 — 호출부는 최대한 묶어서 부른다.

요약 로직과 섞여 있으면 '왜 이렇게 비싼가'를 따라가기 어려워 여기로 분리했다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading

CLI_TIMEOUT = 180
# 단순 요약이 아니다 — 시간에 따라 뒤집히는 메모를 정리하고 지속 선호와 일회성을 갈라야 한다.
# 판단이 필요한 일이라 작은 모델은 쓰지 않는다.
MODEL = os.environ.get("MODEL", "sonnet")

# claude CLI 는 ANTHROPIC_API_KEY 가 있으면 그걸 우선 쓰고 claude.ai 로그인(구독)을 무시한다.
# 이 리포는 voicenote 용으로 키를 둘 수 있고, _load_env() 가 web/.env.local 을 통째로 환경에
# 올리기까지 해서, 크레딧 없는 키가 잡히면 "Credit balance is too low" 로 전부 실패한다.
# 요약은 구독 로그인으로 도는 게 맞으므로 자식 프로세스에서만 인증 변수를 걷어낸다.
# 정말 API 키로 청구하고 싶으면 USE_API_KEY=1.
_AUTH_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
              "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX")


def cli_env() -> dict:
    env = dict(os.environ)
    if os.environ.get("USE_API_KEY"):
        return env
    for k in _AUTH_VARS:
        env.pop(k, None)
    return env


def stripped_vars() -> list[str]:
    return [] if os.environ.get("USE_API_KEY") else [k for k in _AUTH_VARS if os.environ.get(k)]


USAGE = {"calls": 0, "in": 0, "cache_read": 0, "cache_write": 0, "out": 0}
_usage_lock = threading.Lock()   # 여러 배치를 동시에 돌리므로 집계는 잠그고 더한다


def run_claude(prompt: str) -> tuple[str | None, str]:
    """Claude CLI 호출. (출력, 실패사유).

    --output-format json 으로 받아 본문과 함께 토큰 사용량도 집계한다.
    호출당 고정비가 큰 구조라, 얼마나 쓰고 있는지 눈으로 봐야 판단이 선다.
    """
    base = ["claude", "-p", prompt, "--output-format", "json"]
    attempts = [base + (["--model", MODEL] if MODEL else [])]
    if MODEL:
        attempts.append(base)

    why = "알 수 없음"
    for cmd in attempts:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=CLI_TIMEOUT, env=cli_env())
        except FileNotFoundError:
            print("❌ claude CLI 가 없습니다. 설치 후 로그인하세요: https://claude.com/claude-code",
                  file=sys.stderr)
            raise SystemExit(1)
        except subprocess.TimeoutExpired:
            why = f"타임아웃 {CLI_TIMEOUT}s"
            continue

        raw = (r.stdout or "").strip()
        if raw:
            try:
                d = json.loads(raw)
                u = d.get("usage") or {}
                with _usage_lock:
                    USAGE["calls"] += 1
                    USAGE["in"] += u.get("input_tokens") or 0
                    USAGE["cache_read"] += u.get("cache_read_input_tokens") or 0
                    USAGE["cache_write"] += u.get("cache_creation_input_tokens") or 0
                    USAGE["out"] += u.get("output_tokens") or 0
                text = (d.get("result") or "").strip()
                if text:
                    return text, ""
                why = f"빈 결과 (subtype={d.get('subtype')})"
                continue
            except json.JSONDecodeError:
                return raw, ""      # json 이 아니면 본문으로 취급
        err = (r.stderr or "").strip()
        why = (err.splitlines()[0][:160] if err else f"빈 응답 (exit={r.returncode})")
    return None, why


def print_usage() -> None:
    u = USAGE
    if not u["calls"]:
        return
    billed = u["in"] + u["cache_write"] + u["cache_read"]
    print(f"\n토큰 사용 · 호출 {u['calls']}회 · 입력 {u['in']:,} + 캐시읽기 {u['cache_read']:,}"
          f" + 캐시쓰기 {u['cache_write']:,} · 출력 {u['out']:,}")
    print(f"  호출당 평균 {billed // u['calls']:,} 토큰"
          f" (대부분 Claude Code 기본 장착분 — 묶을수록 1인당 비용이 준다)")


def check_cli() -> int:
    """CHECK=1 — 한 번만 불러보고 무슨 일이 일어나는지 그대로 보여준다."""
    print(f"claude CLI 점검 · 모델 {MODEL or '기본'}")
    dropped = stripped_vars()
    if dropped:
        print(f"인증 변수 제외(구독 로그인 사용): {', '.join(dropped)}")
    cmd = ["claude", "-p", "한 단어로 답해: 안녕"] + (["--model", MODEL] if MODEL else [])
    print("실행:", " ".join(cmd[:3]), "…")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=CLI_TIMEOUT, env=cli_env())
    except FileNotFoundError:
        print("❌ claude 명령을 찾을 수 없음 — 설치/PATH 확인")
        return 1
    print(f"exit={r.returncode}")
    print("--- stdout ---\n" + (r.stdout or "(비어 있음)"))
    print("--- stderr ---\n" + (r.stderr or "(비어 있음)"))
    return 0 if (r.stdout or "").strip() else 1


