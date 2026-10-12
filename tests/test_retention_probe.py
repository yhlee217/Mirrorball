"""개선 계획 v4 사전 측정(worker/retention_probe.py) — 세는 기준이 맞는지.

측정이 틀리면 '첫 방문 안부를 주 몇 명' '다시 오실 때를 며칠에' 같은 기본값을 잘못 정한다.
네트워크 없이 순수 계산만 본다. 이름·전화번호는 측정에 들어오지도 않는다.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import retention_probe as rp  # noqa: E402

NOW = dt.datetime(2026, 10, 12, 15, 0, tzinfo=rp.up.KST)  # 월요일
TODAY = NOW.date()


def d(days: int) -> str:
    return (TODAY + dt.timedelta(days=days)).isoformat()


def cust(cid: str, ext: str = "100", churned: str | None = None) -> dict:
    return {"id": cid, "ext_id": ext, "churned_at": churned}


def tx(cid: str, day: int, service: str = "여자컷", kind: str | None = "service") -> dict:
    return {"customer_id": cid, "date": d(day), "service": service, "kind": kind}


CUSTOMERS = [
    cust("A"), cust("B"), cust("C"), cust("D"), cust("E"), cust("F"),
    cust("W", ext="손님"),                 # 워크인 집계 — 세지 않는다
    cust("X", churned="2026-09-01T00:00:00Z"),  # 이탈 표시 — 세지 않는다
]
TXS = [
    # A: 120일 전 첫 방문, 30일 뒤 다시(90일 안) — 닫힌 손님
    tx("A", -120), tx("A", -90),
    # B: 200일 전 첫 방문, 100일 뒤 다시(90일 넘어서) — 닫힌 손님, 90일 안엔 안 옴
    tx("B", -200), tx("B", -100),
    # C: 150일 전 한 번 — 닫힌 손님, 안 옴. 방문 1회 풀의 91~180일
    tx("C", -150),
    # D: 지난주 첫 방문(6일 전) — 방문 1회 풀의 0~13일, 주당 첫 방문에 잡힌다
    tx("D", -6), tx("D", -6, "선불충전", "charge"),
    # E: 40일 전 한 번 + 예약 있음 → 방문 1회 풀에서 뺀다
    tx("E", -40),
    # F: 충전만 — 방문 없음
    tx("F", -30, "선불충전", "charge"),
    # 워크인·이탈 — 세지 않는다
    tx("W", -6), tx("X", -6),
    # kind 가 비어 있으면 메뉴명으로 판정(충전은 방문 아님)
    tx("A", -10, "선불충전", None),
]
BOOKINGS = [
    {"customer_id": "E", "date": d(5), "time": "11:00", "status": "예약"},
    {"customer_id": "C", "date": d(9), "time": "13:00", "status": "예약취소"},  # 취소 — 예약 아님
]
CONTACTS = [
    {"customer_id": "A", "kind": "contact", "why": "sms", "sent_at": "2026-09-20T03:00:00Z"},  # 그 뒤 방문 없음
    {"customer_id": "B", "kind": "contact", "why": "call", "sent_at": "2026-07-01T03:00:00Z"},  # 7.4 방문(-100) → 오심
    {"customer_id": "B", "kind": "contact", "why": "sms", "sent_at": "2026-07-02T03:00:00Z"},  # 같은 분 두 번 — 사람은 한 번
    {"customer_id": "E", "kind": "contact", "why": "copy", "sent_at": "2026-10-01T03:00:00Z"},  # 그 뒤 예약 → 예약 잡힘
]


def m():
    return rp.measure(CUSTOMERS, TXS, BOOKINGS, CONTACTS, NOW)


def test_visit_dates_skip_charges_and_duplicates():
    v = rp.visit_dates(TXS)
    assert v["A"] == [d(-120), d(-90)]       # 충전(kind 없음 → 메뉴명으로 충전)은 방문이 아니다
    assert v["D"] == [d(-6)]                 # 같은 날 충전은 방문을 늘리지 않는다
    assert "F" not in v


def test_first_to_second_visit():
    r = m()
    assert r["customers"] == 6               # 워크인·이탈 표시 제외
    assert r["closed"] == 3                  # A·B·C (첫 방문 90일~1년 전)
    assert dict(r["reach"]) == {28: 0, 42: 1, 56: 1, 90: 1}   # A 만 30일 만에
    assert r["gap"]["n"] == 2 and r["gap"]["p50"] == 100      # A 30일 · B 100일


def test_first_visits_per_week():
    # 오늘(10.12 월) 전까지 꽉 찬 8주(8.17~10.11) — E(9.2 수)는 셋째 주, D(10.6 월)는 마지막 주.
    # A·B·C 는 8주보다 전, F 는 방문이 없다
    assert m()["per_week"] == [0, 0, 1, 0, 0, 0, 0, 1]


def test_single_visit_pool_skips_booked():
    pool = dict(m()["pool"])
    assert pool[(0, 13)] == 1                # D
    assert pool[(28, 56)] == 0               # E 는 예약이 있어 빠진다
    assert pool[(91, 180)] == 1              # C(취소된 예약은 예약이 아니다)


def test_contacts_then_visit_or_booking():
    r = m()
    assert r["contacts"] == 4 and r["contacted"] == 3
    assert r["contact_since"] == "2026-07-01"
    assert (r["came"], r["booked"]) == (1, 1)     # B 오심 · E 예약 · A 아직
    assert r["via"] == {"sms": 2, "call": 1, "copy": 1}


def test_pages_and_report_print_counts_only():
    r = m()
    assert rp.pages(0) == 1 and rp.pages(1000) == 1 and rp.pages(1001) == 2
    out = "\n".join(rp.report("demo", r) + rp.verdicts([r]))
    assert "거래" in out and "첫 방문" in out
    for name in ("김", "010"):              # 이름·번호는 측정에 들어오지 않는다
        assert name not in out
