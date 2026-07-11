-- Mirrorball v2 · P0 초기 스키마 (멀티테넌트 + RLS + 하이브리드 PII)
-- 대상: Supabase(Postgres). 적용: `supabase db push` 또는 SQL Editor 실행.
-- 원칙:
--   · PII(이름·생일·전화)는 앱 계층에서 봉투 암호화(AES-GCM) 후 bytea 로 저장 → DB엔 평문 없음.
--   · 운영 지표(방문수·주기·매출 등)는 평문 → 정렬·집계·필터에 사용.
--   · 모든 업무 테이블 RLS: 멤버는 자기 tenant 행만. 수집 워커는 service_role 로 RLS 우회.

create extension if not exists pgcrypto;

-- ── 테넌트(디자이너/살롱) ──
create table tenants (
  id          uuid primary key default gen_random_uuid(),
  slug        text unique not null,
  salon_name  text not null,
  timezone    text not null default 'Asia/Seoul',
  plan        text not null default 'pilot',
  dek_wrapped bytea,                         -- 테넌트별 DEK(KEK로 래핑). KEK는 앱/Vault 보관
  created_at  timestamptz not null default now()
);

-- ── 멤버십(auth.users ↔ tenant). 파일럿: 1인 1테넌트 ──
create table memberships (
  tenant_id  uuid not null references tenants(id) on delete cascade,
  user_id    uuid not null references auth.users(id) on delete cascade,
  role       text not null default 'owner',
  created_at timestamptz not null default now(),
  primary key (tenant_id, user_id)
);

-- RLS 헬퍼: 현재 로그인 사용자가 속한 tenant_id 집합
create or replace function current_tenant_ids()
returns setof uuid language sql stable security definer set search_path = public as $$
  select tenant_id from memberships where user_id = auth.uid()
$$;

-- ── POS 자격증명(HandSOS). 절대 평문 금지 · 워커(service_role) 전용 ──
create table pos_credentials (
  tenant_id      uuid primary key references tenants(id) on delete cascade,
  provider       text not null default 'handsos',
  enc_blob       bytea not null,             -- 로그인 정보(KEK 암호화)
  session_cookie bytea,                       -- 재사용 세션(암호화) → 매 사이클 재로그인 회피
  status         text not null default 'ok',  -- ok | needs_reauth | error
  last_login_at  timestamptz,
  updated_at     timestamptz not null default now()
);

-- ── 고객 카르테. PII=암호화, 운영지표=평문 ──
create table customers (
  id                 uuid primary key default gen_random_uuid(),
  tenant_id          uuid not null references tenants(id) on delete cascade,
  ext_id             text,                    -- HandSOS 고객번호(테넌트 내 유일)
  pii_enc            bytea,                   -- {이름,생일,전화} 봉투 암호화
  pii_kid            text,                    -- 키 버전(로테이션)
  visit_count        int  not null default 0,
  first_visit        date,
  last_visit         date,
  total_won          bigint not null default 0,
  revisit_cycle_days int,
  revisit_state      text,                    -- overdue | due | new | null
  tier               text,                    -- vip 등
  prefer_tags        text[] not null default '{}',
  updated_at         timestamptz not null default now(),
  unique (tenant_id, ext_id)
);

-- ── 거래(매출) ──
create table transactions (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  customer_id uuid references customers(id) on delete set null,
  date        date not null,
  service     text,
  amount_won  bigint not null default 0,
  ext_id      text,
  unique (tenant_id, ext_id)
);

-- ── 예약(다가오는 예약). source: handsos | naver ──
create table bookings (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  customer_id uuid references customers(id) on delete set null,
  date        date not null,
  time        text,
  service     text,
  status      text not null default 'confirmed',
  source      text not null default 'handsos',
  ext_id      text,
  unique (tenant_id, ext_id)
);

-- ── 케어(오늘 챙길 고객) — 파생 ──
create table care_items (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  customer_id uuid references customers(id) on delete cascade,
  kind        text not null,                 -- bday | revisit | atrisk | season
  why         text,
  draft       text,
  due_at      date,
  sent_at     timestamptz,
  created_at  timestamptz not null default now()
);

-- ── 공개 소개 페이지(비-PII) ──
create table profiles (
  tenant_id  uuid primary key references tenants(id) on delete cascade,
  tagline    text,
  bio        text,
  services   jsonb not null default '[]',
  faq        jsonb not null default '[]',
  location   text,
  lang_ko    jsonb,
  lang_en    jsonb,
  published  boolean not null default false,
  updated_at timestamptz not null default now()
);

-- ── 수집 잡(관측·재시도) — v1 _raw 로그 대체 ──
create table sync_jobs (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id) on delete cascade,
  kind        text not null default 'sync',    -- sync | backfill | reserve
  status      text not null default 'queued',  -- queued | running | ok | error
  started_at  timestamptz,
  finished_at timestamptz,
  stats       jsonb,
  error       text,
  created_at  timestamptz not null default now()
);

-- 인덱스
create index on customers    (tenant_id, revisit_state);
create index on transactions (tenant_id, date);
create index on bookings     (tenant_id, date);
create index on care_items   (tenant_id, due_at);
create index on sync_jobs    (tenant_id, created_at);

-- ── RLS 활성화 ──
alter table tenants         enable row level security;
alter table memberships     enable row level security;
alter table pos_credentials enable row level security;
alter table customers       enable row level security;
alter table transactions    enable row level security;
alter table bookings        enable row level security;
alter table care_items      enable row level security;
alter table profiles        enable row level security;
alter table sync_jobs       enable row level security;

-- 테넌트 스코프 정책(멤버 = 자기 테넌트 행만; FOR ALL). service_role 은 RLS 우회.
create policy tenant_rw on customers    using (tenant_id in (select current_tenant_ids())) with check (tenant_id in (select current_tenant_ids()));
create policy tenant_rw on transactions using (tenant_id in (select current_tenant_ids())) with check (tenant_id in (select current_tenant_ids()));
create policy tenant_rw on bookings     using (tenant_id in (select current_tenant_ids())) with check (tenant_id in (select current_tenant_ids()));
create policy tenant_rw on care_items   using (tenant_id in (select current_tenant_ids())) with check (tenant_id in (select current_tenant_ids()));
create policy tenant_rw on sync_jobs    using (tenant_id in (select current_tenant_ids())) with check (tenant_id in (select current_tenant_ids()));
create policy tenant_self  on tenants     using (id in (select current_tenant_ids()));
create policy membership_self on memberships using (user_id = auth.uid());

-- profiles: 멤버 read/write + 공개(published)는 익명 read
create policy profile_owner       on profiles using (tenant_id in (select current_tenant_ids())) with check (tenant_id in (select current_tenant_ids()));
create policy profile_public_read on profiles for select using (published = true);

-- pos_credentials: 정책 미부여 = 기본 거부(anon·authenticated 접근 불가).
--   워커는 service_role 로만 접근. 디자이너의 자격증명 입력은 서버 함수/서비스롤 경유로 처리.
