"""매장 메모 AI 정리 — 고객별 메모를 한 번에 읽어 몇 줄로 요약하고 DB 에 박아둔다.

왜 배치인가:
    HandSOS 매장 메모는 방문마다 한 줄씩 쌓여 중구난방이다("컬 약하게", "두피 예민", ...).
    화면을 열 때마다 AI 를 부르면 느리고 비싸므로, 맥에서 수집 직후 한 번 정리해 저장한다.
    앱은 customers.memo_ai 를 읽기만 한다.

개인정보:
    고객 이름·연락처는 테넌트 키로 암호화돼 있고, 이 스크립트는 **복호화하지 않는다**.
    AI 에 넘기는 것은 날짜와 메모 문장뿐이다(누구인지 모르는 상태로 요약).

재실행:
    메모 원본의 해시를 memo_ai_src 에 함께 저장해, 메모가 그대로면 건너뛴다.
    주 1회 배치에서 대부분은 호출 없이 지나간다. 전부 다시 만들려면 FORCE=1.

사용량:
    고객 1명당 호출 1번이면 1,300명에 1,300번이라 구독 사용량이 순식간에 녹는다.
    BATCH 명씩 한 프롬프트에 묶어 호출 수를 그만큼 줄인다(기본 6 → 약 1/6).

속도:
    claude CLI 한 번이 기동+응답에 십수 초~1분이라 순차로 돌리면 몇십 명만 돼도 하염없다.
    모델은 판단 품질 때문에 낮추지 않고, 대신 여러 명을 동시에 돌려 벽시계 시간을 줄인다.
    JOBS 를 올리면 그만큼 빨라진다(맥 사양·요금제에 맞춰 4~8 권장).

사용:
    .venv/bin/python worker/summarize_memos.py            # 바뀐 고객만
    FORCE=1 .venv/bin/python worker/summarize_memos.py    # 전부 다시
    LIMIT=5 .venv/bin/python worker/summarize_memos.py    # 5명만(시험)
    CHECK=1 .venv/bin/python worker/summarize_memos.py    # CLI 가 되는지만 점검
    USE_API_KEY=1 .venv/bin/python ...                    # 구독 대신 ANTHROPIC_API_KEY 로 청구
    JOBS=8 .venv/bin/python worker/summarize_memos.py     # 동시 실행 수(기본 4)
    BATCH=20 .venv/bin/python worker/summarize_memos.py   # 1회 호출에 묶을 고객 수(기본 12)
    ACTIVE_MONTHS=12 .venv/bin/python ...                 # 최근 12개월 방문 고객만(기본: 전체)
    MODEL=opus .venv/bin/python ...                       # 모델 변경(기본 sonnet), MODEL= 로 지정 해제
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    p = ROOT / "web" / ".env.local"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    if not os.environ.get("SUPABASE_URL") and os.environ.get("NEXT_PUBLIC_SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = os.environ["NEXT_PUBLIC_SUPABASE_URL"]


_load_env()

import supa  # noqa: E402

MAX_MEMOS = 40          # 한 고객당 최근 메모 상한(프롬프트 길이 방어)
CLI_TIMEOUT = 180
# 단순 요약이 아니다 — "지난번엔 밝게, 최근엔 어둡게"처럼 시간에 따라 뒤집히는 걸 정리하고,
# 지속되는 선호와 한 번뿐인 잡담을 갈라내야 한다. 판단이 필요한 일이라 작은 모델은 쓰지 않는다.
MODEL = os.environ.get("MODEL", "sonnet")
# 프롬프트가 바뀌면 기존 요약은 형식이 달라 못 쓴다. 해시에 섞어 자동으로 다시 만들게 한다.
PROMPT_VERSION = "2-sections"
# claude -p 는 단순 모델 호출이 아니라 Claude Code 에이전트를 띄운다. 실측 결과 프롬프트가
# 10토큰이어도 시스템 프롬프트·툴 정의로 호출당 약 3만 토큰이 붙는다(대부분 캐시 읽기).
# 즉 비용은 '메모 길이'가 아니라 '호출 횟수'가 정한다 — 1,300명을 1명씩 부르면 4천만 토큰,
# 20명씩 묶으면 200만 토큰. 그래서 최대한 크게 묶는다.
#
# 참고: --system-prompt 로 껍데기를 줄이려 하면 오히려 손해다. 기본 시스템 프롬프트는
# 호출 간 캐시로 재사용(1/10 가격)되는데, 직접 지정하면 캐시가 깨져 매번 새로 쓴다.
BATCH = max(1, int(os.environ.get("BATCH") or 12))
# 2년 전 한 번 오고 안 오는 고객까지 정리해봐야 그 카르테는 열릴 일이 없다.
# 최근 N개월 안에 다녀간 고객만 대상으로 잡아 일 자체를 줄인다(0 이면 전체).
ACTIVE_MONTHS = int(os.environ.get("ACTIVE_MONTHS") or 0)


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
_usage_lock = __import__("threading").Lock()


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


def summarize_one(job: dict) -> tuple[str, str | None, str | None, str]:
    """한 고객 요약 — 스레드에서 실행. (customer_id, 선호, 근황, 실패사유)"""
    out, why = run_claude(build_prompt(job["memos"]))
    if not out:
        return job["cid"], None, None, why
    pref, recent = parse_sections(out)
    return job["cid"], pref, recent, ("" if pref else "형식에 맞지 않는 응답")


def build_batch_prompt(blocks: list[list[str]]) -> str:
    """여러 고객의 메모를 한 프롬프트로. blocks[i] = 그 고객의 '날짜 메모' 줄들."""
    body = "\n\n".join(
        f"--- 고객 {i + 1} ---\n" + "\n".join(lines) for i, lines in enumerate(blocks)
    )
    return (
        f"너는 미용실 디자이너를 돕는 조수다. 아래에 고객 {len(blocks)}명의 매장 메모가 있다"
        "(고객마다 날짜 오름차순). 각 고객을 두 덩이로 정리해라.\n\n"
        "[선호] — 시술에 계속 반영할 것\n"
        "- 반복되는 선호·주의사항, 모발·두피 상태.\n"
        "- 시간에 따라 뒤집히면 날짜를 보고 최근 것을 따르되 '최근에는 ~' 으로 적어라.\n"
        "- 2~4개. 각 줄 25자 내외.\n\n"
        "[근황] — 다음에 만나면 먼저 물어볼 이야기\n"
        "- 개인 근황·대화거리(가족, 일, 이사, 여행, 행사, 건강 등). 시술과 무관해도 좋다.\n"
        "- 한 번만 나온 이야기라도 담아라. 이게 이 항목의 목적이다.\n"
        "- 최근 것 위주로 최대 3개. 각 줄 앞에 (YYYY-MM) 을 붙여라.\n"
        "- 오래돼 지금 꺼내기 어색한 이야기는 빼라. 해당 없으면 아무 줄도 쓰지 마라.\n\n"
        "공통: 메모에 실제로 있는 내용만. 없는 사실을 지어내지 마라.\n"
        "고객 번호를 절대 섞지 마라 — 각자 자기 메모만 보고 정리한다.\n"
        "인사말·설명 없이 아래 형식 그대로, 고객 수만큼 반복해서 출력:\n"
        "### 1\n[선호]\n- ...\n[근황]\n- (2026-07) ...\n### 2\n[선호]\n- ...\n\n"
        f"{body}\n"
    )


def parse_batch(text: str, n: int) -> dict[int, tuple[str | None, str | None]]:
    """'### i' 로 나뉜 응답을 고객 번호별로 파싱. 일부가 깨져도 나머지는 살린다."""
    out: dict[int, tuple[str | None, str | None]] = {}
    cur: int | None = None
    buf: list[str] = []

    def flush() -> None:
        if cur is not None and 1 <= cur <= n:
            out[cur] = parse_sections("\n".join(buf))

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("###"):
            flush()
            digits = "".join(ch for ch in line if ch.isdigit())
            cur, buf = (int(digits) if digits else None), []
            continue
        buf.append(raw)
    flush()
    return out


def summarize_batch(jobs: list[dict]) -> list[tuple[str, str | None, str | None, str]]:
    """한 번의 호출로 여러 고객 처리. 반환은 고객별 (cid, 선호, 근황, 실패사유)."""
    out, why = run_claude(build_batch_prompt([j["memos"] for j in jobs]))
    if not out:
        return [(j["cid"], None, None, why) for j in jobs]
    parsed = parse_batch(out, len(jobs))
    res = []
    for i, j in enumerate(jobs, start=1):
        pref, recent = parsed.get(i, (None, None))
        res.append((j["cid"], pref, recent, "" if pref else "응답에서 이 고객 항목을 못 찾음"))
    return res


def build_prompt(lines: list[str]) -> str:
    """lines: '2026-06-01 컬 약하게' 처럼 날짜가 붙은 메모들(오래된 순).
    날짜가 있어야 '최근에는 ~' 판단과 근황의 시점 표기가 가능하다."""
    joined = "\n".join(lines)
    return (
        "너는 미용실 디자이너를 돕는 조수다. 아래는 한 고객에 대해 매장에서 방문마다 적어둔 메모다(날짜 오름차순).\n"
        "디자이너가 이 고객을 다시 맞을 때 3초 안에 파악하도록 두 덩이로 정리해라.\n\n"
        "[선호] — 시술에 계속 반영할 것\n"
        "- 반복되는 선호·주의사항, 모발·두피 상태.\n"
        "- 시간에 따라 뒤집히면 날짜를 보고 최근 것을 따르되 '최근에는 ~' 으로 적어라.\n"
        "- 2~4개. 각 줄 25자 내외.\n\n"
        "[근황] — 다음에 만나면 먼저 물어볼 이야기\n"
        "- 개인 근황·대화거리(가족, 일, 이사, 여행, 행사, 건강 등). 시술과 무관해도 좋다.\n"
        "- 한 번만 나온 이야기라도 담아라. 이게 이 항목의 목적이다.\n"
        "- 최근 것 위주로 최대 3개. 각 줄 앞에 (YYYY-MM) 을 붙여라.\n"
        "- 오래돼 지금 꺼내기 어색한 이야기는 빼라. 해당 없으면 아무 줄도 쓰지 마라.\n\n"
        "공통: 메모에 실제로 있는 내용만. 없는 사실을 지어내지 마라.\n"
        "인사말·설명 없이 아래 형식 그대로만 출력:\n"
        "[선호]\n- ...\n[근황]\n- (2026-07) ...\n\n"
        f"메모:\n{joined}\n"
    )


def parse_sections(text: str) -> tuple[str | None, str | None]:
    """모델 출력에서 [선호]/[근황] 두 덩이를 뽑는다. 서두·코드펜스는 버린다."""
    pref: list[str] = []
    recent: list[str] = []
    cur: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip().strip("`").strip()
        if not line:
            continue
        if line.startswith("[선호]"):
            cur = pref
            continue
        if line.startswith("[근황]"):
            cur = recent
            continue
        if line.startswith(("- ", "• ", "* ")) and cur is not None:
            cur.append("- " + line[2:].strip())
    return ("\n".join(pref[:4]) or None, "\n".join(recent[:3]) or None)


def preflight_columns() -> None:
    """쓸 컬럼이 실제로 있는지 먼저 확인한다.

    없으면 AI 를 다 부른 뒤 저장 단계에서 400 이 나 그때까지의 호출이 통째로 버려진다
    (1,300명 배치에서는 한 시간을 날린다). 그래서 호출 전에 한 번 찔러보고 멈춘다.
    """
    need = "id,memo_ai,memo_ai_recent,memo_ai_at,memo_ai_src"
    try:
        supa._get("/customers", {"select": need, "limit": "1"})
    except RuntimeError as exc:
        msg = str(exc)
        if "memo_ai" not in msg and "PGRST204" not in msg:
            raise
        print("❌ customers 에 필요한 컬럼이 없습니다(마이그레이션 미적용).", file=sys.stderr)
        print("   Supabase SQL Editor 에서 아래를 실행한 뒤 다시 돌리세요:\n", file=sys.stderr)
        print("   alter table customers add column if not exists memo_ai        text;", file=sys.stderr)
        print("   alter table customers add column if not exists memo_ai_at     timestamptz;", file=sys.stderr)
        print("   alter table customers add column if not exists memo_ai_src    text;", file=sys.stderr)
        print("   alter table customers add column if not exists memo_ai_recent text;", file=sys.stderr)
        print("\n   이미 실행했는데도 이 메시지가 나오면 스키마 캐시가 덜 갱신된 것:", file=sys.stderr)
        print("   notify pgrst, 'reload schema';", file=sys.stderr)
        raise SystemExit(1)


def main() -> int:
    if os.environ.get("CHECK"):
        return check_cli()

    preflight_columns()          # 컬럼부터 확인 — AI 호출을 낭비하지 않게
    cutoff = ""
    if ACTIVE_MONTHS:
        cutoff = str(date.today() - timedelta(days=30 * ACTIVE_MONTHS))
        print(f"최근 {ACTIVE_MONTHS}개월({cutoff} 이후) 방문 고객만 대상")
    force = bool(os.environ.get("FORCE"))
    limit = int(os.environ.get("LIMIT") or 0)
    jobs_n = max(1, int(os.environ.get("JOBS") or 4))
    t0 = time.time()

    # ── 1) 대상 선별 (AI 호출 전) ─────────────────────────────
    print("대상 고르는 중…", flush=True)
    tenants = supa._get("/tenants", {"select": "id,slug", "order": "slug"})
    todo: list[dict] = []

    for t in tenants:
        tid, slug = t["id"], t.get("slug") or t["id"][:8]

        # 메모가 달린 거래만. 이름은 읽지 않는다(복호화 안 함).
        txs = supa.select_all("transactions", tid, "customer_id,date,memo")
        by_cust: dict[str, list[tuple[str, str]]] = {}
        for r in txs:
            memo = (r.get("memo") or "").strip()
            if not r.get("customer_id") or not memo:
                continue
            by_cust.setdefault(r["customer_id"], []).append((r.get("date") or "", memo))

        if not by_cust:
            print(f"  [{slug}] 메모 있는 고객 없음")
            continue

        existing = {c["id"]: c.get("memo_ai_src") for c in supa.select_all("customers", tid, "id,memo_ai_src")}

        picked = skipped = 0
        for cid, rows in by_cust.items():
            rows.sort(key=lambda x: x[0])                 # 오래된 순
            rows = rows[-MAX_MEMOS:]
            # 메모가 한 줄뿐이면 요약할 게 없다 — AI 를 부르지 않는다.
            if len(rows) < 2:
                skipped += 1
                continue
            if cutoff and rows[-1][0] < cutoff:   # 오래 안 온 고객은 건너뛴다
                skipped += 1
                continue
            src = hashlib.sha256(
                (PROMPT_VERSION + "\n" + "\n".join(f"{d} {m}" for d, m in rows)).encode("utf-8")
            ).hexdigest()
            if not force and existing.get(cid) == src:
                skipped += 1
                continue
            todo.append({"cid": cid, "src": src, "slug": slug,
                         "last": rows[-1][0],                     # 최근 메모 날짜 — 처리 순서용
                         "memos": [f"{d} {m}" for d, m in rows]})  # 날짜 포함 — 모순 해소용
            picked += 1
        print(f"  [{slug}] 대상 {picked}명 · 변경 없어 건너뜀 {skipped}명")

    if not todo:
        print("정리할 고객 없음 — 이미 최신입니다")
        return 0

    # 최근에 다녀간 고객부터. 중간에 멈춰도 지금 만날 사람들이 먼저 끝나 있게.
    todo.sort(key=lambda j: j["last"], reverse=True)
    if limit:
        todo = todo[:limit]
    total = len(todo)
    batches = [todo[i:i + BATCH] for i in range(0, total, BATCH)]
    print(f"\n{total}명 정리 시작 · {len(batches)}회 호출(1회당 {BATCH}명) · 동시 {jobs_n} · 모델 {MODEL or '기본'}",
          flush=True)

    done = failed = 0
    by_id = {j["cid"]: j for j in todo}
    with ThreadPoolExecutor(max_workers=jobs_n) as pool:
        futs = [pool.submit(summarize_batch, b) for b in batches]
        for fut in as_completed(futs):
            for cid, summary, recent, why in fut.result():
                if not summary:
                    failed += 1
                    print(f"  [{done + failed}/{total}] {cid[:8]} 실패 — {why}", flush=True)
                    continue
                supa.patch("customers", {"id": f"eq.{cid}"}, {
                    "memo_ai": summary,
                    "memo_ai_recent": recent,      # 없으면 null 로 덮어 옛 근황이 남지 않게
                    "memo_ai_at": datetime.now(timezone.utc).isoformat(),
                    "memo_ai_src": by_id[cid]["src"],
                })
                done += 1
                first = summary.splitlines()[0][:30]
                print(f"  [{done + failed}/{total}] {cid[:8]} ✓{' +근황' if recent else ''} {first}", flush=True)

    print_usage()
    took = int(time.time() - t0)
    print(f"\n완료: {done}명 갱신" + (f" · 실패 {failed}명" if failed else "") + f" · {took//60}분 {took%60}초")
    if limit and total == limit:
        print("LIMIT 로 잘린 상태 — 전체는 LIMIT 없이 다시 실행하세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
