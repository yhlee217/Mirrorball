-- 매장 메모 AI 정리 — 카르테 최상단 '한눈에' 카드의 원천.
--
-- HandSOS 에서 긁어온 매장 메모는 방문마다 한 줄씩 쌓여 중구난방이다("컬 약하게", "지난번보다
-- 밝게", "두피 예민" …). 사람이 스무 줄을 훑어야 파악되던 걸, 맥에서 배치로 한 번 정리해
-- 고객마다 몇 줄로 박아둔다. 화면은 이 값을 읽기만 한다(렌더 때 AI 호출 없음).
alter table customers add column if not exists memo_ai    text;
alter table customers add column if not exists memo_ai_at timestamptz;

-- 원본 메모들의 해시. 메모가 그대로면 다시 요약하지 않는다(주 1회 배치에서 대부분 건너뜀).
alter table customers add column if not exists memo_ai_src text;
