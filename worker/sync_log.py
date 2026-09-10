"""수집 이력 확인 — 예정된 일요일이 실제로 돌았는지 눈으로 본다.

앱은 마지막 '성공'만 보여준다. 그래서 "8일 전"이라는 숫자만 보고는
 (a) 아예 실행이 안 됐는지  (b) 돌았는데 실패했는지 를 구분할 수 없다.
그 둘은 고치는 방법이 완전히 다르다:
  - 기록이 아예 없다      → launchd 가 안 돌았거나 run_mac.sh 가 중간에 빠져나갔다
  - error 로 남아 있다     → 로그인·크로미움·네트워크 등 수집 자체의 문제

읽기만 하므로 몇 번을 돌려도 안전하다.

사용:
    .venv/bin/python worker/sync_log.py          # 최근 8주
    WEEKS=20 .venv/bin/python worker/sync_log.py
"""

from __future__ import annotations

import datetime as dt
import os

from env import load_env

load_env()


import supa  # noqa: E402

WD = "월화수목금토일"
SCHEDULE_WD = 6  # 일요일 — com.mirrorball.collect.plist 의 Weekday 0
KST = dt.timezone(dt.timedelta(hours=9))


def _kst(iso: str) -> dt.datetime:
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(KST)


def main() -> int:
    weeks = int(os.environ.get("WEEKS", "8"))
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(weeks=weeks)).isoformat()
    rows = supa._get("/sync_jobs", {
        "select": "tenant_id,status,finished_at,error",
        "finished_at": f"gte.{since}",
        "order": "finished_at.desc",
        "limit": "500",
    })

    today = dt.datetime.now(KST).date()
    print(f"오늘 {today} ({WD[today.weekday()]}) · 최근 {weeks}주\n")

    if not rows:
        print(f"기록 없음 — 최근 {weeks}주 동안 수집이 한 번도 시작되지 않았다.")
        return 1

    # 날짜별로 묶는다(테넌트가 셋이라 한 번 돌면 세 줄이 남는다)
    byday: dict[dt.date, list] = {}
    for r in rows:
        if not r.get("finished_at"):
            continue
        byday.setdefault(_kst(r["finished_at"]).date(), []).append(r)

    for d in sorted(byday, reverse=True):
        rs = byday[d]
        ok = sum(1 for r in rs if r["status"] == "ok")
        bad = [r for r in rs if r["status"] != "ok"]
        mark = "" if d.weekday() == SCHEDULE_WD else "  ← 예정일(일) 아님. 수동 실행이었을 것"
        print(f"{d} ({WD[d.weekday()]})  성공 {ok} · 실패 {len(bad)}{mark}")
        for r in bad[:3]:
            print(f"    error: {(r.get('error') or '')[:120]}")

    # 예정된 일요일 중 흔적이 아예 없는 날 — 여기가 '조용히 사라진 주'다
    missing = []
    d = today
    while d > today - dt.timedelta(weeks=weeks):
        if d.weekday() == SCHEDULE_WD and d not in byday and d != today:
            missing.append(d)
        d -= dt.timedelta(days=1)

    print()
    if missing:
        print("예정된 일요일인데 성공도 실패도 기록이 없는 날:")
        for d in missing:
            print(f"  {d} (일)  ← run_mac.sh 가 아예 안 돌았거나 중간에 빠져나갔다")
        print("\n  맥에서 확인:")
        print("    launchctl list | grep mirrorball                 # 등록·마지막 종료코드")
        print("    tail -40 runs/collect.out.log                    # 그날 로그가 있는지")
        return 1

    print("예정된 일요일에 모두 기록이 남아 있다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
