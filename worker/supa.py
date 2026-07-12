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


def _get(path: str, params: dict):
    with httpx.Client(timeout=30) as c:
        r = c.get(_base() + path, params=params, headers=_headers())
        r.raise_for_status()
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
        r.raise_for_status()


def update_job(job_id: str, **fields):
    with httpx.Client(timeout=30) as c:
        r = c.patch(_base() + "/sync_jobs", params={"id": f"eq.{job_id}"}, headers=_headers(), json=fields)
        r.raise_for_status()
