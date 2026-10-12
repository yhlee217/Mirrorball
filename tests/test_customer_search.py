"""고객 목록 검색 — 이름 또는 전화번호 뒷자리(web/lib/contact.ts phoneTail · matchesQuery).

목록은 전 고객을 화면으로 내려보낸다. 그래서 번호는 뒷자리 4자리만 보내고, 검색도 그걸로 한다.
TS 는 tsc → node(tests/tsnode.py). 마지막 테스트는 화면에 번호 원문이 실리지 않는지 소스로 지킨다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent

PHONES = ["010-1234-5678", "+82 10-1234-5678", "02)345-6789", "123", "", None]
ROW = {"name": "김서연", "tail": "5678"}
QUERIES = [
    ("5678", True),             # 뒷자리 그대로
    ("1234", False),            # 가운데 자리는 모른다(뒷자리만 있다)
    ("56 78", True),            # 띄어쓰기 무시
    ("010-1234-5678", True),    # 번호를 통째로 넣어도 뒤 4자리로
    ("78", True),               # 덜 친 동안에도 좁혀진다
    ("서연", True),
    ("박", False),
    ("", True),
    ("   ", True),
]

SCRIPT = """
const C = require('./contact.js');
out({
  tails: D.phones.map(C.phoneTail),
  hits: D.queries.map((q) => C.matchesQuery(D.row, q)),
  noTail: C.matchesQuery({ name: '박지훈', tail: '' }, '5678'),
});
"""


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/contact.ts"], SCRIPT, {"phones": PHONES, "row": ROW, "queries": [q for q, _ in QUERIES]})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_phone_tail(ts):
    assert ts["tails"] == ["5678", "5678", "6789", "", "", ""]


def test_matches_query(ts):
    assert ts["hits"] == [want for _, want in QUERIES]


def test_no_phone_never_matches_digits(ts):
    assert ts["noTail"] is False


def test_customer_list_rows_carry_only_the_tail():
    """고객 목록이 화면으로 넘기는 행에 번호 원문(phone)이 없다 — 뒷자리(tail)와 유무(hasPhone)만."""
    src = (ROOT / "web" / "app" / "customers" / "page.tsx").read_text(encoding="utf-8")
    rows = src[src.index("const rows = list.map"):src.index("return (", src.index("const rows = list.map"))]
    assert "tail:" in rows and "hasPhone:" in rows
    assert not re.search(r"\bphone\s*:", rows), "번호 원문이 화면으로 나간다"
