"""세무대리인 테넌트 생성(industry='tax'). 미용실 온보딩(onboard_designers.py)과 같은 방식.

사용:
    .venv/bin/python worker/onboard_tax.py <slug> "<사무소명>" "<이름>"          # 미리보기
    CONFIRM=1 .venv/bin/python worker/onboard_tax.py <slug> "<사무소명>" "<이름>"  # 실제 생성

예:
    CONFIRM=1 .venv/bin/python worker/onboard_tax.py taxlee "서초세무회계" "이용휘"

생성 후 로그인 연결(멤버십)은 기존 스크립트를 그대로 쓴다:
    node web/scripts/onboard-login.mjs <slug> <이메일>

테넌트마다 자체 DEK 를 갖는다(미용실과 동일). 거래처 PII(대표자명·연락처)는 이 키로만 열린다.
"""

from __future__ import annotations

import os
import sys

from env import load_env

load_env()




import mirrorball_crypto as mc  # noqa: E402
import supa  # noqa: E402


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    slug, office, name = sys.argv[1], sys.argv[2], sys.argv[3]
    dry = not os.environ.get("CONFIRM")

    existing = supa.get_tenant_by_slug(slug)
    if existing:
        # 이미 있으면 업종만 tax 로 맞춰준다(미용실로 잘못 만든 경우 복구용).
        if dry:
            print(f"[dry-run] 이미 존재: {slug} — industry='tax' 로 갱신 예정")
        else:
            supa.patch("tenants", {"id": f"eq.{existing['id']}"},
                       {"industry": "tax", "salon_name": office, "designer_name": name})
            print(f"갱신: {slug} (industry=tax)")
        return 0

    if dry:
        print(f"[dry-run] 생성 예정: {slug} · 사무소={office} · 이름={name} · industry=tax")
        print("CONFIRM=1 을 붙이면 실제로 생성합니다.")
        return 0

    dek = mc.generate_dek()
    supa.insert("tenants", [{
        "slug": slug,
        "salon_name": office,      # 컬럼명은 미용실 시절 것이지만 '소속 조직명' 으로 그대로 쓴다
        "designer_name": name,     # 마찬가지로 '사용자 이름'
        "industry": "tax",
        "dek_wrapped": mc.wrap_dek(dek),
    }])
    print(f"생성 완료: {slug} ({name} · {office})")
    print(f"다음: node web/scripts/onboard-login.mjs {slug} <이메일>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
