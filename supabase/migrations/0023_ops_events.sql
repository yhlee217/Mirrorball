-- 0023: 운영 기록 — 주 1회 백업 시각과 화면 오류(개선 계획 v5 P1 · P2).
--
-- 왜 필요한가
--   백업(worker/backup.py)은 맥에서 돈다. 맥 밖의 감시자(GitHub Actions sync-health)가 '이번 주 백업이
--   됐나'를 알 길이 없었다 — 수집 지연과 같은 문제다. 화면 오류도 디자이너가 말해주기 전엔 아무도 몰랐다.
--   sync_jobs 에 섞으면 sync_health() 의 '마지막 수집'이 백업 시각으로 오염된다 → 따로 둔다.
--
-- 담는 것 — 손님 정보는 담지 않는다
--   backup : 매장별 백업 건수(손님 기록 · 사비 표시 · 연락 수). 워커(service_role)가 남긴다.
--   error  : 오류가 난 화면 경로(손님·예약 id 는 ':id' 로 지움)와 Next 오류 번호(digest). 앱이 남긴다.

create table if not exists public.ops_events (
  id         bigint generated always as identity primary key,
  tenant_id  uuid references public.tenants(id) on delete cascade,
  kind       text not null check (kind in ('backup', 'error')),
  detail     jsonb,
  created_at timestamptz not null default now()
);

create index if not exists ops_events_kind_time on public.ops_events (kind, created_at desc);

alter table public.ops_events enable row level security;

-- 로그인한 디자이너는 자기 매장의 '오류'만 남길 수 있고, 읽지는 못한다(읽기는 아래 함수로 건수만).
drop policy if exists ops_events_insert_error on public.ops_events;
create policy ops_events_insert_error on public.ops_events
  for insert to authenticated
  with check (kind = 'error' and tenant_id in (select public.current_tenant_ids()));

-- 감시자용 — 매장별 마지막 백업 시각과 지난 24시간 오류 수만(sync_health 와 같은 방식, anon 키로 충분).
create or replace function public.ops_health()
returns table (
  slug        text,
  last_backup timestamptz,
  errors_24h  bigint
)
language sql
stable
security definer
set search_path = public
as $$
  select
    t.slug,
    max(e.created_at) filter (where e.kind = 'backup')                                         as last_backup,
    count(e.id) filter (where e.kind = 'error' and e.created_at > now() - interval '24 hours') as errors_24h
  from public.tenants t
  left join public.ops_events e on e.tenant_id = t.id
  group by t.slug
$$;

revoke all on function public.ops_health() from public;
grant execute on function public.ops_health() to anon, authenticated;

comment on function public.ops_health() is
  '매장별 마지막 백업 시각과 지난 24시간 화면 오류 수만 노출(고객 정보 없음). 외부 감시자용 — 0023 참조.';
