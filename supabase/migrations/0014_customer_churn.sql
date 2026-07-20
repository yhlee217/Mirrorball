-- 디자이너가 직접 '이 고객은 이제 안 오신다'고 확정 표시하는 칸.
-- 자동 판정(revisit_state=overdue '이탈 위험')은 어디까지나 추정이라, 확실히 아는 건
-- 사람이다. 표시된 고객은 챙길 고객·홈 신호·알림에서 빠진다(데이터는 그대로 보존).
-- null = 활성 고객. 값이 있으면 그 시각에 표시한 것.
alter table customers add column if not exists churned_at timestamptz;

-- 홈·목록이 테넌트별로 '이탈 아닌 고객'을 자주 훑으므로 부분 인덱스를 둔다.
create index if not exists customers_active_idx on customers (tenant_id) where churned_at is null;
