// 시술별 표준 재관리 주기와, 고객에게 쓸 자연스러운 표현.
//   펌은 3개월쯤 풀리고, 뿌리염색은 5주면 뿌리가 올라오고, 커트는 남자 4주·여자 8주로 크게 다르다.
// 개인 방문주기(실제 행동)가 있으면 타이밍은 그쪽이 우선이지만, 문구는 항상 '무엇을 받았는지'에
// 맞춰 말해야 자연스럽다("이제 관리할 시기" → "뿌리 올라올 때쯤이라").
//
// 분류는 반드시 '원본 POS 메뉴명'으로 한다. 고객에게 보이는 이름은 friendlyService 가 '커트'로
// 뭉뚱그리지만(남자컷(부원장) → 커트), 주기 판단에는 성별·부위 정보가 필요하기 때문이다.
// 위에서부터 먼저 매칭되는 규칙을 쓰므로, 복합 시술(남자컷+다운펌)은 펌·염색이 우선한다.

// 표는 web/lib/care-cycle.json — 점검 스크립트(worker/care_cycle.py)도 같은 파일을 읽는다.
//   tip: 그날 받은 시술의 홈케어 안내(방문 관리 화면에 그대로 — 손님께 전할 말 겸 기억용)
//   keep: 1~2주 뒤 첫 방문 안부에 넣을 팁 — 시술 직후용 팁('당일'·'이틀')은 그때 보내면 어색하다
import table from './care-cycle.json';

export type Care = { cat: string; days: number; phrase: string; tip: string; keep: string };

// '뿌리펌'은 펌인데 '뿌리'에 먼저 걸리면 염색 주기가 잡힌다 → 표에서 뿌리염색보다 위에 둔다.
// 염색은 클리닉보다 위('염색클리닉'은 색이 주된 시술), 커트는 성별·부위로 가장 크게 갈린다
// (앞머리 3주 < 남자·주니어 4주 < 여자 8주). 순서가 뜻을 갖는다.
const TABLE: { test: RegExp; care: Care }[] = table.rules.map((r) => ({
  test: new RegExp(r.pattern),
  care: { cat: r.cat, days: r.days, phrase: r.phrase, tip: r.tip, keep: r.keep },
}));

/** 시술 종류(cat) → 표준 주기(일). 다음 시술 추천(lib/recommend)이 종류별로 때가 됐는지 볼 때 쓴다. */
export const CYCLE_BY_CAT: Record<string, number> = Object.fromEntries(TABLE.map((r) => [r.care.cat, r.care.days]));

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

/**
 * 그날 받은 시술 중 주기가 가장 짧은 것 — 먼저 돌아올 이유가 다음 방문을 정한다(남자컷+뿌리염색 →
 * 남자커트 4주). 카르테 '다음 방문' 추정과 첫 방문 손님 '다시 오실 때'가 같은 규칙을 쓴다.
 */
export function soonestCare(services: (string | null | undefined)[]): { service: string; care: Care } | null {
  let best: { service: string; care: Care } | null = null;
  for (const s of services) {
    const c = careFor(s);
    if (c && s && (!best || c.days < best.care.days)) best = { service: s, care: c };
  }
  return best;
}
