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
    rows = _get("/customers", {"tenant_id": f"eq.{tenant_id}", "select": "id,ext_id"})
    return {r["ext_id"]: r["id"] for r in rows if r.get("ext_id")}


def select_all(table: str, tenant_id: str, select: str) -> list:
    """테넌트의 해당 테이블 전 행(1000 페이지네이션)."""
    out: list = []
    off = 0
    while True:
        part = _get(f"/{table}", {"tenant_id": f"eq.{tenant_id}", "select": select, "limit": "1000", "offset": str(off)})
        out += part
        if len(part) < 1000:
            break
        off += 1000
    return out


def delete(table: str, tenant_id: str):
    with httpx.Client(timeout=30) as c:
        r = c.delete(_base() + f"/{table}", params={"tenant_id": f"eq.{tenant_id}"}, headers=_headers())
        _check(r)


def insert(table: str, rows: list):
    if not rows:
        return
    with httpx.Client(timeout=60) as c:
        r = c.post(_base() + f"/{table}", headers=_headers({"Prefer": "return=minimal"}), json=rows)
        _check(r)
