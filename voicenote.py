#!/usr/bin/env python3
"""음성 메모 파이프라인 — 녹음 파일 → (Whisper) 텍스트 → (Claude) 요약 → 카르테 자동 반영.

흐름(사람 손 최소):
  1) 폰에서 녹음(시작할 때 고객 이름 한마디) → 클라우드 폴더 자동 동기화
  2) 이 스크립트를 Mac 에서 watch 로 켜두면, 새 오디오를 감지해:
     transcribe(무료 로컬 Whisper) → summarize(Claude) → 고객 매칭 → 메모 기입 → 앱 데이터 재빌드
  3) 처리한 파일은 _done/ 으로 이동

핵심: Claude 는 STT 를 못 한다 → 변환은 Whisper, 요약·구조화만 Claude.
변환/요약 백엔드는 환경에 맞게 교체 가능(없으면 명확히 안내). 매칭·기입은 결정적.

사용법:
  python voicenote.py process <audio> --client clients/{slug}
  python voicenote.py watch <folder>  --client clients/{slug}
  python voicenote.py apply  <transcript.txt> --client clients/{slug}   # 변환된 텍스트만 있을 때
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

AUDIO_EXT = {".m4a", ".mp3", ".wav", ".aac", ".mp4", ".webm", ".caf", ".ogg"}


# ── ③ STT: 로컬 Whisper (무료). 없으면 안내. ─────────────────────────
_MODEL = None


def load_model(size: str = "base"):
    """Whisper 모델을 한 번만 로드해 캐시(watch 모드에서 매 파일 재로딩 방지)."""
    global _MODEL
    if _MODEL is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "로컬 STT 미설치 — Mac 에서:  pip install faster-whisper\n"
                "  (무료·무제한. Claude 는 음성 변환을 못 하므로 변환은 Whisper 가 담당)"
            ) from e
        import os
        _MODEL = WhisperModel(os.getenv("WHISPER_MODEL", size), compute_type="int8")
    return _MODEL


def transcribe(audio_path: str, model=None) -> str:
    model = model or load_model()
    segments, _ = model.transcribe(audio_path, language="ko")
    return " ".join(s.text.strip() for s in segments).strip()


# ── ④ 요약·구조화: Claude (Anthropic). 없으면 프롬프트만 내보내 수동 처리. ──
SUMMARY_SCHEMA_HINT = (
    '{"customer_name": "고객 성함(말한 이름)", '
    '"summary": "1~3문장 카르테 메모(존댓말, 핵심만)", '
    '"tags": ["취향/주의 태그", "..."], '
    '"service": "언급된 시술(없으면 빈문자열)", '
    '"next_action": "다음 방문 때 챙길 것(없으면 빈문자열)", '
    '"care_cycle_days": null}'
)


def summarize_prompt(transcript: str) -> str:
    return (
        "다음은 미용 디자이너가 고객 상담/시술 직후 남긴 음성 메모를 받아쓴 것이다. "
        "사실만 사용해 카르테용으로 정리하라(없는 내용 지어내기 금지). "
        "아래 JSON 스키마로만 출력하라(설명·코드펜스 없이 JSON 본문만):\n"
        f"{SUMMARY_SCHEMA_HINT}\n\n[받아쓴 메모]\n{transcript}"
    )


def summarize(transcript: str) -> dict:
    import os

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "Claude 요약 키 없음(ANTHROPIC_API_KEY). 자동 요약을 쓰려면 키를 설정하거나,\n"
            "  python voicenote.py prompt <transcript> 로 프롬프트를 받아 Claude 에 직접 붙여넣어 처리하세요."
        )
    import anthropic

    client = anthropic.Anthropic(api_key=key)
    model = os.getenv("CLAUDE_MODEL", "claude-3-5-haiku-latest")
    msg = client.messages.create(
        model=model, max_tokens=600,
        messages=[{"role": "user", "content": summarize_prompt(transcript)}],
    )
    return parse_summary(msg.content[0].text)


def parse_summary(text: str) -> dict:
    """모델 응답에서 JSON 본문만 추출해 파싱(코드펜스 허용)."""
    t = (text or "").strip()
    if "```" in t:
        m = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
        if m:
            t = m.group(1).strip()
    if not t.startswith("{"):
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if m:
            t = m.group(0)
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError("요약 결과가 JSON 객체가 아닙니다")
    return data


# ── ⑤ 앱 반영: 고객 매칭 + 메모/태그 기입 ───────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "")).replace("님", "")


def match_customer(name: str, customers: list[dict]) -> dict | None:
    """말한 이름 → 고객. 정확 일치 → 포함 일치 순."""
    n = _norm(name)
    if not n:
        return None
    for c in customers:
        if _norm(c.get("name")) == n:
            return c
    for c in customers:
        cn = _norm(c.get("name"))
        if cn and (cn in n or n in cn):
            return c
    return None


# ── 시간 기반 매칭: 녹음 시각 ↔ 네이버 예약 시간 ──────────────────────
def recording_dt(path: str):
    """녹음 파일의 시각(생성시간 우선, 없으면 수정시간)."""
    import os
    from datetime import datetime as _dt

    st = os.stat(path)
    ts = getattr(st, "st_birthtime", None) or st.st_mtime
    return _dt.fromtimestamp(ts)


def load_bookings(client_dir: str) -> list[dict]:
    p = Path(client_dir) / "bookings.yaml"
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _hm(t):
    m = re.search(r"(\d{1,2}):(\d{2})", str(t or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def match_by_time(rec_dt, bookings: list[dict], before_h: float = 0.5, after_h: float = 5):
    """녹음 시각 기준, 같은 날 예약 중 '직전에 시작한' 시술을 고른다(끝나고 녹음하는 패턴)."""
    day = rec_dt.strftime("%Y-%m-%d")
    cands = []
    for b in bookings:
        if str(b.get("date")) != day:
            continue
        hm = _hm(b.get("time"))
        if not hm:
            continue
        bt = rec_dt.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        diff = (rec_dt - bt).total_seconds() / 3600.0   # >0 = 시작 이후
        cands.append((diff, b))
    after = sorted([c for c in cands if 0 <= c[0] <= after_h], key=lambda c: c[0])
    if after:
        return after[0][1]                              # 시작 직후(가장 가까운) = 가장 최근 시술
    near = sorted([c for c in cands if -before_h <= c[0] < 0], key=lambda c: -c[0])
    return near[0][1] if near else None


def resolve_customer(summary: dict, customers: list[dict],
                     bookings: list[dict] | None = None, rec_dt=None):
    """이름(말함) + 시간(녹음↔예약) 교차로 고객 결정. (customer, method, note)."""
    by_name = match_customer(summary.get("customer_name", ""), customers)
    by_time = None
    if rec_dt is not None and bookings:
        b = match_by_time(rec_dt, bookings)
        if b:
            by_time = match_customer(b.get("name", ""), customers)
    if by_name and by_time:
        if by_name is by_time:
            return by_name, "name+time", ""
        return by_name, "name(시간 후보와 불일치)", f"시간기준: {by_time.get('name')}님"
    if by_name:
        return by_name, "name", ""
    if by_time:
        return by_time, "time", "이름 미언급 — 예약시간으로 추정"
    return None, "none", ""


def _load(p: Path) -> dict:
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def apply_summary(client_dir: str, summary: dict, today: str | None = None,
                  rec_dt=None) -> dict:
    """요약을 매칭 고객 yaml 에 반영(메모 누적 + 태그 병합). 결과 상태 반환.
    rec_dt(녹음 시각) 주면 네이버 예약시간(bookings.yaml)과 대조해 이름 없이도 매칭."""
    today = today or str(date.today())
    cdir = Path(client_dir) / "customers"
    paths = sorted(cdir.glob("*.yaml"))
    customers = [(p, _load(p)) for p in paths]

    target, method, note = resolve_customer(
        summary, [c for _, c in customers], load_bookings(client_dir), rec_dt)
    if target is None:
        return {"matched": False, "name": summary.get("customer_name", ""),
                "reason": "이름·예약시간 어느 것으로도 못 찾음 — 확인 필요"}

    path = next(p for p, c in customers if c is target)
    memo_line = f"[{today}] {summary.get('summary', '').strip()}"
    if summary.get("next_action"):
        memo_line += f" (다음: {summary['next_action'].strip()})"
    prev = (target.get("memo") or "").strip()
    target["memo"] = (prev + "\n" + memo_line).strip() if prev else memo_line

    # 태그 병합(중복 제거, 순서 보존)
    tags = [t.strip() for t in (summary.get("tags") or []) if t and t.strip()]
    pref = list(target.get("prefer") or [])
    for t in tags:
        if t not in pref:
            pref.append(t)
    if pref:
        target["prefer"] = pref
    if summary.get("care_cycle_days"):
        target["care_cycle_days"] = int(summary["care_cycle_days"])

    path.write_text(yaml.safe_dump(target, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"matched": True, "id": target.get("id"), "name": target.get("name"),
            "path": str(path), "method": method, "note": note}


def rebuild_app(client_dir: str) -> None:
    try:
        import build_app
        build_app.build_one(client_dir)
    except Exception as exc:
        print(f"  (앱 데이터 재빌드 건너뜀: {exc})")


def process(audio: str, client_dir: str, model=None) -> dict:
    print(f"· 변환(Whisper): {audio}")
    transcript = transcribe(audio, model=model)
    print(f"  받아쓰기: {transcript[:60]}…")
    summary = summarize(transcript)
    res = apply_summary(client_dir, summary, rec_dt=recording_dt(audio))
    if res["matched"]:
        rebuild_app(client_dir)
        tag = f"[{res.get('method')}]" + (f" {res['note']}" if res.get("note") else "")
        print(f"✓ {res['name']}님 카르테에 반영 → 앱 갱신  {tag}")
    else:
        print(f"✗ {res['reason']} (이름: {res['name']})")
    return res


def watch(folder: str, client_dir: str) -> int:
    import time

    src = Path(folder)
    done = src / "_done"
    done.mkdir(exist_ok=True)
    model = load_model()             # 한 번만 로드 → 이후 각 파일은 추론만(빠름)
    print(f"감시 시작: {src}  (새 오디오 → 자동 처리)  Ctrl+C 종료")
    seen: set[str] = set()
    while True:
        for f in sorted(src.iterdir()):
            if f.suffix.lower() in AUDIO_EXT and f.name not in seen:
                seen.add(f.name)
                try:
                    process(str(f), client_dir, model=model)
                    f.rename(done / f.name)
                except Exception as exc:
                    print(f"  처리 실패({f.name}): {exc}")
        time.sleep(5)


def batch(folder: str, client_dir: str) -> int:
    """폴더의 모든 오디오를 한 번에 처리(저녁 배치용). 처리분은 _done/ 으로."""
    src = Path(folder)
    done = src / "_done"
    done.mkdir(exist_ok=True)
    files = [f for f in sorted(src.iterdir()) if f.suffix.lower() in AUDIO_EXT]
    if not files:
        print("처리할 오디오가 없습니다.")
        return 0
    model = load_model()
    ok = miss = 0
    for f in files:
        try:
            res = process(str(f), client_dir, model=model)
            f.rename(done / f.name)
            ok += 1 if res.get("matched") else 0
            miss += 0 if res.get("matched") else 1
        except Exception as exc:
            print(f"  처리 실패({f.name}): {exc}")
            miss += 1
    print(f"\n배치 완료: 반영 {ok} · 미매칭/실패 {miss} (총 {len(files)})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="음성 메모 → 카르테 자동 반영")
    ap.add_argument("cmd", choices=["process", "batch", "watch", "apply", "prompt"])
    ap.add_argument("target", help="오디오/폴더/텍스트 경로")
    ap.add_argument("--client", help="clients/{slug}")
    args = ap.parse_args()

    if args.cmd == "prompt":
        text = Path(args.target).read_text(encoding="utf-8")
        print(summarize_prompt(text))
        return 0
    if not args.client:
        print("--client clients/{slug} 가 필요합니다")
        return 2
    if args.cmd == "process":
        process(args.target, args.client)
    elif args.cmd == "batch":
        batch(args.target, args.client)
    elif args.cmd == "watch":
        watch(args.target, args.client)
    elif args.cmd == "apply":   # 이미 텍스트로 변환된 경우(예: Voice Memos 자동 텍스트)
        transcript = Path(args.target).read_text(encoding="utf-8")
        res = apply_summary(args.client, summarize(transcript))
        print(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
