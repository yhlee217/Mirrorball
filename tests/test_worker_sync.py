"""워커 수집 파이프라인 회귀 테스트 (코드리뷰 H1·H2).

네트워크 없이 순수 로직을 검증한다:
  · delete_stale 의 '빈 수집분 전체삭제 금지' 방어(H1) — 실제 DELETE HTTP 발생 여부로 확인.
  · normalize 의 reservations_ok 전파(H1).
  · 거래 스테일 ext_id 계산(H2) — delete_stale 대상이 현재 수집분으로 좁혀지는지.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import supa  # noqa: E402
import scrape  # noqa: E402


class _FakeResp:
    status_code = 200
    text = ""


class _FakeClient:
    """httpx.Client 대역 — delete 호출을 calls 리스트에 기록."""
    calls: list = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def delete(self, url, params=None, headers=None):
        _FakeClient.calls.append({"url": url, "params": params or {}})
        return _FakeResp()


@pytest.fixture
def fake_delete(monkeypatch):
    _FakeClient.calls = []
    monkeypatch.setattr(supa, "_URL", "http://supa.test")
    monkeypatch.setattr(supa, "_KEY", "svc-key")
    monkeypatch.setattr(supa.httpx, "Client", _FakeClient)
    return _FakeClient


# ── H1: 빈 수집분 전체삭제 금지 ──
def test_delete_stale_empty_without_allow_is_noop(fake_delete):
    # 예약 수확 실패로 빈 리스트가 와도 DELETE 가 나가면 안 됨(전량 삭제 사고 방지)
    supa.delete_stale("bookings", "tid-1", [])
    assert fake_delete.calls == []            # HTTP 미발생 = 기존 예약 보존


def test_delete_stale_empty_with_allow_deletes_all(fake_delete):
    # '진짜 0건' 을 확인한 호출자만 allow_empty=True → 테넌트 전체(스테일) 삭제
    supa.delete_stale("bookings", "tid-1", [], allow_empty=True)
    assert len(fake_delete.calls) == 1
    p = dict(fake_delete.calls[0]["params"])
    assert p["tenant_id"] == "eq.tid-1" and "ext_id" not in p   # ext_id 필터 없음 = 전체


def test_delete_stale_nonempty_uses_not_in(fake_delete):
    supa.delete_stale("bookings", "tid-1", ["B0", "B1"])
    assert len(fake_delete.calls) == 1
    p = dict(fake_delete.calls[0]["params"])
    assert p["tenant_id"] == "eq.tid-1"
    assert p["ext_id"].startswith("not.in.(") and '"B0"' in p["ext_id"] and '"B1"' in p["ext_id"]


# ── H2: 거래 스테일 정리는 수집한 날짜 범위로 한정 ──
def test_delete_stale_scopes_by_date_range(fake_delete):
    # 창 밖 과거 거래를 지우지 않도록 date gte/lte 로 범위를 좁혀야 함
    supa.delete_stale("transactions", "tid-1", ["100-2026-06-01-0"],
                      date_from="2026-06-01", date_to="2026-06-07")
    assert len(fake_delete.calls) == 1
    params = fake_delete.calls[0]["params"]      # list[tuple] (중복 date 키 허용)
    keys = [k for k, _ in params]
    assert keys.count("date") == 2               # gte + lte 둘 다
    vals = dict((k, v) for k, v in params if k != "date")
    dates = [v for k, v in params if k == "date"]
    assert "gte.2026-06-01" in dates and "lte.2026-06-07" in dates
    assert vals["tenant_id"] == "eq.tid-1"
    assert vals["ext_id"].startswith("not.in.(")


def test_normalize_tx_ext_ids_stable_same_day():
    # 같은 고객 같은 날 거래 2건 → 안정 순번 키(재수집 시 병합 정확의 전제)
    rows = [_row(date="2026-06-01", svc="컷", won="10000"),
            _row(date="2026-06-01", svc="펌", won="50000")]
    out = scrape.normalize(rows, [])
    ids = sorted(t["ext_id"] for t in out["transactions"])
    assert ids == ["100-2026-06-01-0", "100-2026-06-01-1"]


# ── H1: normalize 의 reservations_ok 전파 ──
def test_normalize_reservations_ok_default_true():
    out = normalize_min()
    assert out["reservations_ok"] is True


def test_normalize_reservations_ok_false_propagates():
    out = scrape.normalize([_row()], [], staff=None, reservations_ok=False)
    assert out["reservations_ok"] is False


def _row(custno="100", name="김", date="2026-06-01", svc="컷", won="10,000"):
    return {"고객번호": custno, "고객명": name, "날짜": date, "상세메뉴": svc,
            "결제액": won, "전화번호": "010-1", "담당": None}


def normalize_min():
    return scrape.normalize([_row()], [])
