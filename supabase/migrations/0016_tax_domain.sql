-- 세무대리인 버전 도메인. 미용실(customers/transactions/bookings)과 별도 테이블로 간다.
--
-- 왜 customers 를 재사용하지 않는가:
--   customers 에는 visit_count·total_won·revisit_cycle_days·visits_90d 등 미용실 전용 컬럼이
--   마이그레이션 15개에 걸쳐 쌓여 있다. 거기에 세무 필드를 얹으면 두 도메인이 서로를 오염시키고
--   쿼리마다 업종 분기가 생긴다. 나중에 공통 구조를 뽑을 때도 섞인 테이블보다 나란한 두 테이블을
--   보고 뽑는 편이 정확하다. 암호화(lib/crypto)와 RLS 패턴은 그대로 재사용한다.

-- 테넌트가 어느 업종인지. 기존 미용실 테넌트는 'salon' 로 남는다.
alter table tenants add column if not exists industry text not null default 'salon';

-- ── 거래처(수임처) ──────────────────────────────────────────────
-- ⚠️ 주민등록번호는 저장하지 않는다.
--    개인정보보호법 제24조의2는 법령에 구체적 근거가 없으면 주민등록번호 처리 자체를 금지한다.
--    세무대리인이 WEHAGO 에서 보는 것은 세무업무 근거가 있지만, 이 앱이 별도로 복사·보관할
--    근거는 없다. 실수로라도 들어갈 자리를 만들지 않기 위해 컬럼 자체를 두지 않는다.
--    같은 이유로 주소·업종코드처럼 이 앱의 목적(연락·자료요청 관리)에 불필요한 항목도 받지 않는다.
create table if not exists clients (
  id                uuid primary key default gen_random_uuid(),
  tenant_id         uuid not null references tenants(id) on delete cascade,
  biz_no            text not null,              -- 사업자등록번호(하이픈 제거해서 저장)
  name              text not null,              -- 상호. 사업자 정보라 평문
  pii_enc           bytea,                      -- {대표자명, 대표전화, 휴대전화, 담당자명, 담당자연락처}
  pii_kid           text,
  entity_type       text,                       -- corp | indiv
  fiscal_month      int,                        -- 결산월(법인). 개인은 12월 고정이라 null 허용
  tax_type          text,                       -- 일반 | 간이 | 면세 — 국세청 오픈API 로 채움
  biz_status        text,                       -- 계속사업자 | 휴업 | 폐업 — 국세청 오픈API 로 채움
  status_checked_at timestamptz,                -- 위 두 값을 마지막으로 조회한 시각
  memo              text,                       -- 담당자 성향·특이사항(인수인계 자산)
  tags              text[] not null default '{}',
  churned_at        timestamptz,                -- 수임 해지(미용실 churned_at 과 같은 방식)
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  unique (tenant_id, biz_no)
);

-- ── 자료 요청 ───────────────────────────────────────────────────
-- 핵심 업무. "무엇을 언제 요청했고 아직 안 왔는지"가 지금은 담당자 기억에만 있다.
-- WEHAGO 자동전표(통장·카드·계산서)로 자동 수집되는 것 말고, 사람이 받아내야 하는 것들을 추적한다.
create table if not exists doc_requests (
  id           uuid primary key default gen_random_uuid(),
  tenant_id    uuid not null references tenants(id) on delete cascade,
  client_id    uuid not null references clients(id) on delete cascade,
  period       text not null,               -- 대상 기간 'YYYY-MM'
  kind         text not null,               -- 인건비 | 현금증빙 | 계약서 | 재고 | 기타
  note         text,
  requested_at timestamptz,                 -- 요청한 시각(전화·카톡)
  received_at  timestamptz,                 -- null 이면 아직 안 옴 → 독촉 대상
  created_at   timestamptz not null default now()
);

-- ── 접촉 이력 ───────────────────────────────────────────────────
-- 통화·카톡·문자 기록. 통화는 iPhone 이 만든 전사 텍스트를 요약해 넣는다.
-- ⚠️ 오디오 원본은 저장하지 않는다(용량·민감도 양쪽 이유).
create table if not exists contacts (
  id         uuid primary key default gen_random_uuid(),
  tenant_id  uuid not null references tenants(id) on delete cascade,
  client_id  uuid references clients(id) on delete set null,
  at         timestamptz not null,
  channel    text not null,                 -- call | kakao | sms | visit | mail
  summary    text,                          -- 요약문(전사 원문이 아니라 요약)
  source     text,                          -- notes | manual — 어디서 들어왔는지
  ext_id     text,                          -- 원천 식별자(메모 앱 노트 id 등). 중복 방지용
  created_at timestamptz not null default now(),
  unique (tenant_id, ext_id)
);

create index if not exists clients_active_idx      on clients (tenant_id) where churned_at is null;
create index if not exists doc_requests_open_idx   on doc_requests (tenant_id, client_id) where received_at is null;
create index if not exists contacts_client_at_idx  on contacts (tenant_id, client_id, at desc);

-- ── RLS ─────────────────────────────────────────────────────────
-- 미용실 테이블과 동일한 패턴: 본인 소속 테넌트 행만 읽고 쓴다.
-- current_tenant_ids() 는 0001_init 에 정의돼 있다(security definer).
alter table clients      enable row level security;
alter table doc_requests enable row level security;
alter table contacts     enable row level security;

create policy tenant_rw on clients      using (tenant_id in (select current_tenant_ids())) with check (tenant_id in (select current_tenant_ids()));
create policy tenant_rw on doc_requests using (tenant_id in (select current_tenant_ids())) with check (tenant_id in (select current_tenant_ids()));
create policy tenant_rw on contacts     using (tenant_id in (select current_tenant_ids())) with check (tenant_id in (select current_tenant_ids()));
