"""챙길 고객 문구(web/lib/care-draft.ts, 개선 계획 v12 P1) — 챙길 고객 탭과 상세보기가 같은 함수로.

전에는 상세보기 💬 가 빈 문자였다(이력을 보다 연락하려면 탭으로 돌아가야 했다). 이제 같은 손님이면 두 곳의 문구가 같고,
설정의 '연락 버튼'(문자 / 카톡 등)을 따른다. 같은 날 받은 시술이 둘이면 표준 주기가 가장 짧은 것이 문구를 정한다
(첫 방문 손님과 같은 규칙 — 전에는 2회 이상 손님만 받아 온 순서로 갈렸다).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tsnode import run_ts

WEB = Path(__file__).resolve().parent.parent / "web"


def _run():
    return run_ts(["lib/care-draft.ts"], """
const { careDraft, careService, lastServiceDay } = require('./care-draft.js');
const { draftFor, whenWord } = require('./drafts.js');
const { careFor, soonestCare } = require('./care-cycle.js');
const { friendlyService } = require('./service-name.js');
const base = { name: '김서연', designer: '하예원', today: '2026-10-15', visitCount: 7, vipVisits: 20, cycleDays: 35 };
// 예전 챙길 고객 화면의 문구 만들기 그대로(비교용)
const oldFirst = (state, svcs, last) => {
  const pick = soonestCare(svcs); const raw = pick?.service ?? svcs[0] ?? null;
  const svc = friendlyService(raw) || null; const care = pick?.care ?? null;
  const days = 0 + Math.round((Date.parse('2026-10-15') - Date.parse(last)) / 86400000);
  return state === 'hello'
    ? draftFor({ kind: 'hello', name: base.name, designer: base.designer, svc, care, days, when: whenWord(last, '2026-10-15') })
    : draftFor({ kind: 'back', name: base.name, designer: base.designer, svc, care, days });
};
const oldRepeat = (state, raw, last, visitCount) => {
  const svc = friendlyService(raw); const care = careFor(raw);
  const days = Math.round((Date.parse('2026-10-15') - Date.parse(last)) / 86400000);
  return draftFor({ kind: state, name: base.name, designer: base.designer, svc: svc || null, care, days,
    loyal: visitCount >= base.vipVisits, cycleDays: base.cycleDays });
};
const now = (state, services, last, visitCount = base.visitCount) => careDraft({ ...base, state, services, lastVisit: last, visitCount });
out({
  hello: [now('hello', ['뿌리염색'], '2026-10-09'), oldFirst('hello', ['뿌리염색'], '2026-10-09')],
  back: [now('back', ['여자컷', '디지털펌'], '2026-08-20'), oldFirst('back', ['여자컷', '디지털펌'], '2026-08-20')],
  due: [now('due', ['남자컷(원장)'], '2026-08-30'), oldRepeat('due', '남자컷(원장)', '2026-08-30', 7)],
  overdueLoyal: [now('overdue', ['뿌리염색'], '2026-06-01', 25), oldRepeat('overdue', '뿌리염색', '2026-06-01', 25)],
  noService: [now('due', [], '2026-08-30'), oldRepeat('due', undefined, '2026-08-30', 7)],
  twoSameDay: careService(['디지털펌', '여자컷']).raw,          // 같은 날 둘 — 주기가 짧은 쪽
  lastDay: lastServiceDay([
    { date: '2026-09-01', service: '디지털펌', kind: null },
    { date: '2026-09-20', service: '선불충전', kind: 'charge' },   // 충전은 시술이 아니다
    { date: '2026-09-12', service: '여자컷', kind: null },
    { date: '2026-09-12', service: '클리닉', kind: null },
    { date: '2026-09-12', service: '여자컷', kind: null },          // 같은 시술 두 줄 — 한 번
  ]),
});
""", {})


def test_shared_draft_matches_the_care_list_wording():
    got = _run()
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    for key in ("hello", "back", "due", "overdueLoyal", "noService"):
        now, old = got[key]
        assert now == old, key
    assert got["lastDay"] == {"day": "2026-09-12", "services": ["여자컷", "클리닉"]}
    assert got["twoSameDay"] == "여자컷"


def test_care_list_and_carte_use_the_same_draft():
    alerts = (WEB / "app" / "alerts" / "page.tsx").read_text(encoding="utf-8")
    assert "careDraft({" in alerts and "draftFor(" not in alerts
    data = (WEB / "app" / "customer" / "[id]" / "data.ts").read_text(encoding="utf-8")
    assert "careDraft({" in data and "lastServiceDay(all).services" in data and "button: settings.contact_button" in data
    page = (WEB / "app" / "customer" / "[id]" / "page.tsx").read_text(encoding="utf-8")
    assert "<ContactButtons id={cust.id} phone={phone} log={!!badge} draft={draft} button={button} />" in page
    btn = (WEB / "components" / "contact-buttons.tsx").read_text(encoding="utf-8")
    assert "if (r === 'sent') mark('share');" in btn                      # 공유는 보내기를 마쳐야 기록
    assert "const share = !!draft && (button === 'share' || !phone);" in btn # 번호가 없으면 대상일 때만 📤
    assert "smsHref(phone, draft ?? '')" in btn                             # 대상이 아니면 지금처럼 빈 문자
