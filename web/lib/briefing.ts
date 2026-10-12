import { txKind } from './tx';
import { friendlyService } from './service-name';
import { addDays, dayLabel } from './week';

/**
 * 홈 '예약 브리핑' — 손님이 오기 전에 카르테를 하나씩 열지 않아도 되게, 예약마다
 * 몇 주 만인지 · 지난번에 뭘 했는지 · 무슨 얘기를 했는지 · 선불이 남았는지를 한 덩이로 묶는다.
 * 화면(app/home-view.tsx)은 여기서 만든 말을 놓기만 한다.
 */

/** 'YYYY-MM-DD' 두 날짜 사이 일수(to − from). */
export function daysBetween(from: string, to: string): number {
  const t = (d: string) => {
    const [y, m, dd] = d.split('-').map(Number);
    return Date.UTC(y, m - 1, dd);
  };
  return Math.round((t(to) - t(from)) / 86400000);
}

/** 기간을 말로 — '10일' · '6주' · '3개월' · '2년'. 미용실에서 실제로 쓰는 단위를 따른다. */
export function spanWords(days: number): string {
  if (days < 14) return `${days}일`;
  if (days < 70) return `${Math.round(days / 7)}주`;
  if (days < 730) return `${Math.round(days / 30)}개월`;
  return `${Math.floor(days / 365)}년`;
}

/** 평소보다 많이 늦게 오시나 — 워커의 '이탈 위험'과 같은 배수(worker/scrape.py _derive). */
export const LATE_RATIO = 1.6;

/**
 * '6주 만 · 평소 5주' — 지난 방문에서 이 예약일까지. 평소 주기는 방문 2회 이상이라 실제 간격이
 * 있을 때만 붙인다. late 면 화면이 눈에 띄게 칠한다(오랜만에 오시는 분은 안부부터).
 */
export function gapLine(
  lastVisit: string | null | undefined,
  bookingDate: string,
  cycleDays: number | null | undefined,
): { text: string; late: boolean } | null {
  if (!lastVisit) return null;
  const gap = daysBetween(lastVisit, bookingDate);
  if (gap <= 0) return null;
  const cyc = cycleDays && cycleDays > 0 ? cycleDays : null;
  return {
    text: `${spanWords(gap)} 만${cyc ? ` · 평소 ${spanWords(cyc)}` : ''}`,
    late: !!cyc && gap > cyc * LATE_RATIO,
  };
}

/**
 * 이번이 몇 번째 방문인지 — 첫 방문과 두 번째 방문만 짚는다. 신규 넷 중 셋은 다시 오지 않아서
 * (2026-10-12 실측, 2회차 전환 22%) 두 번째로 오신 분은 그 자체로 챙길 이유다.
 */
export function visitTag(visitCount: number | null | undefined): '첫 방문' | '두 번째 방문' | null {
  if (!visitCount) return '첫 방문';
  return visitCount === 1 ? '두 번째 방문' : null;
}

/** 매장 메모 정리(memo_ai · memo_ai_recent)의 줄들 — 앞의 '- ' 를 떼고 최대 n줄. */
export function memoLines(text: string | null | undefined, n: number): string[] {
  return (text ?? '')
    .split('\n')
    .map((l) => l.trim().replace(/^[-•*]\s*/, '').trim())
    .filter(Boolean)
    .slice(0, n);
}

/** 근황 중 가장 최근 한 줄 — 줄 앞의 (YYYY-MM) 꼬리표로 고른다. 꼬리표가 없으면 첫 줄. */
export function latestRecent(text: string | null | undefined): string | null {
  const lines = memoLines(text, 3);
  if (!lines.length) return null;
  const tag = (l: string) => /^\((\d{4}-\d{2})\)/.exec(l)?.[1] ?? '';
  return lines.reduce((best, l) => (tag(l) > tag(best) ? l : best));
}

/**
 * 지난 방문에 받은 시술 — 같은 날 여러 건이면 ' + '로 잇는다. 마지막 방문일(last_visit)의 시술
 * 거래만 본다. 충전·제품은 시술이 아니라 뺀다. 이름은 직급·가격 표기를 뗀 것(friendlyService).
 */
export function lastServices(
  tx: { customer_id: string | null; date: string | null; service: string | null; kind: string | null }[],
  lastVisitOf: (customerId: string) => string | null | undefined,
): Map<string, string> {
  const acc = new Map<string, string[]>();
  for (const t of tx) {
    if (!t.customer_id || !t.date || t.date !== lastVisitOf(t.customer_id)) continue;
    if (txKind(t.kind, t.service) !== 'service') continue;
    const s = friendlyService(t.service);
    if (!s) continue;
    const a = acc.get(t.customer_id) ?? [];
    if (!a.includes(s)) a.push(s);
    acc.set(t.customer_id, a);
  }
  return new Map([...acc].map(([id, a]) => [id, a.join(' + ')]));
}

/** 날짜 머리말 — '오늘 · 10.12(월)' · '내일 · 10.13(화)' · '10.15(수)'. */
export function dayHead(date: string, today: string): string {
  if (date === today) return `오늘 · ${dayLabel(date)}`;
  if (date === addDays(today, 1)) return `내일 · ${dayLabel(date)}`;
  return dayLabel(date);
}
