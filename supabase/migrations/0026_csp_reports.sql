-- 0026: 콘텐츠 보안 정책(CSP) 어긋남 기록(개선 계획 v14 P0).
--
-- 왜 필요한가
--   보안 응답 헤더를 넣으면서 CSP 전체는 한 주 '보고만'(Report-Only)으로 건다 — 막으면 어긋나는 게 있을 때 화면이 깨진다.
--   어긋남을 남길 곳이 필요한데, '화면 오류'(kind 'error')에 섞으면 매일 감시의 오류 기준(24시간 5건)이 거짓으로 넘는다
--   → 종류를 따로 둔다.
--
-- 담는 것 — 손님 정보는 담지 않는다
--   ops_events.kind = 'csp' : 어긋난 규칙(script-src 등) · 막힐 뻔한 것의 출처(https://host 또는 inline · data …) ·
--                             화면 경로(손님 id 는 ':id'). 앱이 남긴다(api/csp-report, web/lib/ops cleanCsp).
--   ops_csp()               : 감시자용 — 지난 7일 규칙 · 출처별 건수(숫자와 출처만).
--
-- 다시 돌려도 안전하다(if exists / or replace).

alter table public.ops_events drop constraint if exists ops_events_kind_check;
alter table public.ops_events add constraint ops_events_kind_check check (kind in ('backup', 'error', 'timing', 'csp'));

-- 앱(로그인한 디자이너)은 자기 매장의 '오류' · '속도' · 'CSP' 만 남길 수 있고, 읽지는 못한다.
drop policy if exists ops_events_insert_app on public.ops_events;
create policy ops_events_insert_app on public.ops_events
  for insert to authenticated
  with check (kind in ('error', 'timing', 'csp') and tenant_id in (select public.current_tenant_ids()));

create or replace function public.ops_csp()
returns table (
  directive text,
  blocked   text,
  n         bigint,
  last_at   timestamptz
)
language sql
stable
security definer
set search_path = public
as $$
  select e.detail->>'directive', e.detail->>'blocked', count(*), max(e.created_at)
  from public.ops_events e
  where e.kind = 'csp' and e.created_at > now() - interval '7 days'
  group by 1, 2
  order by 3 desc
  limit 20
$$;

revoke all on function public.ops_csp() from public;
grant execute on function public.ops_csp() to anon, authenticated;

comment on function public.ops_csp() is
  'CSP(보고만) 어긋남 — 지난 7일 규칙 · 출처별 건수. 출처와 숫자만(손님 정보 없음). 외부 감시자용 — 0026 참조.';
