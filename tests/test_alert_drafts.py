"""챙길 고객 문자 문구 — web/lib/drafts.ts (루트 drafts.py 의 옛 문구 테스트는 test_drafts.py).

손님께 그대로 나갈 수 있는 글이라 조사·시점·빠진 값을 사례로 고정한다. 안부(hello)는 예약 권유가
없어야 한다(개선 계획 v4 결정 2). TS 는 tsc → node(tests/tsnode.py).
"""

from __future__ import annotations

import pytest

from tsnode import run_ts

TODAY = "2026-10-12"  # 월요일

SCRIPT = """
const T = require('./drafts.js');
const C = require('./care-cycle.js');
const root = C.careFor('뿌리염색');
out({
  cop: ['하예원', '주환', '서하', '다운부', 'Amy'].map(T.copula),
  // 10.15(목) 기준 — 이번 주는 10.12(월)부터, 지난주는 10.5(월)~10.11(일)
  when: ['2026-10-15', '2026-10-14', '2026-10-13', '2026-10-12', '2026-10-11', '2026-10-05', '2026-10-04']
    .map((d) => T.whenWord(d, '2026-10-15')),
  hello: T.draftFor({ kind: 'hello', name: '김서연', designer: '하예원', svc: '뿌리염색', care: root, days: 6, when: '지난주' }),
  helloNoDesigner: T.draftFor({ kind: 'hello', name: '김서연', designer: null, svc: '뿌리염색', care: root, days: 6, when: '지난주' }),
  helloNoSvc: T.draftFor({ kind: 'hello', name: '김서연', designer: '서하', svc: null, care: null, days: 3, when: '이번 주' }),
  back: T.draftFor({ kind: 'back', name: '박지훈', designer: '하예원', svc: '뿌리염색', care: root, days: 38 }),
  backNoSvc: T.draftFor({ kind: 'back', name: '박지훈', designer: null, svc: null, care: null, days: 50 }),
  overdue: T.draftFor({ kind: 'overdue', name: '이하은', designer: '하예원', svc: '뿌리염색', care: root, days: 92, loyal: true }),
  due: T.draftFor({ kind: 'due', name: '이하은', designer: null, svc: '펌', care: null, days: 50, cycleDays: 45 }),
});
"""


@pytest.fixture(scope="module")
def ts():
    got = run_ts(["lib/drafts.ts", "lib/care-cycle.ts"], SCRIPT, {"today": TODAY})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    return got


def test_copula_follows_the_last_syllable(ts):
    assert ts["cop"] == ["이에요", "이에요", "예요", "예요", "이에요"]


def test_when_word(ts):
    assert ts["when"] == ["오늘", "어제", "이번 주", "이번 주", "지난주", "지난주", "지난번"]


def test_hello_has_no_booking_push(ts):
    for k in ("hello", "helloNoDesigner", "helloNoSvc"):
        assert "예약" not in ts[k], k
    assert ts["hello"] == ("김서연님, 지난주 뿌리염색 해드린 하예원이에요 😊 지내보시니 괜찮으세요? "
                           "너무 뜨거운 물로 자주 감지 않으시면 색이 더 오래가요. 불편한 점 있으면 편하게 말씀 주세요!")
    assert ts["helloNoDesigner"].startswith("김서연님, 지난주 뿌리염색 받으신 뒤로 지내보시니 괜찮으세요? 😊")
    assert ts["helloNoSvc"] == "김서연님, 이번 주 뵀던 서하예요 😊 지내보시니 괜찮으세요? 불편한 점 있으면 편하게 말씀 주세요!"


def test_back_introduces_the_designer(ts):
    assert ts["back"] == ("박지훈님, 하예원이에요! 5주 전 처음 오셨을 때 뿌리염색 해드렸는데, 뿌리 올라올 때쯤이라 "
                          "연락드려요. 편하신 시간에 예약 도와드릴게요!")
    assert ts["backNoSvc"] == "박지훈님, 7주 전 처음 뵙고 시간이 좀 지났네요. 편하신 시간에 예약 도와드릴게요!"


def test_existing_drafts_unchanged(ts):
    """이탈 위험·재방문 도래 문구는 화면에 있던 그대로 옮겼다."""
    assert ts["overdue"] == ("이하은님, 오랜만이에요! 벌써 3개월 됐네요. 늘 찾아주셔서 감사해요 🙏 지난 뿌리염색 "
                             "뿌리 올라올 때쯤이라 한번 뵙고 싶어서 연락드려요. 편하신 때 편하게 연락 주세요!")
    assert ts["due"] == "이하은님, 지난 펌 이제 관리해주실 시기예요 (평소 45일 주기). 편하신 시간에 예약 도와드릴게요!"
