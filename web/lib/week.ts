import { txKind } from './tx';

/**
 * 홈 '이번 주 요약'의 지난 한 주 — 몇 분이 다녀가셨고(그중 첫 방문), 얼마를 벌었나.
 *
 * 수집은 주 1회(일 14:00)다. '오늘부터 7일 전'으로 잡으면 아직 수집되지 않은 날이 섞여
 * 수집 직전일수록 숫자가 줄어든 것처럼 보인다. 수집 당일도 수집 시각 뒤가 빠져 있다.
 * 그래서 '마지막 수집일 전날까지 7일'을 지난 한 주로 쓴다. 견주는 전주도 같은 모양이라
 * 둘 다 빈틈이 없다 — 한쪽만 덜 채워져 있으면 '줄었다'로 잘못 읽힌다.
 */

export type Span = { start: string; end: string };

/** 'YYYY-MM-DD' + n일. */
export function addDays(date: string, n: number): string {
  const [y, m, d] = date.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d + n)).toISOString().slice(0, 10);
}

/** 지난 한 주(cur)와 그 전주(prev). 수집 기록이 없으면 어제까지 7일. */
export function lastWeek(syncDate: string | null | undefined, today: string): { cur: Span; prev: Span } {
  const end = addDays(syncDate || today, -1);
  return {
    cur: { start: addDays(end, -6), end },
    prev: { start: addDays(end, -13), end: addDays(end, -7) },
  };
}

const DOW = ['일', '월', '화', '수', '목', '금', '토'];

/** '10.4(일)' — 요일을 붙여야 어느 주인지 바로 읽힌다. */
export function dayLabel(date: string): string {
  const [y, m, d] = date.split('-').map(Number);
  return `${m}.${d}(${DOW[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]})`;
}

export const spanLabel = (s: Span): string => `${dayLabel(s.start)}~${dayLabel(s.end)}`;

export type WeekTx = {
  customer_id: string | null;
  date: string | null;
  kind: string | null;
  service: string | null;
  amount_won: number | null;
  covered_won: number | null;
};
export type WeekNums = { visits: number; firsts: number; revenue: number };

const inSpan = (d: string | null | undefined, s: Span): boolean => !!d && d >= s.start && d <= s.end;

/**
 * visits  다녀가신 분 — 시술을 받은 (손님, 날짜). 충전·제품만 산 날은 방문이 아니다(방문 관리와 같은 기준).
 *         한 분이 한 주에 두 번 오면 두 번으로 센다 — 디자이너가 '몇 명 받았다'고 세는 방식.
 * firsts  첫 방문 — 첫 시술일(first_visit)이 이 주인 실고객. 호출부가 실고객의 first_visit 만 넘긴다.
 * revenue 실매출 — 금액 − 선불 잔액으로 결제된 금액. 통계 '이번 달'과 같은 규칙(충전과 그 돈으로
 *         받은 시술을 둘 다 더하면 이중 계상).
 */
export function weekNums(tx: WeekTx[], firstVisits: (string | null)[], s: Span): WeekNums {
  const seen = new Set<string>();
  let revenue = 0;
  for (const t of tx) {
    if (!inSpan(t.date, s)) continue;
    revenue += (t.amount_won || 0) - (t.covered_won || 0);
    if (t.customer_id && txKind(t.kind, t.service) === 'service') seen.add(`${t.customer_id}|${t.date}`);
  }
  return { visits: seen.size, firsts: firstVisits.filter((d) => inSpan(d, s)).length, revenue };
}
