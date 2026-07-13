-- 0008 · tenants 쓰기 잠금 (코드리뷰 M1)
--
-- 문제: 0001 의 tenant_self 가 FOR ALL 이라 멤버가 PostgREST 로 자기 테넌트 행의 임의 컬럼을
--   직접 수정 가능했다 — plan(과금 등급 상향), dek_wrapped(자기 PII 키 파괴), slug(공개 URL 변경).
--   RLS 는 컬럼을 못 막으므로 정책만으론 부족.
-- 수정: 멤버에겐 tenants '조회'만 허용(FOR SELECT). 설정 변경(salon_name/designer_name/settings)은
--   서버 API(/api/settings)가 service_role 로 대신 쓴다(민감 컬럼은 API 가 손대지 않음).
--   → 멤버의 tenants 직접 쓰기 경로 자체를 제거.

drop policy if exists tenant_self on tenants;
create policy tenant_self on tenants
  for select using (id in (select current_tenant_ids()));
