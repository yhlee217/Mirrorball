"""교차판매(파이썬 단일 소스) — 규칙·우선순위·JS 폴백과의 드리프트 방지."""

import re
from pathlib import Path

import crosssell as cs

ROOT = Path(__file__).resolve().parent.parent


def _cust(name="김민지", visits=None, services=()):
    hist = [{"date": f"2026-0{i+1}-01", "service": s} for i, s in enumerate(services)]
    return {"name": name, "loyalty_visits": visits if visits is not None else len(hist),
            "history": hist}


def test_cat_of():
    assert cs.cat_of("남자컷") == "컷" and cs.cat_of("레이어드펌") == "펌"
    assert cs.cat_of("이노아 염색") == "염색" and cs.cat_of("모발 클리닉") == "클리닉"
    assert cs.cat_of("기장 추가") == "옵션" and cs.cat_of("드라이") == "기타"


def test_under_two_visits_no_offer():
    assert cs.crosssell_for(_cust(services=["컷"])) is None


def test_repeat_color_without_clinic_wins_priority():
    c = _cust(services=["염색", "염색", "컷"])          # 염색 2일 + 클리닉 0 — 컷만 규칙보다 우선
    off = cs.crosssell_for(c)
    assert off["id"] == "color_care" and "김민지님" in off["copy"]


def test_cut_only_rule():
    off = cs.crosssell_for(_cust(services=["컷", "컷"]))
    assert off["id"] == "cut_only"


def test_perm_without_clinic_rule():
    off = cs.crosssell_for(_cust(services=["레이어드펌", "컷"]))
    assert off["id"] == "perm_clinic"


def test_loyal_upsell_rule_and_none_when_covered():
    off = cs.crosssell_for(_cust(services=["컷", "염색", "클리닉", "컷"]))
    assert off["id"] == "upsell"                        # 4회+옵션0
    covered = cs.crosssell_for(_cust(services=["컷", "염색", "클리닉", "기장 추가"]))
    assert covered is None                              # 다 갖춤 → 제안 없음


def test_build_customer_carries_crosssell_and_thresholds():
    import build_app
    c = build_app.build_customer(_cust(services=["레이어드펌", "컷"]))
    assert c["crosssell"]["id"] == "perm_clinic"        # 카드에 실려 앱은 렌더만
    assert build_app.TIER_THRESHOLDS["vip"] == 500000


def test_no_drift_with_js_fallback_copies():
    """앱 JS 폴백의 카피 문구가 파이썬(단일 소스)과 동일한지 — 이중화 드리프트 감지기."""
    js = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    js_copies = re.findall(r"copy:nm\+'([^']+)'", js)
    assert len(js_copies) == 4
    py = [cs.crosssell_for(_cust(services=["염색", "염색"]))["copy"],
          cs.crosssell_for(_cust(services=["컷", "컷"]))["copy"],
          cs.crosssell_for(_cust(services=["펌", "펌"]))["copy"],
          cs.crosssell_for(_cust(services=["기타1", "기타2", "기타3", "기타4"]))["copy"]]
    for j, p in zip(js_copies, py):
        assert p == "김민지" + j                        # nm+'...' 그대로


def test_js_tier_thresholds_match_python():
    import build_app
    js = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    m = re.search(r"\{vip:(\d+),regular:(\d+),normal:(\d+)\}", js)
    assert m, "JS tier 폴백 상수를 찾지 못함"
    assert {"vip": int(m.group(1)), "regular": int(m.group(2)),
            "normal": int(m.group(3))} == build_app.TIER_THRESHOLDS
