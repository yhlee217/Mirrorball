"""카톡 등으로 보내기(개선 계획 v11 P1) — 폰의 공유 창 · 설정의 큰 버튼 · 방문 뒤 안내.

앱의 큰 버튼이 문자뿐이라 카톡으로 연락하면 앱엔 연락이 0명으로 남았다(연락 0명이 '안 했다'인지 '다른 데서 했다'인지
모름). 공유 창은 보내기를 마쳐야 '연락함' — 창을 닫았는데 연락한 걸로 남으면 그분이 2주 동안 목록에서 사라진다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def test_share_or_copy_outcomes():
    got = run_ts(["lib/share.ts"], """
const { shareOrCopy } = require('./share.js');
const setNav = (v) => Object.defineProperty(globalThis, 'navigator', { value: v, configurable: true, writable: true });
const okClip = { writeText: async () => {} };
const badClip = { writeText: async () => { throw new Error('denied'); } };
(async () => {
  const r = {};
  setNav({ share: async () => {}, clipboard: okClip });                                       r.sent = await shareOrCopy('x');
  setNav({ share: async () => { const e = new Error('x'); e.name = 'AbortError'; throw e; }, clipboard: okClip });
  r.cancel = await shareOrCopy('x');
  setNav({ share: async () => { const e = new Error('x'); e.name = 'NotAllowedError'; throw e; }, clipboard: okClip });
  r.denied = await shareOrCopy('x');
  setNav({ clipboard: okClip });                                                             r.noShare = await shareOrCopy('x');
  setNav({ clipboard: badClip });                                                            r.nothing = await shareOrCopy('x');
  out(r);
})();
""", {})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got == {"sent": "sent", "cancel": "cancel", "denied": "copied", "noShare": "copied", "nothing": "fail"}


def test_contact_button_setting():
    got = run_ts(["lib/settings.ts"], """
const { mergeSettings, DEFAULT_SETTINGS } = require('./settings.js');
out({
  def: DEFAULT_SETTINGS.contact_button,
  share: mergeSettings({ contact_button: 'share' }).contact_button,
  junk: mergeSettings({ contact_button: 'kakao' }).contact_button,
  none: mergeSettings(null).contact_button,
  keepsOthers: mergeSettings({ contact_button: 'share', vip_visits: 9 }).vip_visits,
});
""", {})
    if got is None:
        pytest.skip("node · web/node_modules 가 없다")
    assert got == {"def": "sms", "share": "share", "junk": "sms", "none": "sms", "keepsOthers": 9}


def test_care_list_logs_share_only_when_sent():
    """챙길 고객 — 공유 창은 보내기를 마쳐야 '연락함'(share), 닫으면 안 남김, 공유가 없으면 복사로 '연락함'(copy)."""
    src = (WEB / "app" / "alerts" / "alerts-list.tsx").read_text(encoding="utf-8")
    fn = src[src.index("  async function send(id: string, text: string) {"):]
    fn = fn[: fn.index("\n  }\n")]
    assert "const r = await shareOrCopy(text);" in fn
    assert "if (r === 'sent') markContacted(id, 'share');" in fn
    assert "markContacted(id, 'copy');" in fn and "'cancel'" not in fn         # 닫으면 아무것도 안 한다
    assert "it.phone && button === 'sms' ?" in src                               # 큰 버튼은 설정을 따른다
    assert "카톡 등으로 보내기</button>" in src and "문자로 보내기</a>" in src   # 다른 쪽은 펼친 곳에
    vias = (WEB / "lib" / "contact.ts").read_text(encoding="utf-8")
    assert "CONTACT_VIAS = ['sms', 'call', 'copy', 'share']" in vias           # 기록 API 가 받는 수단(CONTACT_VIAS)
    page = (WEB / "app" / "alerts" / "page.tsx").read_text(encoding="utf-8")
    assert "button={settings.contact_button}" in page


def test_after_visit_message_follows_the_setting():
    """방문 탭 방문 뒤 안내 — 문자면 문자 앱(번호가 있을 때), 아니면 공유 창. 연락 기록엔 안 남는다(v9 그대로)."""
    page = (WEB / "app" / "visits" / "page.tsx").read_text(encoding="utf-8")
    assert "mergeSettings(tRow?.settings).contact_button" in page and "button={button}" in page
    lst = (WEB / "app" / "visits" / "visits-list.tsx").read_text(encoding="utf-8")
    assert "it.after && button === 'sms' && it.sms ?" in lst and "<ShareButton" in lst
    btn = (WEB / "components" / "share-button.tsx").read_text(encoding="utf-8")
    assert "customer-contact" not in btn                                         # 기록하지 않는다
    probe = (ROOT / "worker" / "usage_probe.py").read_text(encoding="utf-8")
    assert "'share': '공유'" in probe


def test_settings_and_profile_save_to_the_shown_salon():
    """설정 · 소개 저장도 화면과 같은 매장(getTenantId) — 소속을 직접 고르는 곳은 lib/tenant 와 데모 만들기뿐(v11 P0)."""
    for route in ("settings", "profile"):
        src = (WEB / "app" / "api" / route / "route.ts").read_text(encoding="utf-8")
        assert "await getTenantId(" in src and "from('memberships')" not in src, route
    readers = sorted(
        str(p.relative_to(WEB)) for p in list((WEB / "app").rglob("*.ts*")) + list((WEB / "lib").rglob("*.ts*"))
        if "from('memberships')" in p.read_text(encoding="utf-8")
    )
    assert readers == ["app/api/onboard/route.ts", "lib/tenant.ts"]
