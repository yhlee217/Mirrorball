-- 0029: 챙길 고객 펼침 수 · 앱 첫 열기 서버 시간(개선 계획 v16 P1 · P2).
--
-- 왜 필요한가
--   P1 — 연락이 감시에 잡힌 10.08~26 내내 0이다. 챙길 고객 화면은 주 3~12번 여는데, 줄을 펼쳐 보기는 하는지 모른다
--        (기록은 '연락함'뿐). 펼친 수를 숫자로만 센다 — 펼침도 0이면 목록 · 알림 쪽, 펼치는데 연락이 0이면 보내는 길 쪽.
--   P2 — 앱 첫 열기 느린 때가 2.7~2.9초(10.19~26)인데 어디서 걸리는지 모른다. 서버가 첫 바이트를 보낸 시각을 함께 받아
--        서버(로그인 확인 · 첫 화면 데이터)와 화면 그리기를 가른다.
--
-- 담는 것 — 손님 정보는 담지 않는다
--   ops_events.kind = 'care'          {step: 'open', op, app} — 어느 손님인지는 없다(api/care-event, web/lib/ops cleanCare)
--   ops_events.kind = 'timing' detail.server   앱 첫 열기 때만 — 서버 첫 바이트(ms, 브라우저가 이미 잰 값)
--   ops_usage(p_key)  care_opens_7d 칸을 더한다 — 디자이너가 펼친 수(운영자 폰은 뺀다)
--   ops_speed(p_key)  server_p50_ms · server_p90_ms 칸을 더한다 — 앱 첫 열기 줄에만(다른 줄은 null)
--   나머지 칸 · 세는 법 · 문(0027 — 운영자 계정이나 감시 열쇠)은 그대로다.
--
-- 실행 순서 — 0027 · 0028 다음(playbook/OPERATIONS_APP.md §4, 셋을 번호 순서로 한 번에). 0027 이 없으면 멈춘다.
-- 다시 돌려도 안전하다(if exists · drop … if exists).

do $$
begin
  if to_regprocedure('public.ops_allowed(text)') is null then
    raise exception '0029: 0027_ops_lock.sql 을 먼저 실행하세요(운영 숫자 문단속)';
  end if;
end $$;

alter table public.ops_events drop constraint if exists ops_events_kind_check;
alter table public.ops_events add constraint ops_events_kind_check
  check (kind in ('backup', 'error', 'timing', 'csp', 'care'));

-- 앱(로그인한 디자이너)은 자기 매장의 '오류' · '속도' · 'CSP' · '펼침'만 남길 수 있고, 읽지는 못한다.
drop policy if exists ops_events_insert_app on public.ops_events;
create policy ops_events_insert_app on public.ops_events
  for insert to authenticated
  with check (kind in ('error', 'timing', 'csp', 'care') and tenant_id in (select public.current_tenant_ids()));

-- 돌려주는 칸이 늘어 모양이 바뀐다 — or replace 로는 못 바꿔서 지우고 다시 만든다.
drop function if exists public.ops_speed(text);
drop function if exists public.ops_usage(text);

create function public.ops_speed(p_key text default null)
returns table (
  screen        text,
  opened        bigint,
  p50_ms        integer,
  p90_ms        integer,
  instant       bigint,
  server_p50_ms integer,
  server_p90_ms integer
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
    count(*) filter (where coalesce((e.detail->>'cached')::boolean, false)),
    (percentile_cont(0.5) within group (order by (e.detail->>'server')::int)
       filter (where e.detail ? 'server'))::int,
    (percentile_cont(0.9) within group (order by (e.detail->>'server')::int)
       filter (where e.detail ? 'server'))::int
  from public.ops_events e
  where e.kind = 'timing' and e.created_at > now() - interval '7 days'
  group by 1
  order by 2 desc;
end
$$;

create function public.ops_usage(p_key text default null)
returns table (
  slug          text,
  screens_7d    bigint,
  app_7d        bigint,
  op_7d         bigint,
  contacts_7d   bigint,
  last_seen     timestamptz,
  since         timestamptz,
  care_opens_7d bigint
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
    (select min(m.created_at) from marked m),
    (select count(*) from public.ops_events o
      where o.tenant_id = t.id and o.kind = 'care' and not coalesce((o.detail->>'op')::boolean, false)
        and o.created_at > now() - interval '7 days')
  from public.tenants t
  order by t.slug;
end
$$;

-- 함수 자체는 공개 키로도 부를 수 있다 — 들어가자마자 운영자 계정 · 감시 열쇠를 확인한다(0027 과 같다).
revoke all on function public.ops_speed(text) from public;
revoke all on function public.ops_usage(text) from public;
grant execute on function public.ops_speed(text) to anon, authenticated;
grant execute on function public.ops_usage(text) to anon, authenticated;

comment on function public.ops_speed(text) is
  '화면별 속도(지난 7일) + 앱 첫 열기 서버 첫 바이트 — 운영자 계정 · 감시 열쇠만(0027). 0024 · 0029 참조.';
comment on function public.ops_usage(text) is
  '매장별 디자이너 사용 · 챙길 고객 펼침 · 연락 수(지난 7일) — 운영자 계정 · 감시 열쇠만(0027). 0025 · 0029 참조.';
