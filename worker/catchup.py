"""맥을 켤 때 밀린 수집 — 로그인할 때 한 번 본다(2026-10-21, 10.18 일요일에 맥이 꺼져 있어 수집을 건너뜀).

launchd 는 예약 시각(일 14:00)에 맥이 잠자기였다면 깨어난 뒤 밀린 수집을 돌리지만, 전원이 꺼져 있었으면 다시 켜도
돌리지 않는다. 그 주는 통째로 빠지고 매일 감시가 8일째에야 알린다. 그래서 로그인할 때(launchd RunAtLoad —
scripts/mac/com.mirrorball.catchup.plist) 이것이 마지막 수집 성공을 보고, 밀렸으면 평소 수집(run_mac.sh — 백업까지)을
한 번 돌린다.

    · 마지막 성공이 7일 넘었을 때만 돈다 — 밀린 주만이라 '주 1회'는 그대로(LAUNCH.md 약관 리스크 판단)
    · 실패했으면 하루에 한 번까지만 다시 시도한다(로그인할 때마다 HandSOS 에 붙지 않게)
    · 일요일 수집이 이미 돌고 있으면 건너뛴다
    · 로그인 직후엔 와이파이가 아직일 수 있어 몇 분 기다렸다가 본다. 끝내 안 되면 다음 로그인 때

사용(보통은 launchd 가 부른다):
    .venv/bin/python worker/catchup.py
    CATCHUP_DRY=1 .venv/bin/python worker/catchup.py      # 판단만 — 수집은 안 돌린다
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

from env import load_env

load_env()

ROOT = Path(__file__).resolve().parent.parent
DUE_DAYS = 7          # 일요일 1회 — 마지막 성공이 이만큼 지났으면 그 주를 놓친 것
RETRY_HOURS = 20      # 실패한 시도 뒤엔 하루에 한 번까지만
NET_TRIES = 10        # 로그인 직후 와이파이를 기다리는 횟수(30초씩 — 5분)
NET_WAIT = 30


def _ts() -> str:
    return dt.datetime.now().strftime("%F %T")


def say(msg: str) -> None:
    print(f"[{_ts()}] [catchup] {msg}", flush=True)   # 수집 로그(collect.out.log)에 함께 쌓인다


def decide(last_ok: dt.datetime | None, last_attempt: dt.datetime | None, now: dt.datetime) -> tuple[bool, str]:
    """(돌릴까, 왜). 네트워크 없이 판정한다(테스트가 이걸 본다)."""
    failed_last = last_attempt is not None and (last_ok is None or last_attempt > last_ok)
    if failed_last:
        hours = (now - last_attempt).total_seconds() / 3600
        if hours < RETRY_HOURS:
            return False, f"{hours:.0f}시간 전에 이미 시도했다(실패) — 하루 한 번까지만"
    if last_ok is None:
        return True, "수집 성공 기록이 없다 — 한 번 돌린다"
    days = (now - last_ok).total_seconds() / 86400
    if days >= DUE_DAYS:
        return True, f"마지막 성공 {days:.1f}일 전 — 놓친 주를 지금 채운다"
    return False, f"마지막 성공 {days:.1f}일 전 — 밀리지 않았다(일요일 수집 그대로)"


def _when(ts: object) -> dt.datetime | None:
    if not ts:
        return None
    return dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))


def _last_times() -> tuple[dt.datetime | None, dt.datetime | None]:
    """sync_jobs 의 마지막 성공 · 마지막 시도(모든 매장 — 수집은 매장을 한꺼번에 돈다). 서비스 키로, 시각만 읽는다."""
    import supa

    ok = supa._get("/sync_jobs", {"select": "finished_at", "status": "eq.ok",
                                  "order": "finished_at.desc", "limit": "1"})
    tried = supa._get("/sync_jobs", {"select": "finished_at", "finished_at": "not.is.null",
                                     "order": "finished_at.desc", "limit": "1"})
    return (_when(ok[0]["finished_at"]) if ok else None), (_when(tried[0]["finished_at"]) if tried else None)


def _running() -> bool:
    """일요일 수집(run_mac.sh)이 지금 돌고 있나."""
    r = subprocess.run(["pgrep", "-f", "worker/run_mac.sh"], capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def _collect() -> int:
    return subprocess.call(["/bin/bash", str(ROOT / "worker" / "run_mac.sh")], cwd=ROOT)


def main() -> int:
    last = None
    for i in range(NET_TRIES):
        try:
            last = _last_times()
            break
        except Exception as exc:  # noqa: BLE001 — 로그인 직후엔 와이파이가 아직일 수 있다
            if i == NET_TRIES - 1:
                say(f"수집 기록을 못 읽었다({str(exc)[:80]}) — 다음 로그인 때 다시 본다")
                return 0
            time.sleep(NET_WAIT)
    run, why = decide(last[0], last[1], dt.datetime.now(dt.timezone.utc))
    say(why)
    if not run:
        return 0
    if _running():
        say("일요일 수집이 이미 돌고 있다 — 건너뛴다")
        return 0
    if os.environ.get("CATCHUP_DRY"):
        say("판단만(CATCHUP_DRY) — 수집은 안 돌린다")
        return 0
    say("밀린 수집 시작(run_mac.sh — 백업까지)")
    rc = _collect()
    say(f"밀린 수집 종료(exit={rc})")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
