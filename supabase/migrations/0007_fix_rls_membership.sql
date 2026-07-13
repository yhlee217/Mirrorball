-- 0007 · RLS 격리 붕괴 수정 (코드리뷰 CRITICAL C1)
--
-- 문제: 0001 의 두 정책이 결합해 '아무 인증 사용자나 남의 테넌트에 가입 → 전 데이터 장악' 이 가능했다.
--   (1) membership_self 가 FOR ALL 이고 with check 가 없어 INSERT 검증에 using 식이 재사용됨.
--       조건이 `user_id = auth.uid()` 뿐이라 tenant_id 무제약 → 사용자가 임의 tenant_id 로
--       자기 멤버십을 self-insert 할 수 있다(멤버십은 온보딩 service_role 로만 만들어야 함).
--   (2) profile_public_read 가 published 프로필 행을 anon 에게 통째 노출 → PK 인 tenant_id 유출.
--       공격자는 이걸로 피해 테넌트 id 를 수집해 (1) 로 가입한다.
-- 익스플로잇: 셀프가입 → GET /profiles?select=tenant_id&published=eq.true → POST /memberships
--   {tenant_id:피해자,user_id:자신} → current_tenant_ids() 에 피해자 포함 → customers/transactions/
--   bookings/settings 읽기·쓰기·삭제.
--
-- 수정 원칙:
--   · 멤버십 생성/변경은 오직 service_role(온보딩)만. 사용자에겐 '자기 멤버십 조회'만 허용.
--   · 공개 소개 페이지는 이미 service_role 로 읽으므로(web/app/p/[slug]/page.tsx) anon 의
--     profiles 직접 read 정책은 불필요 → 제거해 tenant_id 유출 경로를 닫는다.

-- (1) memberships: FOR ALL → FOR SELECT (self-insert/update/delete 차단)
drop policy if exists membership_self on memberships;
create policy membership_self on memberships
  for select using (user_id = auth.uid());

-- (2) profiles: anon 공개 read 정책 제거(공개 페이지는 service_role 경유).
--     소유자 read/write 는 profile_owner 정책이 계속 담당한다(변경 없음).
drop policy if exists profile_public_read on profiles;
