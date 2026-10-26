"""매일 감시 — 빠진 일요일은 다음 날 알기(개선 계획 v16 P0, 2026-10-26).

10.25 일요일 수집이 돌지 않았다(맥 꺼짐 — 10.18 에 이어 두 주 연속). 감시는 '마지막 성공 8일'만 봐서, 10.21(수)에
수동 수집을 한 이번 주는 10.30 에야 실패했을 것이다. 밀린 수집(worker/catchup.py)과 같은 '놓친 일요일' 판정으로 —
판정할 일요일 수집 차례(일 14:00 KST, 그 뒤 20시간) 뒤로 성공이 없으면 월요일 감시가 실패(메일)한다.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import plistlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("sync_health_check", ROOT / "scripts" / "sync_health_check.py")
shc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shc)
sys.path.insert(0, str(ROOT / "worker"))

import catchup as cu  # noqa: E402

UTC = dt.timezone.utc


def kst(m: int, d: int, h: int, mi: int = 0) -> dt.datetime:
    return dt.datetime(2026, m, d, h, mi, tzinfo=shc.KST)


def row(slug: str, ok: dt.datetime | None, tried: dt.datetime | None, now: dt.datetime) -> dict:
    """sync_health 한 줄 모양(시각은 Supabase 처럼 UTC 문자열)."""
    iso = (lambda t: t.astimezone(UTC).isoformat() if t else None)
    return {"slug": slug, "last_ok": iso(ok), "last_attempt": iso(tried or ok),
            "days_since": None if ok is None else (now - ok).total_seconds() / 86400}


SUN_OK = kst(10, 18, 14, 5)       # 10.18 일요일 수집 성공(가정)
WED_OK = kst(10, 21, 16, 8)       # 10.21 수요일 수동 수집(실제)
MON = kst(10, 26, 14, 59)         # 10.26 월요일 감시(실제 실행 시각)


def test_monday_watch_catches_the_missed_sunday():
    """이번 일 — 수요일 수동 수집 뒤 일요일이 빠졌다. 예전 판정(8일)은 4.9일이라 조용했다."""
    rows = [row(s, WED_OK, None, MON) for s in ("hayewoni", "juhwan", "daunbu")]
    assert all(r["days_since"] < 8 for r in rows)                              # 8일 판정만으로는 조용하다(4.9일)
    late = shc.evaluate(rows, 8, MON)
    assert [r["slug"] for r in late] == ["hayewoni", "juhwan", "daunbu"]
    slot = shc.judged_slot(MON)
    assert slot == kst(10, 25, 14)
    assert shc._fmt(rows[0], 8, slot).endswith("· 10.25 일요일 수집 없음 — 시도 없음(맥이 꺼져 있었나요?)")


def test_failed_sunday_and_one_store_only():
    rows = [row("hayewoni", kst(10, 25, 14, 4), None, MON),                     # 일요일 성공
            row("juhwan", SUN_OK, kst(10, 25, 14, 3), MON)]                     # 일요일에 돌다 실패
    late = shc.evaluate(rows, 8, MON)
    assert [r["slug"] for r in late] == ["juhwan"]
    slot = shc.judged_slot(MON)
    assert shc._fmt(rows[1], 8, slot).endswith("· 10.25 일요일 수집 없음 — 마지막 시도 10.25 14:03(KST) 실패")
    assert "일요일 수집 없음" not in shc._fmt(rows[0], 8, slot)


def test_waits_until_monday_morning():
    """일요일 오후 감시(14:55 — 실제로 이쯤 돈다)는 수집을 기다린다. 월요일 10시부터 판정."""
    assert shc.evaluate([row("a", SUN_OK, None, kst(10, 25, 14, 55))], 8, kst(10, 25, 14, 55)) == []
    assert shc.evaluate([row("a", SUN_OK, None, kst(10, 26, 9, 59))], 8, kst(10, 26, 9, 59)) == []
    assert shc.evaluate([row("a", SUN_OK, None, kst(10, 26, 10, 1))], 8, kst(10, 26, 10, 1))
    assert shc.judged_slot(kst(10, 25, 14, 55)) == kst(10, 18, 14)              # 일요일 오후엔 아직 지난주 차례
    assert shc.evaluate([row("a", SUN_OK, None, kst(10, 26, 9))], 8, kst(10, 26, 9), grace_hours=12)   # 기준은 환경 값


def test_normal_week_stays_green():
    for now in (kst(10, 19, 10, 7), kst(10, 22, 14, 59), kst(10, 25, 13, 59), kst(10, 25, 14, 55)):
        assert shc.evaluate([row("a", SUN_OK, None, now)], 8, now) == [], now
    assert shc.evaluate([row("a", WED_OK, None, kst(10, 24, 10))], 8, kst(10, 24, 10)) == []    # 주중 수동 수집 — 토요일까지 정상


def test_old_rules_still_hold():
    """8일 · 기록 없음은 그대로(바깥 테두리). 마지막 성공 칸이 없는 줄은 날짜 판정을 하지 않는다."""
    assert shc.evaluate([{"slug": "a", "days_since": 7.9}], 8, MON) == []
    assert shc.evaluate([{"slug": "a", "days_since": 8}], 8, MON)
    never = {"slug": "neu", "last_ok": None, "last_attempt": None, "days_since": None}
    assert shc.evaluate([never], 8, MON) and "일요일 수집 없음" not in shc._fmt(never, 8, shc.judged_slot(MON))


def test_slot_is_the_collection_and_catchup_time():
    cal = plistlib.loads((ROOT / "scripts" / "mac" / "com.mirrorball.collect.plist").read_bytes())["StartCalendarInterval"]
    assert (cal["Weekday"] % 7, cal["Hour"]) == ((shc.SLOT_WEEKDAY + 1) % 7, shc.SLOT_HOUR)
    assert (shc.SLOT_WEEKDAY, shc.SLOT_HOUR) == (cu.SLOT_WEEKDAY, cu.SLOT_HOUR)
    for now in (MON, kst(10, 25, 13, 59), kst(10, 25, 14), kst(11, 1, 23, 59), dt.datetime(2026, 10, 25, 5, tzinfo=UTC)):
        assert shc.last_slot(now) == cu.last_slot(now), now


def test_main_prints_the_slot_and_workflow_explains_it():
    src = (ROOT / "scripts" / "sync_health_check.py").read_text(encoding="utf-8")
    main = src[src.index("def main"):]
    assert "slot = judged_slot(now, grace)" in main and "late = evaluate(rows, stale_days, now, grace)" in main
    assert "판정할 일요일 수집" in main
    wf = (ROOT / ".github" / "workflows" / "sync-health.yml").read_text(encoding="utf-8")
    assert "SLOT_GRACE_HOURS" in wf and "STALE_DAYS: '8'" in wf
