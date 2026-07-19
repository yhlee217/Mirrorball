-- 예약 상태(예약중·고객취소·매장취소·예약대기 등). 취소된 건도 수집해 화면에 '취소됨'으로 보여주기 위함
-- (그 시간이 비었다는 걸 디자이너가 알아야 한다). '방문완료'는 지난 건이라 수집 단계에서 제외한다.
alter table bookings add column if not exists status text;
