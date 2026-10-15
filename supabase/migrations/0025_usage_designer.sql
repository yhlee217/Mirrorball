-- 0025: 사용 수는 디자이너 것만 — 운영자 폰 · 홈 화면 앱 · 기록 시작(개선 계획 v10 P0).
--
-- 왜 필요한가
--   0024 의 매장별 '화면 연 수'는 매장 단위로만 셌다. 운영자가 폰으로 확인한 화면도 그 계정이 가장 먼저 소속된 매장으로
--   들어가 디자이너 사용과 가를 수 없었다(2026-10-15 첫 숫자 — 하예원 47번, 대부분 운영자 확인). 그리고 출력은 '지난 7일'인데
--   기록은 0024 적용일부터라 '0번'이 며칠 기준인지 안 보였다.
--
-- 바뀌는 것 — 감시 함수 하나(표 · 정책 · ops_speed 는 그대로)
--   앱이 화면 기록에 두 칸을 늘 남긴다(web/lib/ops cleanTiming): op(운영자 폰 — 설정을 ?op=1 로 열어 그 폰에 표시) ·
--   app(홈 화면 앱으로 열었나). ops_usage() 는 매장별
--     screens_7d  디자이너가 연 화면(운영자 폰 뺌)        app_7d   그중 홈 화면 앱으로 연 것
--     op_7d       운영자 폰 화면(따로)                    contacts_7d · last_seen(디자이너) — 0024 와 같은 뜻
--     since       기록 시작(두 칸을 남기기 시작한 때 — 모든 매장 같은 값)
--   두 칸이 없는 예전 기록(0025 전 앱)은 사용 수에 세지 않는다 — 누구 것인지 모른다. 화면 속도(ops_speed)는 모두 센다 —
--   운영자 폰도 같은 앱, 같은 속도다.
--
-- 다시 돌려도 안전하다(drop if exists → create). 돌려주는 칸이 바뀌어 create or replace 로는 안 된다.

drop function if exists public.ops_usage();

create function public.ops_usage()
returns table (
  slug        text,
  screens_7d  bigint,
  app_7d      bigint,
  op_7d       bigint,
  contacts_7d bigint,
  last_seen   timestamptz,
  since       timestamptz
)
language sql
stable
security definer
set search_path = public
as $$
  with marked as (
    select e.tenant_id,
           e.created_at,
           coalesce((e.detail->>'op')::boolean, false)  as op,
           coalesce((e.detail->>'app')::boolean, false) as app
    from public.ops_events e
    where e.kind = 'timing' and e.detail ? 'op'
  )
  select
    t.slug,
    (select count(*) from marked m
      where m.tenant_id = t.id and not m.op and m.created_at > now() - interval '7 days'),
    (select count(*) from marked m
      where m.tenant_id = t.id and not m.op and m.app and m.created_at > now() - interval '7 days'),
    (select count(*) from marked m
      where m.tenant_id = t.id and m.op and m.created_at > now() - interval '7 days'),
    (select count(distinct c.customer_id) from public.care_items c
      where c.tenant_id = t.id and c.kind = 'contact' and c.sent_at > now() - interval '7 days'),
    (select max(m.created_at) from marked m where m.tenant_id = t.id and not m.op),
    (select min(m.created_at) from marked m)
  from public.tenants t
  order by t.slug
$$;

revoke all on function public.ops_usage() from public;
grant execute on function public.ops_usage() to anon, authenticated;

comment on function public.ops_usage() is
  '매장별 디자이너 화면 수 · 그중 앱으로 연 수 · 운영자 폰 화면 수 · 연락한 손님 수(지난 7일) · 마지막 사용 · 기록 시작 — 숫자만. 외부 감시자용 — 0025 참조.';
