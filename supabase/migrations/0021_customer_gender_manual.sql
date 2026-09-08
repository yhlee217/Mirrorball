-- 사람이 직접 지정한 성별.
--
-- 시술명 추정은 데이터의 한계로 약 22% 가 미상이다(다운펌·앞머리컷처럼 메뉴에 성별이 없는
-- 시술만 받은 고객). 디자이너는 그 사람을 아니까 직접 넣을 수 있어야 한다.
--
-- 추정값(gender)과 같은 칸에 쓰면 다음 재계산 때 워커가 덮어쓴다. 그래서 칸을 나눈다:
--   gender         워커가 매번 다시 쓰는 추정값
--   gender_manual  사람이 넣은 값 — 워커는 절대 건드리지 않는다
-- 실제로 쓰는 값은 gender_manual 이 있으면 그것, 없으면 gender.
alter table customers add column if not exists gender_manual text;
