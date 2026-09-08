-- 선불 충전을 시술과 분리한다.
--
-- 지금은 transactions 에 '30만원 충전'과 '10만원 커트'가 같은 행으로 섞여 있고 구분이 없다.
-- 그래서 total_won 이 둘을 다 더해 이중 계상된다 — 30만 충전 후 10만 시술 3회면 누적 60만으로
-- 보이지만 실제로 받은 돈은 30만이다. 방문 횟수도 '충전만 하고 간 날'을 1회로 세어
-- 재방문 주기·이탈 판정이 밀린다.
--
--   kind                — service | charge | product | refund
--   paid_out_of_pocket  — 충전 잔액이 아니라 사비로 결제했다고 사장님이 표시한 건
--
-- paid_out_of_pocket 은 사람이 넣는 값이라 수집이 덮으면 안 된다. 워커 업서트는
-- resolution=merge-duplicates 라 payload 에 없는 컬럼은 건드리지 않으므로,
-- 워커가 이 컬럼을 보내지 않는 한 유지된다.
alter table transactions add column if not exists kind text;
alter table transactions add column if not exists paid_out_of_pocket boolean;

-- 과거분 소급 분류. 시술명만 보고 판정할 수 있으므로 Postgres 안에서 한 번에 끝낸다
-- (5만 행을 API 로 왕복시키면 느리고 실패 지점만 늘어난다).
-- 판정 기준은 web/lib/service-name.ts 의 NOT_SERVICE 와 같은 어휘를 쓴다.
update transactions set kind = case
    when service ~ '환불'                                then 'refund'
    when service ~ '충전|선불|정액|상품권'                 then 'charge'
    when service ~ '제품|판매|펌제|약제|기장추가'           then 'product'
    else                                                      'service'
  end
  where kind is null;

alter table transactions alter column kind set default 'service';

-- 잔액·집계 계산이 고객별 시간순으로 훑으므로 그 순서에 맞춘 인덱스.
create index if not exists transactions_cust_date_idx
  on transactions (tenant_id, customer_id, date);

-- 추정 선불 잔액. 앱이 매번 전 거래를 훑어 계산하지 않도록 워커가 미리 넣는다
-- (방문수·매출과 같은 방식). 어디까지나 추정이라 화면에도 그렇게 표시한다.
alter table customers add column if not exists prepaid_balance integer not null default 0;

-- 이 거래 금액 중 선불 잔액으로 결제된 것으로 추정한 금액.
-- 실매출 = amount_won − covered_won 이라는 한 규칙으로 모든 화면이 계산할 수 있게 한다
-- (통계는 월별 합산이라 고객 단위 집계로는 안 된다).
alter table transactions add column if not exists covered_won integer not null default 0;
