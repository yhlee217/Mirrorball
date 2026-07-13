"""secrets/stores.yaml → pos_credentials 재저장(KEK 암호화). 회사코드 포함.

사용: .venv/bin/python worker/import_creds.py [slug]   (slug 생략 시 enabled 전부)
      DRY_RUN=1 이면 실제 저장 없이 무엇을 넣을지만 출력.
시크릿은 web/.env.local 에서 자동 로드(MIRRORBALL_KEK, SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL,
SUPABASE_SERVICE_ROLE_KEY).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    """web/.env.local 을 os.environ 에 주입(이미 있으면 유지) + SUPABASE_URL 폴백."""
    p = ROOT / "web" / ".env.local"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    if not os.environ.get("SUPABASE_URL") and os.environ.get("NEXT_PUBLIC_SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = os.environ["NEXT_PUBLIC_SUPABASE_URL"]


_load_env()

import yaml  # noqa: E402

import mirrorball_crypto as mc  # noqa: E402
import supa  # noqa: E402


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    dry = bool(os.environ.get("DRY_RUN"))
    data = yaml.safe_load((ROOT / "secrets" / "stores.yaml").read_text(encoding="utf-8")) or {}
    stores = data.get("stores") or []
    n = 0
    for s in stores:
        slug = s.get("slug")
        if not slug or (only and slug != only):
            continue
        if only is None and s.get("enabled") is False:
            continue
        company = str(s.get("company_code") or "").strip()
        uid = str(s.get("username") or "").strip()
        pw = str(s.get("password") or "").strip()
        if not (company and uid and pw):
            print(f"건너뜀({slug}): company_code/username/password 중 누락")
            continue
        tenant = supa.get_tenant_by_slug(slug)
        if not tenant:
            print(f"건너뜀({slug}): tenant 없음(먼저 온보딩 필요)")
            continue
        creds = {"company": company, "id": uid, "pw": pw}
        if s.get("staff"):
            creds["staff"] = str(s["staff"])
        days = (s.get("report") or {}).get("date_range_days")
        if days is not None:
            creds["days"] = int(days)
        if s.get("designers"):  # 멀티테넌트: 담당→디자이너 매핑을 자격증명에 포함
            creds["designers"] = s["designers"]

        blob = mc.kek_encrypt_json(creds)
        # 라운드트립 자기검증(암호문이 실제로 복호화되는지)
        assert mc.kek_decrypt_json(blob) == creds, "복호화 불일치"

        if dry:
            # 자격증명 3요소(회사코드·아이디·비번)는 CI 로그에 남지 않게 전부 마스킹 — 길이만 노출.
            print(f"[dry-run] {slug}: keys={list(creds)} company=***({len(company)}) id=***({len(uid)}) "
                  f"pw=***({len(pw)}) staff={creds.get('staff')} days={creds.get('days')}")
        else:
            supa.upsert(
                "pos_credentials",
                [{"tenant_id": tenant["id"], "provider": "handsos", "enc_blob": blob, "status": "ok"}],
                "tenant_id",
            )
            print(f"OK {slug}: 자격증명 재저장(회사코드 포함, staff={creds.get('staff')}, days={creds.get('days')})")
        n += 1
    if n == 0:
        print("대상 없음(slug/enabled 확인)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
