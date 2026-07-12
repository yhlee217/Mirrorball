-- 예약자 이름/전화(암호화) — 고객 매칭 여부와 무관하게 '다가오는 예약'에 이름 표시.
-- 예약행엔 고객번호가 없어 항상 연결되진 않으므로, 예약 자체에 예약자 PII를 봉투암호화로 보관.
alter table bookings add column if not exists pii_enc text;
