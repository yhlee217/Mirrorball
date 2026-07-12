-- 인사말·표시에 쓸 디자이너 이름(비-PII, 공개성 낮음)을 테넌트에 추가.
alter table tenants add column if not exists designer_name text;
