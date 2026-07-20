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
    def __init__(self, data=None):
        self.status_code = 200
        self.text = ""
        self._data = data if data is not None else []

    def json(self):
        return self._data


class _FakeClient:
    """httpx.Client 대역 — get(범위 내 기존 ext_id 조회)·delete 호출 기록.
    현 delete_stale 은 'not.in URL' 대신 기존 ext_id 를 읽어 로컬 차집합만 삭제한다."""
    deletes: list = []
    gets: list = []
    existing: list = []       # _existing_ext_ids 가 돌려줄 기존 ext_id 목록

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, params=None, headers=None):
        _FakeClient.gets.append({"url": url, "params": params or {}})
        off = int((params or {}).get("offset", "0"))
        rows = [{"ext_id": e} for e in _FakeClient.existing] if off == 0 else []
        return _FakeResp(rows)

    def delete(self, url, params=None, headers=None):
        _FakeClient.deletes.append({"url": url, "params": params or {}})
        return _FakeResp()


def _deleted_ext_ids(deletes) -> set:
    """delete 호출들의 ext_id=in.(...) 에서 실제 삭제된 ext_id 집합 추출."""
    import re
    out: set = set()
    for c in deletes:
        m = re.search(r"in\.\((.*)\)", c["params"].get("ext_id", ""))
        if m:
            out |= {s.strip().strip('"') for s in m.group(1).split(",") if s.strip()}
    return out


@pytest.fixture
def fake_delete(monkeypatch):
    _FakeClient.deletes = []
    _FakeClient.gets = []
    _FakeClient.existing = []
    monkeypatch.setattr(supa, "_URL", "http://supa.test")
    monkeypatch.setattr(supa, "_KEY", "svc-key")
    monkeypatch.setattr(supa.httpx, "Client", _FakeClient)
    return _FakeClient


# ── H1: 빈 수집분 전체삭제 금지 ──
def test_delete_stale_empty_without_allow_is_noop(fake_delete):
    # 예약 수확 실패로 빈 리스트가 와도 어떤 HTTP 도 나가면 안 됨(전량 삭제 사고 방지)
    fake_delete.existing = ["B0", "B1"]
    supa.delete_stale("bookings", "tid-1", [])
    assert fake_delete.deletes == [] and fake_delete.gets == []   # 조회·삭제 모두 미발생 = 보존


def test_delete_stale_empty_with_allow_deletes_all(fake_delete):
    # '진짜 0건' 을 확인한 호출자만 allow_empty=True → 범위 내 기존분 전부(스테일) 삭제
    fake_delete.existing = ["B0", "B1"]
    supa.delete_stale("bookings", "tid-1", [], allow_empty=True)
    assert _deleted_ext_ids(fake_delete.deletes) == {"B0", "B1"}   # 기존 전부 삭제


def test_delete_guards_empty_tenant(fake_delete):
    # 빈 tenant_id 로 파괴적 호출 시 전체삭제 대신 에러(defense-in-depth)
    with pytest.raises(ValueError):
        supa.delete("bookings", "")
    with pytest.raises(ValueError):
        supa.delete_stale("bookings", "", ["B0"])
    assert fake_delete.deletes == [] and fake_delete.gets == []   # 어떤 HTTP 도 나가지 않음


def test_delete_stale_deletes_only_stale(fake_delete):
    # 기존 [B0,B1,B2] 중 수집분 [B0,B1] 유지 → B2(스테일)만 삭제(B0/B1 은 보존)
    fake_delete.existing = ["B0", "B1", "B2"]
    supa.delete_stale("bookings", "tid-1", ["B0", "B1"])
    assert _deleted_ext_ids(fake_delete.deletes) == {"B2"}


# ── H2: 거래 스테일 정리는 수집한 날짜 범위로 한정 ──
def test_delete_stale_scopes_by_date_range(fake_delete):
    # 범위 밖 과거 거래를 안 지우도록, 기존 조회(GET)·삭제(DELETE) 모두 date gte/lte 로 좁혀야 함
    fake_delete.existing = ["100-2026-06-01-0", "100-2026-06-03-0"]
    supa.delete_stale("transactions", "tid-1", ["100-2026-06-01-0"],
                      date_from="2026-06-01", date_to="2026-06-07")
    # 기존 조회가 날짜 범위로 스코프됐는지
    assert fake_delete.gets, "범위 내 기존 ext_id 조회 GET 발생해야"
    gp = fake_delete.gets[0]["params"]
    assert gp["tenant_id"] == "eq.tid-1"
    assert gp.get("date") == ["gte.2026-06-01", "lte.2026-06-07"]
    # 삭제도 범위 포함 + 스테일(수집분에 없는 것)만
    assert _deleted_ext_ids(fake_delete.deletes) == {"100-2026-06-03-0"}
    dp = fake_delete.deletes[0]["params"]
    assert dp.get("date") == ["gte.2026-06-01", "lte.2026-06-07"]


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


# ── M3: 창 분할이 경계일을 겹치지 않아야(이중 집계 방지) ──
def test_windows_no_boundary_overlap_and_full_cover():
    from datetime import date as _date, timedelta
    today = _date(2026, 7, 13)
    wins = scrape._windows(760, today)      # 365+365+30
    # 각 창 ≤365일
    for s, e in wins:
        assert (e - s).days + 1 <= 365 and s <= e
    # 경계일 비중복: 모든 창의 날짜 집합이 서로소
    seen = set()
    for s, e in wins:
        d = s
        while d <= e:
            assert d not in seen, f"경계일 중복: {d}"
            seen.add(d)
            d += timedelta(days=1)
    # 전체 760일을 빠짐없이 커버(today 포함 과거 760일)
    assert max(seen) == today
    assert (today - min(seen)).days + 1 == 760


# ── M4: relink 가 고객번호 내부 '-' 를 보존해야 ──
def test_custno_of_preserves_internal_dash():
    import relink
    assert relink.custno_of("100-2026-06-01-0") == "100"
    assert relink.custno_of("A-1-2026-06-01-3") == "A-1"     # 대시 포함 고객번호
    assert relink.custno_of("김민지-2026-12-31-12") == "김민지"


def _row(custno="100", name="김", date="2026-06-01", svc="컷", won="10,000"):
    return {"고객번호": custno, "고객명": name, "날짜": date, "상세메뉴": svc,
            "결제액": won, "전화번호": "010-1", "담당": None}


def normalize_min():
    return scrape.normalize([_row()], [])
