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
  return rows.filter((b) => !isCancelled(b.status) && passedSinceSync(b, sync, now));
}

/** 마지막 수집 뒤 · 시각이 지난 예약인가(상태는 보지 않는다). 수집한 날은 수집 시각 뒤 것만. */
function passedSinceSync(
  b: { date: string | null; time: string | null },
  sync: { date: string; time: string },
  now: { date: string; time: string },
): boolean {
  if (!b.date) return false;
  const after = b.date > sync.date || (b.date === sync.date && !!b.time && b.time > sync.time);
  return after && !isUpcoming(b.date, b.time, now);
}

/**
 * 디자이너가 앱에서 노쇼로 표시한 예약 — 예약 상태를 '노쇼·앱|원래 상태'로 바꾼다. 노쇼 · 취소 판정(isCancelled)이
 * 모든 화면(방문 · 고객 목록 · 상세보기 · 챙길 고객)에 이미 걸려 있어 한 곳만 바꾸면 된다. 원래 상태를 뒤에 남겨
 * 되돌리기가 그대로 돌려놓는다. 수집이 주 1회라 주중에 취소 · 노쇼가 나도 앱은 일요일까지 몰랐다(2026-10-15).
 */
export const APP_NOSHOW = '노쇼·앱|';

export function isAppNoShow(status: string | null | undefined): boolean {
  return !!status && status.startsWith(APP_NOSHOW);
}

/** 노쇼 표시 · 되돌리기 뒤의 예약 상태. 할 수 없으면 ok=false — 이미 취소 · 노쇼, 아직 시간이 안 된 예약, 앱이 표시하지 않은 노쇼. */
export function noShowUpdate(
  b: { date: string | null; time: string | null; status: string | null },
  undo: boolean,
  now: { date: string; time: string } = kstNow(),
): { ok: boolean; status: string | null } {
  if (undo) {
    if (!isAppNoShow(b.status)) return { ok: false, status: b.status };
    return { ok: true, status: (b.status as string).slice(APP_NOSHOW.length) || null };
  }
  if (!b.date || isCancelled(b.status) || isUpcoming(b.date, b.time, now)) return { ok: false, status: b.status };
  return { ok: true, status: APP_NOSHOW + (b.status ?? '') };
}

/** 마지막 수집 뒤 앱에서 노쇼로 표시한 예약 — 방문 탭에 줄을 그어 남긴다(되돌리기 자리). 세지는 않는다. */
export function noShowsSinceSync<B extends { date: string | null; time: string | null; status: string | null }>(
  rows: B[],
  sync: { date: string; time: string },
  now: { date: string; time: string } = kstNow(),
): B[] {
  return rows.filter((b) => isAppNoShow(b.status) && passedSinceSync(b, sync, now));
}

/**
 * 손님별 수집 뒤 다녀가신 날(예약 기준) — 몇 번 · 마지막 날. 고객 목록 · 상세보기의 'N회' · '마지막 방문'을
 * 수집 기준이 아니라 지금 기준으로 맞춘다("지금 이미 다녀가신 분은 세야지", 2026-10-15 폰 확인).
 * 같은 날 두 예약은 한 번. 노쇼였다면 다음 수집이 바로잡는다.
 */
export function seenSinceSync<B extends { customer_id: string | null; date: string | null; time: string | null; status: string | null }>(
  rows: B[],
  sync: { date: string; time: string } | null,
  now: { date: string; time: string } = kstNow(),
): Map<string, { count: number; last: string }> {
  const out = new Map<string, { count: number; last: string }>();
  if (!sync) return out;
  const days = new Map<string, Set<string>>();
  for (const b of visitsSinceSync(rows, sync, now)) {
    if (b.customer_id && b.date) days.set(b.customer_id, (days.get(b.customer_id) ?? new Set()).add(b.date));
  }
  for (const [id, ds] of days) {
    const sorted = [...ds].sort();
    out.set(id, { count: sorted.length, last: sorted[sorted.length - 1] });
  }
  return out;
}

/** 마지막 방문 — 수집된 날과 수집 뒤 다녀가신 날 중 늦은 쪽(KST 날짜). */
export function laterDay(a: string | null | undefined, b: string | null | undefined): string | null {
  const x = a ? a.slice(0, 10) : null;
  const y = b ? b.slice(0, 10) : null;
  if (!x) return y;
  if (!y) return x;
  return x > y ? x : y;
}
