-- 가족 관계: HandSOS 가족고객 현황(c_Family.asp)의 가족번호(6자리).
-- 같은 tenant 내에서 동일 family_ext_id 를 가진 고객끼리 가족. 담당(디자이너)이 다른 가족원은
-- 다른 tenant 에 있어 서로 안 보인다(멀티테넌트 격리 유지) — 각 디자이너는 '자기 고객인 가족원'만 본다.
alter table customers add column if not exists family_ext_id text;
create index if not exists idx_customers_family
  on customers(tenant_id, family_ext_id) where family_ext_id is not null;
