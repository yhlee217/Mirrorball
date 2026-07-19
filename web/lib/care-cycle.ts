// 시술별 표준 재관리 주기와, 고객에게 쓸 자연스러운 표현.
//   펌은 3개월쯤 풀리고, 뿌리염색은 5주면 뿌리가 올라오고, 커트는 남자 4주·여자 8주로 크게 다르다.
// 개인 방문주기(실제 행동)가 있으면 타이밍은 그쪽이 우선이지만, 문구는 항상 '무엇을 받았는지'에
// 맞춰 말해야 자연스럽다("이제 관리할 시기" → "뿌리 올라올 때쯤이라").
//
// 분류는 반드시 '원본 POS 메뉴명'으로 한다. 고객에게 보이는 이름은 friendlyService 가 '커트'로
// 뭉뚱그리지만(남자컷(부원장) → 커트), 주기 판단에는 성별·부위 정보가 필요하기 때문이다.
// 위에서부터 먼저 매칭되는 규칙을 쓰므로, 복합 시술(남자컷+다운펌)은 펌·염색이 우선한다.

export type Care = { cat: string; days: number; phrase: string };

const TABLE: { test: RegExp; care: Care }[] = [
  // '뿌리펌'은 펌인데 '뿌리'에 먼저 걸리면 염색 주기가 잡힌다 → 뿌리염색보다 위에 둔다.
  { test: /뿌리\s*(?:볼륨)?\s*펌/, care: { cat: '뿌리펌', days: 70, phrase: '볼륨 슬슬 가라앉을 때쯤이라' } },
  { test: /뿌리|새치/, care: { cat: '뿌리염색', days: 35, phrase: '뿌리 올라올 때쯤이라' } },
  { test: /다운펌/, care: { cat: '다운펌', days: 56, phrase: '슬슬 풀릴 때쯤이라' } },
  { test: /매직|셋팅|디지털|볼륨|웨이브|펌/, care: { cat: '펌', days: 90, phrase: '슬슬 풀릴 때쯤이라' } },
  // 염색을 클리닉보다 위에 — '염색클리닉'은 색이 주된 시술이라 염색 주기가 맞다.
  { test: /염색|컬러|이노아|탈색|블리치|하이라이트|톤다운|톤업/, care: { cat: '염색', days: 56, phrase: '컬러 빠질 때쯤이라' } },
  { test: /클리닉|트리트|케어|앰플|두피|스켈프/, care: { cat: '클리닉', days: 28, phrase: '모발 컨디션 챙기실 때라' } },
  // 커트 — 성별·부위로 주기가 가장 크게 갈린다(앞머리 3주 < 남자·주니어 4주 < 여자 8주).
  { test: /앞머리\s*(?:컷|커트)/, care: { cat: '앞머리컷', days: 21, phrase: '앞머리 자랐을 때쯤이라' } },
  { test: /(?:주니어|학생|아동|어린이)\s*(?:컷|커트)/, care: { cat: '주니어커트', days: 28, phrase: '머리 자랐을 때쯤이라' } },
  { test: /(?:남자|남성)\s*(?:컷|커트)/, care: { cat: '남자커트', days: 28, phrase: '머리 자라 정리하실 때쯤이라' } },
  { test: /(?:여자|여성)\s*(?:컷|커트)/, care: { cat: '여자커트', days: 56, phrase: '머리 모양 정리하실 때쯤이라' } },
  { test: /컷|커트/, care: { cat: '커트', days: 35, phrase: '머리 정리하실 때쯤이라' } },
];

/** 원본 메뉴명 → 표준 관리주기·표현. 매칭 안 되면 null(일반 문구로 폴백). */
export function careFor(service?: string | null): Care | null {
  if (!service) return null;
  for (const r of TABLE) if (r.test.test(service)) return r.care;
  return null;
}

/** 이 고객에게 쓸 주기(일) — 개인 방문주기가 있으면 우선, 없으면 시술 표준, 그것도 없으면 42. */
export function effectiveCycle(service?: string | null, personalDays?: number | null): number {
  if (personalDays && personalDays > 0) return personalDays;
  return careFor(service)?.days ?? 42;
}
