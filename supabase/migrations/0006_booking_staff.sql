-- 예약 담당 디자이너(표시 필터용). 수집은 전 디자이너 다 하고, 화면에서 담당별로 필터.
alter table bookings add column if not exists staff text;
