"""build_app 알림 엔진 테스트 — '오늘 챙길 고객' 결정 로직."""

from datetime import date

import build_app as ba


def test_birthday_alert_on_match():
    cust = {"id": "a", "name": "박", "birthday": "06-23"}
    alerts = ba.alerts_for(cust, date(2026, 6, 23))
    assert any(a["kind"] == "bday" for a in alerts)


def test_no_birthday_alert_off_day():
    cust = {"id": "a", "name": "박", "birthday": "06-24"}
    assert ba.alerts_for(cust, date(2026, 6, 23)) == []


def test_revisit_due_within_window():
    cust = {
        "id": "b", "name": "이", "care_cycle_days": 70,
        "history": [{"date": "2026-04-20", "service": "발레아주"}],
    }
    # 4/20 + 70 = 6/29 → 6/23 기준 6일 내 → 알림
    alerts = ba.alerts_for(cust, date(2026, 6, 23))
    assert any(a["kind"] == "revisit" for a in alerts)


def test_revisit_not_due_far_out():
    cust = {
        "id": "c", "name": "지우", "care_cycle_days": 150,
        "history": [{"date": "2026-04-02", "service": "레이어드펌"}],
    }
    # 4/2 + 150 = 8/30 → 윈도우 밖 → 알림 없음
    assert ba.alerts_for(cust, date(2026, 6, 23)) == []


def test_revisit_overdue_flagged():
    # 주기 30일인데 83일째 → 이탈 위험(atrisk)
    cust = {
        "id": "d", "name": "최", "care_cycle_days": 30,
        "history": [{"date": "2026-04-01", "service": "컬러"}],
    }
    alerts = ba.alerts_for(cust, date(2026, 6, 23))
    risk = [a for a in alerts if a["kind"] == "atrisk"]
    assert risk and "안 오심" in risk[0]["why"]


def test_derive_cycle_from_intervals():
    # 방문 간격 30·30 → 주기 30일(명시값 없이 이력에서 추정)
    cust = {"history": [
        {"date": "2026-04-01", "service": "컷"},
        {"date": "2026-05-01", "service": "컷"},
        {"date": "2026-05-31", "service": "컷"},
    ]}
    assert ba.derive_cycle(cust) == 30


def test_derive_cycle_needs_two_visits():
    assert ba.derive_cycle({"history": [{"date": "2026-04-01", "service": "컷"}]}) == 0


def test_revisit_state_overdue_needs_three_visits():
    # 3회+ 단골이 평소 주기 1.6배 초과 → overdue
    cust = {"loyalty_visits": 4, "history": [
        {"date": "2026-01-01", "service": "컷"},
        {"date": "2026-02-01", "service": "컷"},
        {"date": "2026-03-03", "service": "컷"},  # 간격 ~30일
    ]}
    ri = ba.revisit_state(cust, date(2026, 6, 23))   # 마지막 3/3 → 112일째 ≫ 30*1.6
    assert ri["state"] == "overdue" and ri["cycle"] == 30


def test_revisit_state_new_recent_single_visit():
    cust = {"loyalty_visits": 1, "history": [{"date": "2026-06-10", "service": "컷"}]}
    assert ba.revisit_state(cust, date(2026, 6, 23))["state"] == "new"


def test_spend_by_custno_sums_price():
    recs = [
        {"custno": "100", "price": 28000}, {"custno": "100", "price": 60000},
        {"custno": "0205", "price": 30000},               # 앞 0 제거 → 205
        {"custno": "", "price": 99999},                   # 고객번호 없음 → 제외
        {"custno": "100"},                                 # 금액 없음 → 무시
    ]
    s = ba.spend_by_custno(recs)
    assert s["100"] == 88000 and s["205"] == 30000 and "" not in s


def test_spend_tier_boundaries():
    assert ba.spend_tier(500000) == "vip"
    assert ba.spend_tier(499999) == "regular"
    assert ba.spend_tier(250000) == "regular"
    assert ba.spend_tier(100000) == "normal"
    assert ba.spend_tier(99999) == "light"


def test_build_customer_carries_ltv_and_tier():
    cust = {"id": "c1", "name": "박", "custno": "1", "total_won": 620000,
            "history": [{"date": "2026-06-01", "service": "컷"}]}
    card = ba.build_customer(cust, date(2026, 6, 23))
    assert card["total_won"] == 620000 and card["tier"] == "vip"


def test_build_one_excludes_contact_pii(tmp_path):
    cdir = tmp_path / "clients" / "demo"
    (cdir / "customers").mkdir(parents=True)
    (cdir / "config.yaml").write_text(
        "slug: demo\ntoday: 2026-06-23\n", encoding="utf-8"
    )
    (cdir / "customers" / "x.yaml").write_text(
        "id: x\nname: 김○○\ncontact: '010-1234'\nbirthday: 06-23\n",
        encoding="utf-8",
    )
    r = ba.build_one(str(cdir), dist=str(tmp_path / "out"))
    import json
    data = json.loads((tmp_path / "out" / "demo.json").read_text(encoding="utf-8"))
    blob = json.dumps(data, ensure_ascii=False)
    assert "010-1234" not in blob  # 연락처는 배포물에서 제외
    assert r["care"] == 1          # 생일 1건


def test_last_visit_picks_latest():
    cust = {"history": [
        {"date": "2026-01-15", "service": "a"},
        {"date": "2026-04-02", "service": "b"},
    ]}
    assert ba.last_visit(cust) == date(2026, 4, 2)
