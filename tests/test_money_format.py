"""금액 표기 — web/lib/format.ts won(합계) · price(객단가).

합계는 만원 단위면 충분하지만 가격은 아니다(65,000 이 '7만원'이 되면 시술끼리 견줄 수 없다).
TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

WON = [0, 5000, 33000, 65000, 3_120_000, 99_999_999, 123_456_789]
PRICE = [0, 5000, 9999, 10000, 30000, 33000, 65000, 99_400, 99_960, 180_000]


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/format.ts"], "const F = require('./format.js');\n"
                 "out({ won: D.won.map(F.won), price: D.price.map(F.price) });\n",
                 {"won": WON, "price": PRICE})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_won_totals(ts):
    assert ts["won"] == ["0원", "5,000원", "3만원", "7만원", "312만원", "1.0억원", "1.2억원"]


def test_price_keeps_one_decimal_under_100k(ts):
    assert ts["price"] == ["0원", "5,000원", "9,999원", "1만원", "3만원", "3.3만원", "6.5만원",
                           "9.9만원", "10만원", "18만원"]
