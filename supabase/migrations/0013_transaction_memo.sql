-- 방문별 매장 메모. HandSOS 매출목록의 메모(saleStrMemoList)는 '그 방문'에 적은 것이라
-- 거래 행에 붙여야 언제 적은 메모인지 알 수 있다(기존엔 고객 단위로 뭉쳐 날짜가 사라졌다).
-- customers.pos_note 는 최근 메모 요약(날짜순)으로 계속 유지한다.
alter table transactions add column if not exists memo text;
