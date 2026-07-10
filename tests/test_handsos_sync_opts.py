"""handsos_sync 런타임 옵션 — 수집 기간(--days)·예약토글(--no-reserve) 순수 헬퍼 회귀.

브라우저·핸드SOS 없이 검증: 백필(365)·배치(1)·기본(0/미지정)의 날짜 범위와,
apply_run_opts 가 report 의 다른 키를 보존하며 date_range_days 만 덮는지,
--no-reserve 가 예약 수집을 끄는지. (증분 누적 자체는 import_handsos.merge_records 담당.)
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import handsos_sync as hs


def test_date_range_backfill_365():
    # 1년 백필: (오늘-365, 오늘)
    assert hs.date_range_value(365, today=date(2026, 7, 10)) == ("2025-07-10", "2026-07-10")


def test_date_range_daily_1():
    # 10분 배치: (어제, 오늘) — 늦게 입력된 전일 거래까지 포착, merge 로 중복 없음
    assert hs.date_range_value(1, today=date(2026, 7, 10)) == ("2026-07-09", "2026-07-10")


def test_date_range_zero_is_empty():
    assert hs.date_range_value(0) == ("", "")


def test_apply_days_sets_range():
    stores = [{"slug": "hayewoni"}]
    hs.apply_run_opts(stores, days=1)
    assert stores[0]["report"]["date_range_days"] == 1


def test_apply_days_preserves_other_report_keys():
    stores = [{"slug": "x", "report": {"staff_label": "하예원", "settle_ms": 1500}}]
    hs.apply_run_opts(stores, days=365)
    assert stores[0]["report"]["date_range_days"] == 365
    assert stores[0]["report"]["staff_label"] == "하예원"
    assert stores[0]["report"]["settle_ms"] == 1500


def test_apply_no_reserve_disables():
    stores = [{"slug": "x", "collect_reservations": True}]
    hs.apply_run_opts(stores, no_reserve=True)
    assert stores[0]["collect_reservations"] is False


def test_apply_none_days_leaves_report_untouched():
    # --days 미지정이면 손대지 않음 → 핸드SOS 화면 기본 기간(이번 달) 유지
    stores = [{"slug": "x"}]
    hs.apply_run_opts(stores, days=None)
    assert "report" not in stores[0]
