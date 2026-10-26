"""시술별 단가(worker/price_probe.py, 2026-10-26 운영자 요청) — 네트워크 없이 계산만.

앱엔 가격표가 없고 금액은 모두 HandSOS 결제액이라, 메뉴마다 결제액의 '보통(가장 흔한 금액)' · 중간 · 범위 · 최근 6개월을
본다. 시술만(충전 · 제품 · 환불 빼고), 0원은 따로. 출력엔 메뉴 이름과 금액만 — 손님은 읽지도 찍지도 않는다.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import price_probe as pp  # noqa: E402

TODAY = dt.date(2026, 10, 26)


def tx(service, amount, date, kind="service"):
    return {"service": service, "amount_won": amount, "date": date, "kind": kind}


ROWS = (
    [tx("여자컷(부원장)", 33000, "2026-09-01")] * 7
    + [tx("여자컷(부원장)", 30000, "2026-08-01")] * 2
    + [tx("여자컷(부원장)  ", 35000, "2026-10-21")]                      # 뒤 빈칸 — 같은 메뉴
    + [tx("여자컷(부원장)", 0, "2026-10-01")]                            # 0원 — 따로 센다
    + [tx("뿌리펌", 150000, "2025-11-01")] * 5                           # 예전 값
    + [tx("뿌리펌", 165000, "2026-07-01")] * 3                           # 최근 6개월 — 올랐다
    + [tx("선불충전 30만", 300000, "2026-10-02", "charge"),
       {"service": "제품 판매", "amount_won": 25000, "date": "2026-10-03", "kind": None}]   # 0019 전 행 — 이름으로 판정
)


def test_summary_finds_the_usual_price_and_changes():
    menus, total = pp.summarize(ROWS, TODAY)
    assert [m["name"] for m in menus] == ["여자컷(부원장)", "뿌리펌"]                 # 건수 많은 순
    cut = menus[0]
    assert (cut["n"], cut["common"], round(cut["share"], 2), cut["median"], cut["p10"], cut["p90"]) == \
        (10, 33000, 0.7, 33000, 30000, 33000)
    assert cut["zero"] == 1 and cut["last"] == dt.date(2026, 10, 21) and cut["recent"] == 33000
    perm = menus[1]
    assert (perm["common"], perm["recent"], perm["recent_n"]) == (150000, 165000, 3)
    assert total == {"paid": 18, "zero": 1, "skipped": 2, "first": dt.date(2025, 11, 1), "last": dt.date(2026, 10, 21)}


def test_report_reads_like_a_price_list_without_customers():
    menus, total = pp.summarize(ROWS, TODAY)
    out = "\n".join(pp.report("hayewoni", menus, total))
    assert "시술별 단가 — hayewoni · 결제 기록 2025.11.01 ~ 2026.10.21 · 시술 18건(0원 1건 따로" in out
    assert ("  여자컷(부원장) — 10건 · 보통 33,000원(70%) · 중간 33,000원 · 범위 30,000~33,000원 · 최근 6개월 33,000원"
            " · 마지막 26.10.21 · 0원 1건") in out
    assert "뿌리펌 — 8건 · 보통 150,000원(62%)" in out and "최근 6개월 165,000원 ← 바뀜" in out
    assert "최근 6개월에 보통 금액이 바뀐 메뉴: 뿌리펌" in out
    for banned in ("customer", "선불충전", "제품 판매"):
        assert banned not in out, banned


def test_ties_pick_the_list_price_and_main_reads_only_menu_columns():
    assert pp._mode([30000, 33000]) == (33000, 1)                        # 건수가 같으면 큰 금액(정가 쪽)
    src = (ROOT / "worker" / "price_probe.py").read_text(encoding="utf-8")
    assert 'supa.select_all("transactions", t["id"], "service,amount_won,date,kind")' in src
    assert "customer" not in src.split("def main", 1)[1]
