-- VIP 판정용 '최근 기간 방문 횟수'. 누적 방문(visit_count)만으로는 6년에 걸쳐 10번 오신 분과
-- 올해만 10번 오신 분이 같아진다 → 최근 활동량을 따로 센다.
-- 수집 때 _recompute_aggregates 가 전체 거래로 다시 계산하므로 앱은 읽기만 한다.
-- 창을 3개 고정으로 두고 설정(vip_recent_months)이 그중 하나를 고르는 방식 — 워커가
-- 테넌트 설정을 몰라도 되고, 설정을 바꿔도 재수집이 필요 없다.
alter table customers add column if not exists visits_90d int;
alter table customers add column if not exists visits_180d int;
alter table customers add column if not exists visits_365d int;
