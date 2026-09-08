-- 시술명으로 추정한 고객 성별·연령대.
--
-- HandSOS 메뉴에 '남자컷/여자컷/주니어컷'이 박혀 있어 단서가 된다. 실측(3개 테넌트)에서
-- 시술 거래의 65~73%에 단서가 있었고 고객의 74~78%가 판정됐다. 대행결제로 남·여가
-- 섞여 판정 불가인 고객은 1~5%에 그쳤다.
--
-- 매번 전 거래를 훑어 계산할 수 없으니(통계 화면이 느려진다) 워커가 미리 넣는다.
-- 판정 규칙은 worker/gender.py 한 곳에 있다.
--
--   gender      'M' | 'F' | null(모름·대행)
--   age_band    'kid'(본인이 아동·학생) | 'adult' | null
--   gender_src  'service' | 'memo-family' | 'memo-spouse' — 무엇으로 갈랐는지(신뢰도 구분용)
alter table customers add column if not exists gender     text;
alter table customers add column if not exists age_band   text;
alter table customers add column if not exists gender_src text;
