# Mirrorball v2 — Supabase (P0)

멀티테넌트 백엔드의 P0 스캐폴딩. 자세한 설계는 상위 `../SERVICE_ARCHITECTURE.md` 참고.

## 구성
- `migrations/0001_init.sql` — 초기 스키마 + RLS + 하이브리드 PII 경계.
  - 업무 테이블: `tenants`, `memberships`, `pos_credentials`, `customers`, `transactions`, `bookings`, `care_items`, `profiles`, `sync_jobs`.
  - **PII(이름·생일·전화)** = `customers.pii_enc`(bytea, 앱 계층 AES-GCM 봉투). **운영지표** = 평문.
  - RLS: 멤버는 `current_tenant_ids()`로 자기 테넌트만. 수집 워커는 `service_role`로 RLS 우회.

## 적용
```bash
# Supabase CLI 설치·로그인 후 프로젝트 링크
supabase link --project-ref <PROJECT_REF>
supabase db push          # migrations/ 적용
# 또는 대시보드 SQL Editor 에 0001_init.sql 붙여넣기 실행
```

## 키 계층(하이브리드 암호화)
- `KEK`(마스터) — 앱 서버/Vault 환경변수. DB에 두지 않음.
- 테넌트별 `DEK` — 생성 후 KEK로 래핑해 `tenants.dek_wrapped`에 저장.
- PII·POS 자격증명은 DEK/KEK로 암호화 후 `bytea`로만 저장. 복호화는 앱·워커 프로세스에서만.

## 다음(P1~)
- P1: Next.js 앱 셸 + Supabase Auth + 홈 화면 포팅(인증 API, RLS 조회).
- P2: 수집 워커(Fly.io + Playwright) — `import/scrape_handsos` 이식, 세션 재사용.
- P3: hayewoni `records.yaml` → 이 스키마로 1회 임포트(PII 암호화).

> 주의: `auth.users`·`auth.uid()`는 Supabase 전용. 순수 Postgres에 적용하려면 auth 스키마 대체 필요.
