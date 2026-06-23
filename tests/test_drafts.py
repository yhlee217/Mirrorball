"""추천 문구(초안) 생성 테스트 — drafts.draft_for."""

from datetime import date

import drafts

TODAY = date(2026, 6, 23)


def test_bday_uses_name_and_prefer():
    c = {"name": "박○○", "prefer": ["밝은 톤"]}
    msg = drafts.draft_for("bday", c, TODAY)
    assert "박○○님 생일 축하" in msg
    assert "밝은 톤" in msg                    # 취향 반영


def test_bday_without_prefer():
    c = {"name": "김", "prefer": []}
    msg = drafts.draft_for("bday", c, TODAY)
    assert "생일 축하" in msg and "밝은 톤" not in msg


def test_revisit_anchors_service_and_months():
    c = {"name": "이", "history": [
        {"date": "2026-03-30", "service": "컬러(톤 정리)"},
    ]}
    msg = drafts.draft_for("revisit", c, TODAY)
    assert "컬러(톤 정리) 하신 지" in msg
    assert "개월" in msg                       # 경과 개월 각인(revisit_anchor)
    assert "톤 정리하면" in msg                 # 컬러 계열 혜택 문구


def test_revisit_perm_benefit():
    c = {"name": "지우", "history": [{"date": "2026-01-18", "service": "레이어드펌"}]}
    msg = drafts.draft_for("revisit", c, TODAY)
    assert "펌" in msg and "손질이 편" in msg


def test_latest_service_picked():
    c = {"name": "최", "history": [
        {"date": "2026-01-15", "service": "발레아주"},
        {"date": "2026-04-02", "service": "레이어드펌"},   # 최신
    ]}
    s, d = drafts._latest_service(c)
    assert s == "레이어드펌" and d == date(2026, 4, 2)


def test_no_overclaim_words():
    # KB no_medical_overclaim — 과장/단정 표현이 기본 문구에 없어야
    c = {"name": "박○○", "prefer": ["밝은 톤"], "history": [{"date": "2026-04-20", "service": "발레아주"}]}
    for kind in ("bday", "revisit"):
        msg = drafts.draft_for(kind, c, TODAY)
        for bad in ("100%", "완벽", "최고", "무조건", "보장"):
            assert bad not in msg
