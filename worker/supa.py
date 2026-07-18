"""Supabase PostgREST 어댑터 — 워커 전용(service_role, RLS 우회)."""

from __future__ import annotations

import os

import httpx

_URL = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def _base() -> str:
    if not _URL or not _KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 필요")
    return _URL.rstrip("/") + "/rest/v1"


def _headers(extra: dict | None = None) -> dict:
    h = {"apikey": _KEY, "Authorization": f"Bearer {_KEY}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


def _check(r) -> None:
    """4xx/5xx 시 PostgREST 응답 본문을 그대로 노출(원인 즉시 파악)."""
    if r.status_code >= 400:
        raise RuntimeError(f"Supabase {r.status_code}: {r.text[:500]}")


def _get(path: str, params: dict):
    with httpx.Client(timeout=30) as c:
        r = c.get(_base() + path, params=params, headers=_headers())
        _check(r)
        return r.json()


def get_tenant(tenant_id: str):
    rows = _get("/tenants", {"id": f"eq.{tenant_id}", "select": "id,slug,dek_wrapped"})
    return rows[0] if rows else None


def get_tenant_by_slug(slug: str):
    rows = _get("/tenants", {"slug": f"eq.{slug}", "select": "id,slug,dek_wrapped"})
    return rows[0] if rows else None


def get_credentials(tenant_id: str):
    rows = _get("/pos_credentials", {"tenant_id": f"eq.{tenant_id}", "select": "*"})
    return rows[0] if rows else None


def claim_jobs(limit: int = 5):
    return _get(
        "/sync_jobs",
        {"status": "eq.queued", "select": "*", "order": "created_at.asc", "limit": str(limit)},
    )


def upsert(table: str, rows: list, on_conflict: str):
    if not rows:
        return
    with httpx.Client(timeout=60) as c:
        r = c.post(
            _base() + f"/{table}",
            params={"on_conflict": on_conflict},
            headers=_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            json=rows,
        )
        _check(r)


def update_job(job_id: str, **fields):
    with httpx.Client(timeout=30) as c:
        r = c.patch(_base() + "/sync_jobs", params={"id": f"eq.{job_id}"}, headers=_headers(), json=fields)
        _check(r)


def list_credentialed_tenants() -> list:
    """pos_credentials 가 등록된 테넌트들(임베드 조인). SYNC_ALL 용."""
    rows = _get("/pos_credentials", {"select": "tenant_id,tenants(id,slug,dek_wrapped)"})
    out = []
    for r in rows:
        t = r.get("tenants")
        if isinstance(t, list):
            t = t[0] if t else None
        if t:
            out.append(t)
    return out


def get_customer_extmap(tenant_id: str) -> dict:
    rows = select_all("customers", tenant_id, "id,ext_id")  # 1000행 상한 회피(페이지네이션)
    return {r["ext_id"]: r["id"] for r in rows if r.get("ext_id")}


def select_all(table: str, tenant_id: str, select: str) -> list:
    """테넌트의 해당 테이블 전 행(1000 페이지네이션).

    반드시 안정 정렬(order=id)로 페이지를 나눈다. ORDER BY 없이 limit/offset 로 나누면
    Postgres 가 페이지 간 행 순서를 보장하지 않아 일부 행을 건너뛰거나 중복시킨다
    (>1000행 테넌트에서 집계 last_visit·방문수 오류, get_customer_extmap 누락→고아 거래).
    """
    out: list = []
    off = 0
    while True:
        part = _get(f"/{table}", {"tenant_id": f"eq.{tenant_id}", "select": select,
                                  "order": "id", "limit": "1000", "offset": str(off)})
        out += part
        if len(part) < 1000:
            break
        off += 1000
    return out


def delete(table: str, tenant_id: str):
    if not tenant_id:                       # 방어: 빈 tenant_id → 전체 삭제 방지(defense-in-depth)
        raise ValueError("delete: tenant_id 가 필요합니다(전체 삭제 방지)")
    with httpx.Client(timeout=30) as c:
        r = c.delete(_base() + f"/{table}", params={"tenant_id": f"eq.{tenant_id}"}, headers=_headers())
        _check(r)


def insert(table: str, rows: list):
    if not rows:
        return
    with httpx.Client(timeout=60) as c:
        r = c.post(_base() + f"/{table}", headers=_headers({"Prefer": "return=minimal"}), json=rows)
        _check(r)


def patch(table: str, filters: dict, fields: dict) -> None:
    """조건(filters: PostgREST 쿼리 형식)에 맞는 행 UPDATE."""
    with httpx.Client(timeout=30) as c:
        r = c.patch(_base() + f"/{table}", params=filters, headers=_headers(), json=fields)
        _check(r)


def delete_stale(table: str, tenant_id: str, ext_ids: list, *, allow_empty: bool = False,
                 date_from: str | None = None, date_to: str | None = None) -> None:
    """현재 수집분(ext_ids) 에 없는 행만 삭제. 업서트 후 호출해 '삽입 실패 시 전멸' 방지.

    ext_ids 가 비면 '테넌트 전체 삭제'가 되는데, 이는 수집 실패로 빈 리스트가 온 경우
    (예: 예약 페이지 수확 예외) 조용히 전량 삭제하는 사고로 이어진다(코드리뷰 H1).
    그래서 빈 리스트 전체삭제는 기본 금지하고, '정말 0건임을 확인'한 호출자만
    allow_empty=True 로 명시해야 실행된다. 아니면 no-op(기존 행 보존).

    date_from/date_to: 삭제를 이 날짜 범위로 한정(코드리뷰 H2). 거래는 수집 창(SYNC_DAYS)
    만 가져오므로, 범위 없이 스테일 정리하면 창 밖 과거 거래를 전량 삭제한다 → 반드시
    '이번에 실제 수집한 날짜 범위' 안에서만 취소·보이드된 행을 정리한다."""
    if not tenant_id:                       # 방어: 빈 tenant_id → 전체 삭제 방지(defense-in-depth)
        raise ValueError("delete_stale: tenant_id 가 필요합니다(전체 삭제 방지)")
    if not ext_ids and not allow_empty:
        return  # 방어: 빈 수집분으로 전체삭제 금지(수집 실패와 진짜 0건을 구분 못하므로 보존)
    params: list[tuple[str, str]] = [("tenant_id", f"eq.{tenant_id}")]
    if ext_ids:
        params.append(("ext_id", "not.in.(" + ",".join(f'"{e}"' for e in ext_ids) + ")"))
    if date_from:
        params.append(("date", f"gte.{date_from}"))
    if date_to:
        params.append(("date", f"lte.{date_to}"))
    with httpx.Client(timeout=30) as c:
        r = c.delete(_base() + f"/{table}", params=params, headers=_headers())
        _check(r)
