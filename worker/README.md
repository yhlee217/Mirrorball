# Mirrorball 수집 워커 (P2 · Fly.io)

HandSOS를 테넌트별 자격증명으로 서버에서 대행 크롤링 → 정규화 → **PII 암호화** → Supabase 업서트.
`web/lib/crypto.ts`와 완전 상호운용(테넌트 DEK로 암호화하면 앱이 복호화). 크립토 교차검증 통과.

## 구성
- `mirrorball_crypto.py` — 봉투 암호화(KEK/DEK, AES-GCM). Node와 상호운용.
- `supa.py` — Supabase PostgREST 어댑터(service_role).
- `scrape.py` — **v1 `scrape_handsos`/`import_handsos` 재사용 지점**(스크레이프 통합 §).
- `sync_tenant.py` — 한 테넌트 동기화(자격증명 복호화 → 스크레이프 → PII 암호화 → 업서트).
- `run.py` — queued `sync_jobs` 처리(1회 실행 · cron이 주기 호출).
- `Dockerfile` / `fly.toml` / `requirements.txt`.

## 자격증명 등록 (디자이너 HandSOS 로그인)
KEK로 암호화해 `pos_credentials`에 저장(평문 미보관):
```bash
cd web
HANDSOS_ID=<아이디> HANDSOS_PW=<비번> node --env-file=.env.local scripts/set-handsos-creds.mjs hayewoni
```
> ⚠ 디자이너의 **명시적 동의 + 위탁 약관**을 전제로만. ToS 저촉 리스크 인지.

## 배포 A — GitHub Actions (무료 · 권장)
`.github/workflows/collect.yml` 이 크론(KST 영업시간 30분마다)으로 `SYNC_ALL=1 python worker/run.py` 실행 → 자격증명 등록된 전 테넌트 수집. 서버·비용 없음.
1. 리포 **Settings → Secrets and variables → Actions** 에 시크릿 3개: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `MIRRORBALL_KEK`(web/.env.local 과 동일 값).
2. 스케줄 트리거는 **기본 브랜치**의 워크플로만 동작 → 이 파일이 기본 브랜치에 있어야 함(claude 브랜치면 머지/기본브랜치 변경).
3. **Actions 탭 → collect → Run workflow** 로 수동 테스트.

## 배포 B — Fly.io (유료 · 선택)
> Fly는 무료 티어가 없어짐(종량제 ~$5/월). 무료로는 A(GitHub Actions) 권장.
```bash
cd /path/to/Mirrorball          # 빌드 컨텍스트는 리포 루트
fly launch --no-deploy --copy-config --dockerfile worker/Dockerfile
fly secrets set SUPABASE_URL=https://<ref>.supabase.co \
                SUPABASE_SERVICE_ROLE_KEY=<secret> \
                MIRRORBALL_KEK=<web/.env.local 과 동일 KEK>
fly deploy
```

## 스케줄 (pg_cron → sync_jobs → 워커)
Supabase SQL Editor:
```sql
create extension if not exists pg_cron;
-- 영업시간 매시 정시, 활성 테넌트에 잡 enqueue(예시)
select cron.schedule('mirrorball-enqueue', '0 10-20 * * *', $$
  insert into sync_jobs (tenant_id, kind, status)
  select id, 'sync', 'queued' from tenants where plan is not null
$$);
```
워커는 cron으로 주기 실행하며 queued 잡을 처리:
```bash
fly machine run . --schedule=hourly
```

## 스크레이프 통합 (남은 작업)
`scrape.py::scrape_tenant(creds, session_cookie)` 를 채워야 실제 수집이 된다:
1. Playwright로 `www.handsos.com/login` 로그인(`creds["id"]`, `creds["pw"]`), 세션쿠키 재사용.
2. `work/detail/saleList.asp`(거래)·`work/reserve/reserveList.asp`(예약) 수집 — `scripts/handsos_selectors.yaml` 셀렉터 재사용.
3. v1 `import_handsos.normalize`로 정규화 → 반환 스키마(customers/transactions/bookings)로 매핑.

정규화 반환 스키마는 `scrape.py` 상단 docstring 참고. PII(name/birthday/phone)는 평문 반환 → `sync_tenant`가 DEK로 암호화.
