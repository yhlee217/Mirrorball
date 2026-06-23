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
    cust = {
        "id": "d", "name": "최", "care_cycle_days": 30,
        "history": [{"date": "2026-04-01", "service": "컬러"}],
    }
    alerts = ba.alerts_for(cust, date(2026, 6, 23))
    rev = [a for a in alerts if a["kind"] == "revisit"]
    assert rev and "지남" in rev[0]["why"]


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
