-- 테넌트별 판정 기준 등 설정(JSON). 홈·필터·통계가 이 값으로 VIP·이탈 등을 판정.
alter table tenants add column if not exists settings jsonb not null default '{}'::jsonb;
