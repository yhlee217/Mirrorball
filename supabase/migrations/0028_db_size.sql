-- 0028: DB 용량 — 무료 한도(500MB)에 다가가면 미리 알기(2026-10-17 운영자 질문).
--
-- 왜 필요한가
--   Supabase 무료 플랜은 DB 가 500MB 를 넘으면 프로젝트가 읽기 전용이 된다(쓰기가 25006 오류 — Supabase 문서
--   'Understanding Database and Disk Size'). 그러면 앱의 연락 기록 · 메모 저장, 일요일 수집 · 백업이 모두 막힌다.
--   그런데 매일 감시는 용량을 보지 않아서 수집이 8일 밀린 뒤에야 알았다. 용량을 매일 보고, 400MB(80%)를 넘으면
--   감시가 빨갛게 끝나 메일이 간다(scripts/sync_health_check.py — 기준은 DB_LIMIT_MB · DB_WARN_MB).
--
-- 담는 것 — 숫자와 표 이름만(손님 정보 없음)
--   ops_db_size(p_key)  'total'(pg_database_size) 한 줄 + public 표 가운데 큰 다섯(인덱스 · TOAST 포함 크기).
--   0027 과 같은 문 — 운영자 계정이거나 감시 열쇠일 때만. 그래서 0027 을 먼저 실행한다.
--
-- 다시 돌려도 안전하다(or replace).

create or replace function public.ops_db_size(p_key text default null)
returns table (
  part  text,
  bytes bigint
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
  select 'total'::text, pg_database_size(current_database())::bigint
  union all
  (select c.relname::text, pg_total_relation_size(c.oid)::bigint
     from pg_class c
     join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'r'
    order by 2 desc
    limit 5);
end
$$;

revoke all on function public.ops_db_size(text) from public;
grant execute on function public.ops_db_size(text) to anon, authenticated;

comment on function public.ops_db_size(text) is
  'DB 용량 — 전체 · 큰 표 다섯(바이트). 숫자와 표 이름만. 운영자 계정 · 감시 열쇠만(0027 의 문). 0028 참조.';
