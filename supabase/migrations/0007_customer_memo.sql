-- 고객 메모(모발 상태·선호·주의사항 등). prefer_tags(text[])는 이미 존재.
alter table customers add column if not exists memo text;
