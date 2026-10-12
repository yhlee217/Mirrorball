"""사용 현황 점검(worker/usage_probe.py) — 개선 계획 v5 P4. 네트워크 없이 계산만.

사람 단위로 센다(같은 분께 문자·전화 둘 다 해도 한 명). 출력엔 이메일·이름·전화가 없어야 한다.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import usage_probe as up  # noqa: E402

NOW = dt.datetime(2026, 10, 20, 3, 0, tzinfo=dt.timezone.utc)


def iso(days: float) -> str:
    return (NOW - dt.timedelta(days=days)).isoformat()


MEMBERS = [{"user_id": "u1"}, {"user_id": "u2"}]
SIGNS = {"u1": iso(9), "u2": iso(2), "x": iso(0)}       # 이 매장 사람 중 가장 최근(u2)
CONTACTS = [
    {"customer_id": "c1", "why": "sms", "sent_at": iso(1)},
    {"customer_id": "c1", "why": "call", "sent_at": iso(1)},   # 같은 분 — 한 명
    {"customer_id": "c2", "why": "copy", "sent_at": iso(10)},
    {"customer_id": "c3", "why": "sms", "sent_at": iso(30)},   # 4주 밖
]
CHURNED = [{"churned_at": iso(3)}, {"churned_at": iso(40)}]


def test_measure_counts_people():
    m = up.measure(MEMBERS, SIGNS, CONTACTS, CHURNED, NOW)
    assert m["users"] == 2 and m["last_seen"] == dt.datetime.fromisoformat(iso(2))
    assert (m["contacted_7"], m["contacted_28"]) == (1, 2)
    assert m["via_28"] == {"sms": 1, "call": 1, "copy": 1}
    assert m["churned_28"] == 1


def test_report_and_verdict_print_counts_only():
    m = up.measure(MEMBERS, SIGNS, CONTACTS, CHURNED, NOW)
    line = up.report("hayewoni", m, NOW)
    assert line.startswith("[hayewoni] 계정 2개 · 마지막 접속 10.18 (2일 전) · 연락 지난 1주 1명 · 4주 2명")
    assert "@" not in line
    quiet = up.measure([{"user_id": "u1"}], {"u1": iso(9)}, [], [], NOW)
    v = up.verdict({"hayewoni": m, "juhwan": quiet}, NOW)
    assert v == ["한 주 넘게 접속이 없는 곳: juhwan — 쓰기 어려운 점을 직접 물어볼 때"]
