-- 방문 시각(HH:MM). HandSOS 매출목록의 날짜 셀에 시간이 함께 오는데 그동안 날짜만 잘라 쓰고 있었다.
-- 방문 관리 화면에서 '몇 시에 다녀가셨는지' 보여주기 위해 저장한다.
alter table transactions add column if not exists time text;
