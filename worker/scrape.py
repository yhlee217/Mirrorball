"""HandSOS 스크레이프 어댑터 — v1 scrape_handsos / import_handsos 재사용 지점.

멀티테넌트: 테넌트별 자격증명(creds)·세션쿠키를 주입해 로그인·수집한다.
v1(단일 Mac)은 secrets 의 단일 로그인을 썼으므로 여기서 per-tenant 로 감싼다.

반환(정규화): {
  "customers":    [{ext_id, name, birthday?, phone?, visit_count, first_visit, last_visit, total_won, revisit_state, revisit_cycle_days}, ...],
  "transactions": [{ext_id, customer_ext, date, service, amount_won}, ...],
  "bookings":     [{ext_id, customer_ext, date, time, service}, ...],
  "session_cookie": "<재사용용, 선택>",
}
PII(name/birthday/phone)는 여기선 평문으로 반환하고, sync_tenant 가 DEK로 암호화한다.
"""

from __future__ import annotations


def scrape_tenant(creds: dict, session_cookie: str | None = None) -> dict:
    # TODO(P2-scrape): v1 scrape_handsos 를 per-tenant creds 로 실행하도록 어댑트.
    #   1) Playwright 로 https://www.handsos.com/login 로그인(creds["id"], creds["pw"])
    #      - session_cookie 있으면 재사용(재로그인·2FA 회피), 만료 시 재로그인 후 새 쿠키 반환
    #   2) work/detail/saleList.asp(거래) · work/reserve/reserveList.asp(예약) 수집
    #      - scripts/handsos_selectors.yaml 셀렉터 재사용
    #   3) import_handsos.normalize(...) 로 고객·거래·예약 정규화 → 위 반환 스키마로 매핑
    #   현재는 스캐폴딩 — 실제 연결/검증은 Fly 배포 + 실 자격증명에서.
    raise NotImplementedError(
        "scrape_tenant: v1 scrape_handsos/import_handsos 어댑터 연결 필요(README §스크레이프 통합)"
    )
