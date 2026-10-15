import { isCancelled } from './bookings';
import { isUpcoming, kstNow } from './kst';

/**
 * 방문 탭 — 수집된 방문과, 마지막 수집 뒤 다녀가셨을 분(예약 기준).
 *
 * 수집이 일요일 한 번이라, 그 뒤(일요일 오후 · 월 · 화 …)에 다녀가신 분은 다음 일요일까지 기록이 없다.
 * '어제 분명 손님이 계셨는데 방문에 없다'(2026-10-15 폰 확인) — 그 사이는 지난 예약으로 보여 준다.
 */

/**
 * 그 방문이 손님의 몇 번째였나 — 지금 총 횟수(visit_count)에서, 목록 안의 그 뒤 방문 수를 뺀다.
 * 전에는 모든 줄에 지금 총 횟수를 붙여, 2주 안에 두 번 오신 분이 두 줄 다 '7회째'였다.
 * 목록은 최근 2주라 그 뒤 방문은 모두 목록 안에 있다(더 최근이니까).
 */
export function visitOrdinals(
  visits: { customer_id: string; date: string }[],
  totalOf: (id: string) => number,
): Map<string, number> {
  const byCust = new Map<string, Set<string>>();
  for (const v of visits) byCust.set(v.customer_id, (byCust.get(v.customer_id) ?? new Set()).add(v.date));
  const out = new Map<string, number>();
  for (const [id, dates] of byCust) {
    [...dates].sort().reverse().forEach((d, later) => out.set(`${id}|${d}`, Math.max(1, totalOf(id) - later)));
  }
  return out;
}

/**
 * 마지막 수집(KST 날짜 · 시각) 뒤에 시각이 지난 예약 — 다녀가셨을 분. 방문 기록(시술 · 금액 · 메모)은 다음
 * 수집에 들어온다. 취소 · 노쇼, 아직 오지 않은 예약(오늘 늦은 시각)은 뺀다. 수집한 날의 예약은 수집 시각
 * 뒤 것만 — 그 전 방문은 이미 수집됐다(시각을 모르는 예약도 수집된 것으로 본다).
 */
export function visitsSinceSync<B extends { date: string | null; time: string | null; status: string | null }>(
  rows: B[],
  sync: { date: string; time: string },
  now: { date: string; time: string } = kstNow(),
): B[] {
  return rows.filter((b) => {
    if (!b.date || isCancelled(b.status)) return false;
    const after = b.date > sync.date || (b.date === sync.date && !!b.time && b.time > sync.time);
    return after && !isUpcoming(b.date, b.time, now);
  });
}
