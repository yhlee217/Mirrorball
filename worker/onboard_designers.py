"""stores.yaml 의 designers → 없는 디자이너 테넌트를 각자 DEK와 함께 생성(멀티테넌트).

사용:      .venv/bin/python worker/onboard_designers.py [salon_slug]   # 미리보기
     CONFIRM=1 .venv/bin/python worker/onboard_designers.py [salon_slug]   # 실제 생성
기존 slug(예: hayewoni)는 건너뜀. salon_slug 생략 시 designers 가 있는 첫 store.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
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
    dry = not os.environ.get("CONFIRM")
    data = yaml.safe_load((ROOT / "secrets" / "stores.yaml").read_text(encoding="utf-8")) or {}
    stores = data.get("stores") or []
    store = next((s for s in stores if (not only and s.get("designers")) or s.get("slug") == only), None)
    if not store:
        raise SystemExit("designers 가 있는 store 를 찾지 못함(stores.yaml 확인)")
    salon = store.get("salon") or store.get("salon_name") or "살롱"
    designers = store.get("designers") or []
    if not designers:
        raise SystemExit("designers 매핑이 비어 있음")

    made = 0
    for dz in designers:
        slug, name = dz.get("slug"), dz.get("name") or dz.get("staff")
        if not slug:
            continue
        existing = supa.get_tenant_by_slug(slug)
        if existing:  # 이미 있으면 이름/살롱만 최신화(재실행 시 실명 반영)
            if dry:
                print(f"[dry-run] 이름 갱신 예정: {slug} → {name}")
            else:
                supa.patch("tenants", {"id": f"eq.{existing['id']}"}, {"designer_name": name, "salon_name": salon})
                print(f"이름 갱신: {slug} → {name}")
            made += 1
            continue
        if dry:
            print(f"[dry-run] 생성 예정: {slug} ({name}) · salon={salon}")
            made += 1
            continue
        dek = mc.generate_dek()
        supa.insert(
            "tenants",
            [{"slug": slug, "salon_name": salon, "designer_name": name, "dek_wrapped": mc.wrap_dek(dek)}],
        )
        print(f"생성: {slug} ({name})")
        made += 1
    if dry and made:
        print("CONFIRM=1 을 붙이면 실제로 생성합니다.")
    if not made:
        print("생성할 신규 디자이너 없음(모두 존재).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
