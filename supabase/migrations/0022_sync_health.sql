-- 0022: 수집 건강 상태 조회 — 맥 밖에서 '수집이 멈췄는지' 확인하는 최소 창구.
--
-- 왜 필요한가
--   수집이 조용히 멈춘 걸 두 번 당했다.
--     2026-08  프리플라이트가 로그 파일에만 외쳤다
--     2026-09~10  크로미움이 사라져 일요일 5번이 전부 죽었다 (5주치 공백)
--   둘 다 '맥 안에서만 알 수 있는 사실'이었다. 맥이 꺼져 있거나 알림을 놓치면 아무도 모른다.
--   그래서 맥과 무관한 감시자(GitHub Actions)가 매일 확인하게 한다.
--
-- 왜 함수로 여는가
--   sync_jobs 는 RLS(tenant_rw)로 막혀 있어 로그인 없이는 못 읽는다. 감시자에게
--   service_role 키를 주면 전 테넌트의 고객 PII 까지 열린다 — 타임스탬프 하나 보려고
--   그럴 수는 없다. 그래서 '마지막 수집 시각'만 돌려주는 security definer 함수를 열고,
--   그 이상은 구조적으로 못 보게 한다.
--
-- 공개되는 정보
--   테넌트 slug(이미 /p/<slug> 공개 소개 페이지로 노출됨) + 수집 시각. 고객 정보 없음.
--   error 본문은 내부 URL·응답이 섞일 수 있어 일부러 돌려주지 않는다.

create or replace function public.sync_health()
returns table (
  slug         text,
  last_ok      timestamptz,
  last_attempt timestamptz,
  days_since   numeric
)
language sql
stable
security definer
set search_path = public
as $$
  select
    t.slug,
    max(j.finished_at) filter (where j.status = 'ok') as last_ok,
    max(j.finished_at)                               as last_attempt,
    extract(epoch from (
      now() - max(j.finished_at) filter (where j.status = 'ok')
    )) / 86400                                       as days_since
  from sync_jobs j
  join tenants t on t.id = j.tenant_id
  group by t.slug
$$;

-- create function 은 기본으로 PUBLIC 에 EXECUTE 를 준다 → 명시적으로 좁힌다.
revoke all on function public.sync_health() from public;
grant execute on function public.sync_health() to anon, authenticated;

comment on function public.sync_health() is
  '수집 마지막 성공/시도 시각만 노출(고객 정보 없음). 외부 감시자용 — 0022 참조.';
