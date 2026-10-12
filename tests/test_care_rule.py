"""'챙길 고객' 판정 — 앱(web/lib/customers.ts needsCare)과 사전 측정(worker/ux_probe.py)이 같은 답을 내는지.

판정이 두 벌이라 한쪽만 바뀌면 측정 숫자가 화면과 어긋난다. 같은 사례를 양쪽에 돌려 대조한다.
TS 쪽은 tsc 로 컴파일해 node 로 실행한다(tests/tsnode.py). 도구가 없으면 건너뛰고, 컴파일이 깨지면 실패한다.
휴가(설정 → 휴무)를 반영한 재방문 판정(careState)도 같은 사례로 대조한다.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import ux_probe as up  # noqa: E402

TODAY = dt.datetime.now(up.KST).date()
S = up.lapse_settings(None)          # web DEFAULT_SETTINGS 와 같은 값


def ago(days: int | None) -> str | None:
    return None if days is None else (TODAY - dt.timedelta(days=days)).isoformat()


# 경계(180·360일)에서 충분히 떨어진 날짜만 쓴다 — 자정 근처 하루 차이로 흔들리지 않게
CASES = [
    ("재방문 도래 — 챙김",           {"revisit_state": "due", "last_visit": ago(40), "visit_count": 3}, False, True),
    ("이탈 위험 — 챙김",             {"revisit_state": "overdue", "last_visit": ago(60), "visit_count": 4}, False, True),
    ("이탈 위험이지만 이미 예약",     {"revisit_state": "overdue", "last_visit": ago(60), "visit_count": 4}, True, False),
    ("재방문 도래지만 이미 예약",     {"revisit_state": "due", "last_visit": ago(40), "visit_count": 3}, True, False),
    ("디자이너가 이탈 표시",          {"revisit_state": "overdue", "last_visit": ago(60), "visit_count": 4,
                                      "churned_at": "2026-09-01T00:00:00Z"}, False, False),
    ("12개월 넘게 안 옴 — 이탈 판정", {"revisit_state": "overdue", "last_visit": ago(400), "visit_count": 9}, False, False),
    ("6개월 넘고 3회 미만 — 이탈 판정", {"revisit_state": "overdue", "last_visit": ago(200), "visit_count": 2}, False, False),
    ("6개월 넘었지만 단골 — 챙김",    {"revisit_state": "overdue", "last_visit": ago(200), "visit_count": 5}, False, True),
    ("신규는 챙길 고객 아님",         {"revisit_state": "new", "last_visit": ago(20), "visit_count": 1}, False, False),
    ("상태 없음",                    {"revisit_state": None, "last_visit": ago(20), "visit_count": 2}, False, False),
    ("마지막 방문 모름 — 이탈 판정",  {"revisit_state": "due", "last_visit": None, "visit_count": 2}, False, False),
]


@pytest.mark.parametrize("name, c, booked, want", CASES, ids=[c[0] for c in CASES])
def test_python_rule(name, c, booked, want):
    assert up.needs_care(c, S, TODAY, booked) is want


# 할 일(챙길 고객 탭) = 상태(needsCare) 이면서 최근 연락하지 않은 분
TODO_CASES = [
    ("챙길 대상 · 연락 안 함 → 할 일",   {"revisit_state": "due", "last_visit": ago(40), "visit_count": 3}, False, False, True),
    ("챙길 대상 · 최근 연락함 → 빠짐",   {"revisit_state": "due", "last_visit": ago(40), "visit_count": 3}, False, True, False),
    ("예약도 있고 연락도 함 → 빠짐",     {"revisit_state": "overdue", "last_visit": ago(60), "visit_count": 4}, True, True, False),
    ("챙길 대상 아님 · 연락 안 함",      {"revisit_state": "new", "last_visit": ago(20), "visit_count": 1}, False, False, False),
]

# 전화번호 → 링크 숫자. 9자리 미만은 번호로 보지 않는다
PHONES = [("010-1234-5678", "01012345678"), ("+82 10-1234-5678", "+821012345678"),
          ("02)345-6789", "023456789"), ("1234", None), ("", None), (None, None)]
BODY = "하예원님, 편하신 때 연락 주세요! & 예약?"


@pytest.mark.parametrize("name, c, booked, contacted, want", TODO_CASES, ids=[c[0] for c in TODO_CASES])
def test_python_todo_rule(name, c, booked, contacted, want):
    assert up.on_care_list(c, S, TODAY, booked, contacted) is want


# 휴가 — 앱과 측정이 같은 설정을 받는다. 30일 휴가(오늘−50 ~ 오늘−21)가 마지막 방문 뒤에 끼어 있다
VAC = [{"from": ago(50), "to": ago(21)}]
SV = dict(S, off_dates=up.off_dates(VAC))
VAC_CASES = [
    # 이름, 고객, 기대 상태(careState), 기대 챙김(needsCare)
    ("휴가 빼면 아직 주기 전 — 재방문 도래에서 빠짐",
     {"revisit_state": "due", "last_visit": ago(55), "visit_count": 3, "revisit_cycle_days": 35}, None, False),
    ("휴가 빼면 이탈 위험 → 재방문 도래",
     {"revisit_state": "overdue", "last_visit": ago(80), "visit_count": 4, "revisit_cycle_days": 35}, "due", True),
    ("휴가를 빼도 이탈 위험",
     {"revisit_state": "overdue", "last_visit": ago(100), "visit_count": 5, "revisit_cycle_days": 35}, "overdue", True),
    ("6개월 넘고 2회 — 휴가 빼면 이탈 판정 아님",
     {"revisit_state": "overdue", "last_visit": ago(200), "visit_count": 2, "revisit_cycle_days": 40}, "overdue", True),
    ("휴가가 마지막 방문 전 — 그대로",
     {"revisit_state": "due", "last_visit": ago(15), "visit_count": 6, "revisit_cycle_days": 10}, "due", True),
    ("앞당기지는 않는다 — 워커가 재방문 도래라면 그대로",
     {"revisit_state": "due", "last_visit": ago(100), "visit_count": 5, "revisit_cycle_days": 35}, "due", True),
]


# 첫 방문 손님(개선 계획 v4 P1) — 안부(첫 방문 14일 안) · 다시 오실 때(그날 시술의 표준 주기 ~ 두 배)
# 이름, 고객, 그날 시술, 휴가 여부, 기대
FIRST_CASES = [
    ("첫 방문 5일 — 안부",                {"visit_count": 1, "last_visit": ago(5)}, ["뿌리염색"], False, "hello"),
    ("첫 방문 13일 — 아직 안부",           {"visit_count": 1, "last_visit": ago(13)}, ["남자컷(원장)"], False, "hello"),
    ("14일 · 남자커트 4주 전 — 아무것도",   {"visit_count": 1, "last_visit": ago(20)}, ["남자컷(원장)"], False, None),
    ("뿌리염색 5주 지남 — 다시 오실 때",     {"visit_count": 1, "last_visit": ago(40)}, ["뿌리염색"], False, "back"),
    ("뿌리염색 두 배(10주) 넘음 — 내림",     {"visit_count": 1, "last_visit": ago(75)}, ["뿌리염색"], False, None),
    ("두 시술이면 짧은 주기(앞머리 3주)",     {"visit_count": 1, "last_visit": ago(30)}, ["여자컷", "앞머리컷"], False, "back"),
    ("모르는 시술은 42일",                  {"visit_count": 1, "last_visit": ago(50)}, ["드라이"], False, "back"),
    ("펌 13주~26주 안 — 다시 오실 때",       {"visit_count": 1, "last_visit": ago(170)}, ["디지털펌"], False, "back"),
    ("두 번 오신 분은 첫 방문 손님 아님",     {"visit_count": 2, "last_visit": ago(40)}, ["뿌리염색"], False, None),
    ("휴가 30일 빼면 아직 주기 전",          {"visit_count": 1, "last_visit": ago(60)}, ["뿌리염색"], True, None),
    ("휴가가 없으면 다시 오실 때",           {"visit_count": 1, "last_visit": ago(60)}, ["뿌리염색"], False, "back"),
]
# 할 일 — 이탈 표시 · 잡힌 예약 · 최근 연락이면 빠진다
FIRST_TODO = [
    ("안부 · 그대로", {"visit_count": 1, "last_visit": ago(5)}, False, False, "hello"),
    ("안부 · 예약 있음", {"visit_count": 1, "last_visit": ago(5)}, True, False, None),
    ("안부 · 연락함", {"visit_count": 1, "last_visit": ago(5)}, False, True, None),
    ("안부 · 이탈 표시", {"visit_count": 1, "last_visit": ago(5), "churned_at": "2026-09-01T00:00:00Z"}, False, False, None),
]


def _node_results() -> dict | None:
    """web/lib 의 판정을 tsc → node 로 돌린 결과(tests/tsnode.py — 컴파일이 깨지면 건너뛰지 않고 실패)."""
    return run_ts(["lib/customers.ts", "lib/settings.ts", "lib/contact.ts", "lib/care-cycle.ts"], """
const { needsCare, onCareList, careState, firstCare, onFirstList } = require('./customers.js');
const { careFor } = require('./care-cycle.js');
const { DEFAULT_SETTINGS: S } = require('./settings.js');
const { phoneDigits, smsHref, telHref } = require('./contact.js');
const SV = { ...S, off_dates: D.vac };
const c0 = (c) => ({ revisit_cycle_days: null, ...c });
out({
  needs: D.needs.map((k) => needsCare(c0(k.c), { settings: S, churned: !!k.c.churned_at, booked: k.booked, asOf: D.today })),
  todo: D.todo.map((k) => onCareList(c0(k.c), { settings: S, churned: !!k.c.churned_at, booked: k.booked, contacted: k.contacted, asOf: D.today })),
  phones: D.phones.map((p) => phoneDigits(p)),
  sms: smsHref('01012345678', D.body), tel: telHref('01012345678'),
  vacState: D.vacCases.map((c) => careState(c, SV, D.today)),
  vacNeeds: D.vacCases.map((c) => needsCare(c, { settings: SV, churned: false, booked: false, asOf: D.today })),
  first: D.first.map((k) => firstCare(k.c, k.svcs, k.vac ? SV : S, D.today)),
  firstTodo: D.firstTodo.map((k) => onFirstList(k.c, ['뿌리염색'],
    { settings: S, churned: !!k.c.churned_at, booked: k.booked, contacted: k.contacted, asOf: D.today })),
  cats: D.menus.map((m) => (careFor(m) || {}).cat || null),
});
""", {
        "needs": [{"c": c_, "booked": b} for _, c_, b, _ in CASES],
        "todo": [{"c": c_, "booked": b, "contacted": k} for _, c_, b, k, _ in TODO_CASES],
        "phones": [ph for ph, _ in PHONES],
        "body": BODY,
        "today": TODAY.isoformat(),
        "vac": VAC,
        "vacCases": [c for _, c, _, _ in VAC_CASES],
        "first": [{"c": c_, "svcs": sv, "vac": v} for _, c_, sv, v, _ in FIRST_CASES],
        "firstTodo": [{"c": c_, "booked": b, "contacted": k} for _, c_, b, k, _ in FIRST_TODO],
        "menus": MENUS,
    })


@pytest.fixture(scope="module")
def web():
    got = _node_results()
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없거나 컴파일 실패 — TS 대조 생략")
    return got


def test_web_rule_matches_python(web):
    for (name, c, booked, want), got in zip(CASES, web["needs"]):
        assert got is want, f"[TS] {name}"
        assert got == up.needs_care(c, S, TODAY, booked), f"[TS↔PY 불일치] {name}"


def test_web_todo_rule_matches_python(web):
    for (name, c, booked, contacted, want), got in zip(TODO_CASES, web["todo"]):
        assert got is want, f"[TS] {name}"
        assert got == up.on_care_list(c, S, TODAY, booked, contacted), f"[TS↔PY 불일치] {name}"


def test_web_phone_links(web):
    """문자·전화 링크 — 번호는 숫자만, 문구는 그대로 실려야 한다(& ? 가 깨지면 본문이 잘린다)."""
    assert web["phones"] == [want for _, want in PHONES]
    assert web["tel"] == "tel:01012345678"
    assert web["sms"].startswith("sms:01012345678?&body=")
    from urllib.parse import unquote
    assert unquote(web["sms"].split("body=", 1)[1]) == BODY


@pytest.mark.parametrize("name, c, want_state, want", VAC_CASES, ids=[c[0] for c in VAC_CASES])
def test_python_vacation_rule(name, c, want_state, want):
    assert up.care_state(c, SV, TODAY) == want_state
    assert up.needs_care(c, SV, TODAY, False) is want


def test_web_vacation_rule_matches_python(web):
    """휴가 동안은 '안 오신 날'이 아니다 — 앱과 측정이 같은 손님을 같은 상태로 본다."""
    for (name, c, want_state, want), st, got in zip(VAC_CASES, web["vacState"], web["vacNeeds"]):
        assert st == want_state, f"[TS 상태] {name}"
        assert got is want, f"[TS 챙김] {name}"
        assert st == up.care_state(c, SV, TODAY) and got == up.needs_care(c, SV, TODAY, False), f"[TS↔PY 불일치] {name}"


def test_no_vacation_keeps_worker_state():
    """휴가를 정하지 않았으면 워커 판정 그대로 — 예전과 같은 숫자."""
    for _, c, _, _ in VAC_CASES:
        assert up.care_state(c, S, TODAY) == c["revisit_state"]


# 시술 분류 — 웹(care-cycle.ts)과 측정(care_cycle.py)이 같은 표(care-cycle.json)를 같은 순서로 읽는가
MENUS = ["뿌리펌", "뿌리 볼륨펌", "뿌리염색", "새치커버", "남자 다운펌", "디지털펌", "염색클리닉", "두피 클리닉",
         "앞머리컷", "주니어컷", "남자컷(원장)", "여자컷(부원장)", "커트", "드라이", ""]


@pytest.mark.parametrize("name, c, svcs, vac, want", FIRST_CASES, ids=[c[0] for c in FIRST_CASES])
def test_python_first_visit_rule(name, c, svcs, vac, want):
    assert up.first_care(c, svcs, SV if vac else S, TODAY) == want


def test_web_first_visit_rule_matches_python(web):
    """첫 방문 손님 — 앱과 측정이 같은 손님을 같은 때(안부·다시 오실 때)로 본다."""
    for (name, c, svcs, vac, want), got in zip(FIRST_CASES, web["first"]):
        assert got == want, f"[TS] {name}"
        assert got == up.first_care(c, svcs, SV if vac else S, TODAY), f"[TS↔PY 불일치] {name}"


def test_web_first_todo_matches_python(web):
    for (name, c, booked, contacted, want), got in zip(FIRST_TODO, web["firstTodo"]):
        assert got == want, f"[TS] {name}"
        assert got == up.on_first_list(c, ["뿌리염색"], S, TODAY, booked, contacted), f"[TS↔PY 불일치] {name}"


def test_care_table_is_shared(web):
    import care_cycle
    assert web["cats"] == [(care_cycle.care_for(m) or {}).get("cat") for m in MENUS]
    assert web["cats"][:4] == ["뿌리펌", "뿌리펌", "뿌리염색", "뿌리염색"]     # 뿌리펌이 뿌리염색보다 먼저
