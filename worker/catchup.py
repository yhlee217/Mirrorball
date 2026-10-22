"""맥을 켤 때 밀린 수집 — 로그인할 때 한 번 본다(2026-10-21, 10.18 일요일에 맥이 꺼져 있어 수집을 건너뜀).

launchd 는 예약 시각(일 14:00)에 맥이 잠자기였다면 깨어난 뒤 밀린 수집을 돌리지만, 전원이 꺼져 있었으면 다시 켜도
돌리지 않는다. 그 주는 통째로 빠지고 매일 감시가 8일째에야 알린다. 그래서 로그인할 때(launchd RunAtLoad —
scripts/mac/com.mirrorball.catchup.plist) 이것이 마지막 수집 성공을 보고, 밀렸으면 평소 수집(run_mac.sh — 백업까지)을
한 번 돌린다.

    · 마지막 일요일 수집 차례(일 14:00) 뒤로 성공이 없을 때만 돈다 — 밀린 주만이라 '주 1회'는 그대로(LAUNCH.md 약관 리스크 판단)
    · 실패했으면 하루에 한 번까지만 다시 시도한다(로그인할 때마다 HandSOS 에 붙지 않게)
    · 일요일 수집이 이미 돌고 있거나 2시간 안에 돌 차례면 건너뛴다(두 수집이 겹치지 않게)
    · 로그인 직후엔 와이파이가 아직일 수 있어 몇 분 기다렸다가 본다. 끝내 안 되면 다음 로그인 때

'마지막 성공이 7일 넘었나'로 보던 첫 판(10.21)은 주중에 수동 · 밀린 수집이 돈 다음 주를 놓쳤다 — 수요일 성공 →
일요일 꺼짐 → 월 · 화요일에 켜면 아직 7일이 안 돼 건너뛰었다(10.22 발견). 그래서 '며칠 지났나'가 아니라 '놓친 차례가 있나'.

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
KST = dt.timezone(dt.timedelta(hours=9))
SLOT_WEEKDAY = 6      # 일요일(파이썬 월=0) · 14시 — 일요일 수집(com.mirrorball.collect.plist)과 같게(테스트가 본다)
SLOT_HOUR = 14
SOON_HOURS = 2        # 일요일 수집 차례가 이만큼 안으로 남았으면 그쪽에 맡긴다
RETRY_HOURS = 20      # 실패한 시도 뒤엔 하루에 한 번까지만
NET_TRIES = 10        # 로그인 직후 와이파이를 기다리는 횟수(30초씩 — 5분)
NET_WAIT = 30


def _ts() -> str:
    return dt.datetime.now().strftime("%F %T")


def say(msg: str) -> None:
    print(f"[{_ts()}] [catchup] {msg}", flush=True)   # 수집 로그(collect.out.log)에 함께 쌓인다


def last_slot(now: dt.datetime) -> dt.datetime:
    """now 와 같거나 앞선 마지막 일요일 수집 차례(일 14:00 KST)."""
    k = now.astimezone(KST)
    slot = (k - dt.timedelta(days=(k.weekday() - SLOT_WEEKDAY) % 7)).replace(
        hour=SLOT_HOUR, minute=0, second=0, microsecond=0)
    return slot if slot <= k else slot - dt.timedelta(days=7)


def decide(last_ok: dt.datetime | None, last_attempt: dt.datetime | None, now: dt.datetime) -> tuple[bool, str]:
    """(돌릴까, 왜). 네트워크 없이 판정한다(테스트가 이걸 본다)."""
    failed_last = last_attempt is not None and (last_ok is None or last_attempt > last_ok)
    if failed_last:
        hours = (now - last_attempt).total_seconds() / 3600
        if hours < RETRY_HOURS:
            return False, f"{hours:.0f}시간 전에 이미 시도했다(실패) — 하루 한 번까지만"
    slot = last_slot(now)
    days = None if last_ok is None else (now - last_ok).total_seconds() / 86400
    if last_ok is not None and last_ok >= slot:
        return False, f"마지막 성공 {days:.1f}일 전 — 밀리지 않았다(일요일 수집 그대로)"
    left = (slot + dt.timedelta(days=7) - now).total_seconds() / 3600
    if left < SOON_HOURS:
        return False, f"일요일 수집 차례가 {left * 60:.0f}분 뒤 — 그쪽에 맡긴다(겹치지 않게)"
    if last_ok is None:
        return True, "수집 성공 기록이 없다 — 한 번 돌린다"
    return True, f"마지막 성공 {days:.1f}일 전 — {slot.month}.{slot.day:02d} 일요일 수집 차례를 놓쳤다 · 지금 채운다"


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


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


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
    run, why = decide(last[0], last[1], _now())
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
