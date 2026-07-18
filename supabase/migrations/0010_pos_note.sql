-- 매장 메모(pos_note): HandSOS 매출 담당메모(saleStrMemoList)를 고객별로 모은 것. 읽기전용 미러
--   — 앱에서 직접 쓰는 customers.memo(0007)와 분리. 수집 때마다 HandSOS 기준으로 갱신된다.
-- 예약 메모(bookings.note): 예약 상세의 개별 메모(요청·시간변경·취소사유 등, 네이버 보일러플레이트 제거).
alter table customers add column if not exists pos_note text;
alter table bookings  add column if not exists note text;
