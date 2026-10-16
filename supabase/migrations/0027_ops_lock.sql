-- 0027: 운영 숫자 문단속 — 공개 키로는 안 보이게(개선 계획 v15 P2).
--
-- 왜 필요한가
--   운영 숫자 함수 다섯(sync_health · ops_health · ops_speed · ops_usage · ops_csp)은 매일 감시(GitHub Actions)가 서비스 키
--   없이 부르도록 공개 키(anon)에 열어 두었다(0022~0026). 공개 키는 앱 화면 코드에 들어 있고 저장소도 공개라, 누구나
--   매장 이름표 · 매장별 화면 수 · 연락한 손님 수 · 마지막 사용 · 수집 · 백업 시각을 받아 갈 수 있었다(손님 정보는 없다).
--   /ops 화면도 누구나 켤 수 있는 쿠키(?op=1)로만 가려져 있었다.
--
-- 바뀌는 것
--   다섯 함수가 p_key 를 받고, '운영자 계정'(ops_readers)이거나 '감시 열쇠'(ops_watch_keys 의 해시와 맞음)일 때만 숫자를
--   준다 — 아니면 오류(42501). 인자 없는 옛 함수는 지운다(남겨 두면 그대로 열려 있다). 돌려주는 칸 · 세는 법은 그대로.
--     ops_new_watch_key()       감시 열쇠를 새로 만들어 한 번만 보여 준다(DB 엔 sha256 해시만) → GitHub 비밀값 OPS_WATCH_KEY
--     ops_add_reader('이메일')   그 계정을 운영 숫자 읽는 사람으로 — 앱의 /ops 는 이 계정일 때만 열린다
--     ops_is_reader()           지금 로그인한 계정이 운영자인가(앱이 /ops · 설정의 '운영 숫자' 버튼을 가릴 때)
--   앞의 둘은 SQL Editor(관리자)에서만 부른다 — 앱 · 공개 키로는 못 부른다.
--
-- 실행 순서(운영자 — playbook/OPERATIONS_APP.md §4)
--   1) 이 파일   2) select public.ops_new_watch_key();  → 나온 값을 GitHub → Settings → Secrets → OPS_WATCH_KEY
--   3) select public.ops_add_reader('운영자 이메일');
--   1) 뒤 2) 를 빠뜨리면 다음 매일 감시가 '감시 열쇠'로 빨갛게 끝난다(조용히 넘어가지 않게).
--
-- 다시 돌려도 안전하다(if not exists · drop if exists · or replace). 감시 열쇠를 다시 만들면 앞의 열쇠는 못 쓴다.

create table if not exists public.ops_readers (
  user_id  uuid primary key references auth.users (id) on delete cascade,
  added_at timestamptz not null default now()
);

create table if not exists public.ops_watch_keys (
  hash       text primary key,
  created_at timestamptz not null default now()
);

-- 정책을 두지 않는다 — API(공개 키 · 로그인한 계정)로는 읽지도 쓰지도 못한다. 아래 함수만 들여다본다.
alter table public.ops_readers enable row level security;
alter table public.ops_watch_keys enable row level security;
revoke all on public.ops_readers from anon, authenticated;
revoke all on public.ops_watch_keys from anon, authenticated;

create or replace function public.ops_allowed(p_key text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (select 1 from public.ops_readers r where r.user_id = auth.uid())
      or (coalesce(length(p_key), 0) >= 32 and exists (
            select 1 from public.ops_watch_keys k
            where k.hash = encode(sha256(convert_to(p_key, 'UTF8')), 'hex')))
$$;

revoke all on function public.ops_allowed(text) from public, anon, authenticated;

create or replace function public.ops_is_reader()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (select 1 from public.ops_readers r where r.user_id = auth.uid())
$$;

revoke all on function public.ops_is_reader() from public, anon;
grant execute on function public.ops_is_reader() to authenticated;

create or replace function public.ops_new_watch_key()
returns text
language plpgsql
volatile
security definer
set search_path = public
as $$
declare
  k text := replace(gen_random_uuid()::text, '-', '') || replace(gen_random_uuid()::text, '-', '');
begin
  delete from public.ops_watch_keys where true;
  insert into public.ops_watch_keys (hash) values (encode(sha256(convert_to(k, 'UTF8')), 'hex'));
  return k;
end
$$;

revoke all on function public.ops_new_watch_key() from public, anon, authenticated;

create or replace function public.ops_add_reader(p_email text)
returns text
language plpgsql
volatile
security definer
set search_path = public
as $$
declare
  uid uuid;
begin
  select u.id into uid from auth.users u where lower(u.email) = lower(trim(p_email));
  if uid is null then
    raise exception '그 이메일의 계정이 없다 — 앱에 한 번 로그인하거나 worker/login_code.py 로 먼저 만든다';
  end if;
  insert into public.ops_readers (user_id) values (uid) on conflict do nothing;
  return '운영 숫자를 읽는 계정이 됐다: ' || lower(trim(p_email));
end
$$;

revoke all on function public.ops_add_reader(text) from public, anon, authenticated;

-- 다섯 함수 — 인자 없는 옛 함수를 지우고 p_key 를 받는 함수로. 몸통은 0022 · 0023 · 0024 · 0025 · 0026 과 같다.
drop function if exists public.sync_health();
drop function if exists public.ops_health();
drop function if exists public.ops_speed();
drop function if exists public.ops_usage();
drop function if exists public.ops_csp();

create or replace function public.sync_health(p_key text default null)
returns table (
  slug         text,
  last_ok      timestamptz,
  last_attempt timestamptz,
  days_since   numeric
)
language plpgsql
stable
security definer
set search_path = public
as $$
#variable_conflict use_column
begin
  if not public.ops_allowed(p_key) then
    raise exception 'ops: 운영자 계정이나 감시 열쇠가 필요하다' using errcode = '42501';
  end if;
  return query
  select
    t.slug,
    max(j.finished_at) filter (where j.status = 'ok'),
    max(j.finished_at),
    (extract(epoch from (now() - max(j.finished_at) filter (where j.status = 'ok'))) / 86400)::numeric
  from public.sync_jobs j
  join public.tenants t on t.id = j.tenant_id
  group by t.slug;
end
$$;

create or replace function public.ops_health(p_key text default null)
returns table (
  slug        text,
  last_backup timestamptz,
  errors_24h  bigint
)
language plpgsql
stable
security definer
set search_path = public
as $$
#variable_conflict use_column
begin
  if not public.ops_allowed(p_key) then
    raise exception 'ops: 운영자 계정이나 감시 열쇠가 필요하다' using errcode = '42501';
  end if;
  return query
  select
    t.slug,
    max(e.created_at) filter (where e.kind = 'backup'),
    count(e.id) filter (where e.kind = 'error' and e.created_at > now() - interval '24 hours')
  from public.tenants t
  left join public.ops_events e on e.tenant_id = t.id
  group by t.slug;
end
$$;

create or replace function public.ops_speed(p_key text default null)
returns table (
  screen  text,
  opened  bigint,
  p50_ms  integer,
  p90_ms  integer,
  instant bigint
)
language plpgsql
stable
security definer
set search_path = public
as $$
#variable_conflict use_column
begin
  if not public.ops_allowed(p_key) then
    raise exception 'ops: 운영자 계정이나 감시 열쇠가 필요하다' using errcode = '42501';
  end if;
  return query
  select
    case when coalesce((e.detail->>'first')::boolean, false)
         then (e.detail->>'path') || ' (앱 열기)' else e.detail->>'path' end,
    count(*),
    (percentile_cont(0.5) within group (order by (e.detail->>'ms')::int)
       filter (where not coalesce((e.detail->>'cached')::boolean, false)))::int,
    (percentile_cont(0.9) within group (order by (e.detail->>'ms')::int)
       filter (where not coalesce((e.detail->>'cached')::boolean, false)))::int,
    count(*) filter (where coalesce((e.detail->>'cached')::boolean, false))
  from public.ops_events e
  where e.kind = 'timing' and e.created_at > now() - interval '7 days'
  group by 1
  order by 2 desc;
end
$$;

create or replace function public.ops_usage(p_key text default null)
returns table (
  slug        text,
  screens_7d  bigint,
  app_7d      bigint,
  op_7d       bigint,
  contacts_7d bigint,
  last_seen   timestamptz,
  since       timestamptz
)
language plpgsql
stable
security definer
set search_path = public
as $$
#variable_conflict use_column
begin
  if not public.ops_allowed(p_key) then
    raise exception 'ops: 운영자 계정이나 감시 열쇠가 필요하다' using errcode = '42501';
  end if;
  return query
  with marked as (
    select e.tenant_id,
           e.created_at,
           coalesce((e.detail->>'op')::boolean, false)  as is_op,
           coalesce((e.detail->>'app')::boolean, false) as is_app
    from public.ops_events e
    where e.kind = 'timing' and e.detail ? 'op'
  )
  select
    t.slug,
    (select count(*) from marked m
      where m.tenant_id = t.id and not m.is_op and m.created_at > now() - interval '7 days'),
    (select count(*) from marked m
      where m.tenant_id = t.id and not m.is_op and m.is_app and m.created_at > now() - interval '7 days'),
    (select count(*) from marked m
      where m.tenant_id = t.id and m.is_op and m.created_at > now() - interval '7 days'),
    (select count(distinct c.customer_id) from public.care_items c
      where c.tenant_id = t.id and c.kind = 'contact' and c.sent_at > now() - interval '7 days'),
    (select max(m.created_at) from marked m where m.tenant_id = t.id and not m.is_op),
    (select min(m.created_at) from marked m)
  from public.tenants t
  order by t.slug;
end
$$;

create or replace function public.ops_csp(p_key text default null)
returns table (
  directive text,
  blocked   text,
  n         bigint,
  last_at   timestamptz
)
language plpgsql
stable
security definer
set search_path = public
as $$
#variable_conflict use_column
begin
  if not public.ops_allowed(p_key) then
    raise exception 'ops: 운영자 계정이나 감시 열쇠가 필요하다' using errcode = '42501';
  end if;
  return query
  select e.detail->>'directive', e.detail->>'blocked', count(*), max(e.created_at)
  from public.ops_events e
  where e.kind = 'csp' and e.created_at > now() - interval '7 days'
  group by 1, 2
  order by 3 desc
  limit 20;
end
$$;

-- 함수 자체는 공개 키로도 부를 수 있다 — 들어가자마자 운영자 계정 · 감시 열쇠를 확인한다.
revoke all on function public.sync_health(text) from public;
revoke all on function public.ops_health(text) from public;
revoke all on function public.ops_speed(text) from public;
revoke all on function public.ops_usage(text) from public;
revoke all on function public.ops_csp(text) from public;
grant execute on function public.sync_health(text) to anon, authenticated;
grant execute on function public.ops_health(text) to anon, authenticated;
grant execute on function public.ops_speed(text) to anon, authenticated;
grant execute on function public.ops_usage(text) to anon, authenticated;
grant execute on function public.ops_csp(text) to anon, authenticated;

comment on function public.sync_health(text) is '수집 마지막 성공/시도 시각 — 운영자 계정 · 감시 열쇠만(0027). 0022 참조.';
comment on function public.ops_health(text) is '매장별 마지막 백업 · 지난 24시간 화면 오류 수 — 운영자 계정 · 감시 열쇠만(0027). 0023 참조.';
comment on function public.ops_speed(text) is '화면별 속도(지난 7일) — 운영자 계정 · 감시 열쇠만(0027). 0024 참조.';
comment on function public.ops_usage(text) is '매장별 디자이너 사용 · 연락 수(지난 7일) — 운영자 계정 · 감시 열쇠만(0027). 0025 참조.';
comment on function public.ops_csp(text) is 'CSP 어긋남(지난 7일) — 운영자 계정 · 감시 열쇠만(0027). 0026 참조.';
