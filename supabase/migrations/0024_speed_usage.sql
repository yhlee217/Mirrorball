-- 0024: 화면 속도 · 사용 수 · 매장 통계 저장(개선 계획 v7).
--
-- 왜 필요한가
--   화면이 실제로 몇 초 걸리는지, 디자이너가 앱을 얼마나 여는지 아무도 몰랐다. 맥 점검(usage_probe)을 돌려야만
--   알 수 있어 계획이 멈췄다(v4~v6). 이제 앱이 폰에서 잰 시간을 남기고, 매일 감시(sync-health)가 숫자만 읽는다.
--
-- 담는 것 — 손님 정보는 담지 않는다
--   ops_events.kind = 'timing' : 화면 경로(손님 id 는 ':id'), 걸린 밀리초, 받아 둔 화면이었나, 앱을 처음 연 것인가.
--                                앱이 남긴다(api/client-timing). 읽기는 아래 함수로 숫자만.
--   store_stats                : 매장 통계를 수집 기준일마다 한 번 계산해 둔 것 — 지금은 '추천 시술' 근거
--                                (시술 갈래끼리 함께 받은 손님 수). 이름 · 번호 없음. v7 P1 이 쓴다.
--
-- 다시 돌려도 안전하다(if exists / or replace).

-- 1) 기록 종류에 '속도'
alter table public.ops_events drop constraint if exists ops_events_kind_check;
alter table public.ops_events add constraint ops_events_kind_check check (kind in ('backup', 'error', 'timing'));

-- 앱(로그인한 디자이너)은 자기 매장의 '오류'와 '속도'만 남길 수 있고, 읽지는 못한다.
drop policy if exists ops_events_insert_error on public.ops_events;
drop policy if exists ops_events_insert_app on public.ops_events;
create policy ops_events_insert_app on public.ops_events
  for insert to authenticated
  with check (kind in ('error', 'timing') and tenant_id in (select public.current_tenant_ids()));

-- 2) 감시자용 — 화면별 속도(지난 7일, 매장 구분 없이). 받아 둔 화면을 바로 보여준 것(instant)은 따로 세고
--    보통(p50) · 느린 때(p90)에서는 뺀다 — 섞으면 서버가 느린 것이 가려진다.
create or replace function public.ops_speed()
returns table (
  screen  text,
  opened  bigint,
  p50_ms  integer,
  p90_ms  integer,
  instant bigint
)
language sql
stable
security definer
set search_path = public
as $$
  select
    case when coalesce((e.detail->>'first')::boolean, false)
         then (e.detail->>'path') || ' (앱 열기)' else e.detail->>'path' end                         as screen,
    count(*)                                                                                        as opened,
    (percentile_cont(0.5) within group (order by (e.detail->>'ms')::int)
       filter (where not coalesce((e.detail->>'cached')::boolean, false)))::int                     as p50_ms,
    (percentile_cont(0.9) within group (order by (e.detail->>'ms')::int)
       filter (where not coalesce((e.detail->>'cached')::boolean, false)))::int                     as p90_ms,
    count(*) filter (where coalesce((e.detail->>'cached')::boolean, false))                         as instant
  from public.ops_events e
  where e.kind = 'timing' and e.created_at > now() - interval '7 days'
  group by 1
  order by 2 desc
$$;

-- 감시자용 — 매장별 사용 수(지난 7일): 화면 연 수 · 연락한 손님 수 · 마지막으로 앱을 쓴 때. 숫자만.
create or replace function public.ops_usage()
returns table (
  slug        text,
  screens_7d  bigint,
  contacts_7d bigint,
  last_seen   timestamptz
)
language sql
stable
security definer
set search_path = public
as $$
  select
    t.slug,
    (select count(*) from public.ops_events e
      where e.tenant_id = t.id and e.kind = 'timing' and e.created_at > now() - interval '7 days'),
    (select count(distinct c.customer_id) from public.care_items c
      where c.tenant_id = t.id and c.kind = 'contact' and c.sent_at > now() - interval '7 days'),
    (select max(e.created_at) from public.ops_events e
      where e.tenant_id = t.id and e.kind = 'timing')
  from public.tenants t
  order by t.slug
$$;

revoke all on function public.ops_speed() from public;
revoke all on function public.ops_usage() from public;
grant execute on function public.ops_speed() to anon, authenticated;
grant execute on function public.ops_usage() to anon, authenticated;

comment on function public.ops_speed() is
  '화면별 걸린 시간(지난 7일, 보통 · 느린 때) — 경로와 숫자만. 외부 감시자용 — 0024 참조.';
comment on function public.ops_usage() is
  '매장별 화면 연 수 · 연락한 손님 수(지난 7일) · 마지막 사용 — 숫자만. 외부 감시자용 — 0024 참조.';

-- 3) 매장 통계 저장 — 수집 기준일(as_of)마다 한 번 계산해 두고 화면들이 읽는다(v7 P1).
create table if not exists public.store_stats (
  tenant_id  uuid not null references public.tenants(id) on delete cascade,
  kind       text not null check (kind in ('pairs')),
  as_of      date not null,
  data       jsonb not null,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, kind)
);

alter table public.store_stats enable row level security;

drop policy if exists store_stats_rw on public.store_stats;
create policy store_stats_rw on public.store_stats
  using (tenant_id in (select public.current_tenant_ids()))
  with check (tenant_id in (select public.current_tenant_ids()));

comment on table public.store_stats is
  '매장 통계 미리 계산(수집 기준일마다 한 번) — 추천 시술 근거 등. 손님 이름 · 번호 없음. 0024 참조.';
