import { isUpcoming, kstDatePlus, kstNow } from './kst';
import { fetchAllRows } from './customers';
import type { supabaseServer } from './supabase/server';

/**
 * 예약 판정 한 곳. 화면마다 따로 짜다가 고객 목록만 날짜를 안 걸러서,
 * 주 1회 수집으로 바뀐 뒤 '지난주에 다녀간 사람'이 계속 예약 있음으로 보였다.
 */

/** 취소·노쇼는 '그 시간이 비었다'는 뜻이라 앞으로 올 예약으로 세지 않는다. */
export function isCancelled(status: string | null | undefined): boolean {
  return !!status && /취소|노쇼/.test(status);
}

type Now = { date: string; time: string };

/**
 * 실제로 '앞으로 올 예약'인가.
 *
 * DB 의 예약은 마지막 수집 시점에 미래였던 것들이다. 수집이 주 1회라 그중 최대 일주일치는
 * 이미 지나가 있다. 수집 주기에 기대지 말고 화면에서 항상 지금 시각으로 다시 걸러야 한다.
 */
export function isActiveBooking(
  b: { date: string | null; time: string | null; status?: string | null },
  now: Now = kstNow(),
): boolean {
  return !isCancelled(b.status) && isUpcoming(b.date, b.time, now);
}

/**
 * 마지막 수집(since, KST 날짜) 뒤에 잡혀 있던 예약인가 — 시각이 지났어도 '다녀가셨을 분'으로 본다.
 *
 * 수집이 일요일 한 번이라 화요일에 다녀가신 분의 방문은 다음 일요일에야 잡힌다. 그 사이 예약은
 * 지난 것이 되고 방문은 아직 없어, 이 판정이 없을 땐 수~토에 '이탈 위험 · 재방문 도래'로 다시
 * 올랐다 — 어제 오신 분께 '오랜만이에요' 문자가 나갈 수 있었다(개선 계획 v6 P0).
 * 취소·노쇼가 아니면 다녀가셨다고 보고 다음 수집까지 챙길 고객에서 뺀다. 노쇼였다면 다음 수집이
 * 노쇼로 고쳐 받아 오고, 그 예약은 수집일보다 앞이 되어 저절로 다시 오른다(늦어도 한 주).
 */
export function isHeldBooking(b: { date: string | null; status?: string | null }, since: string): boolean {
  return !isCancelled(b.status) && !!b.date && b.date >= since;
}

export type BookingRow = { customer_id: string | null; date: string | null; time: string | null; status: string | null };

/**
 * 손님별 예약 판정 둘 — 같은 줄에서 뜻이 다른 두 집합을 만든다.
 *  upcoming: 앞으로 올 예약이 있는 분 — 고객 목록 '예약 있음', 연락 문구.
 *  hold:     챙길 고객에서 잠시 뺄 분 — upcoming + 마지막 수집 뒤 예약 시각이 지난 분(isHeldBooking).
 *            챙길 고객 · 홈 숫자 · 이탈위험/재방문도래 · 카르테 뱃지 · 연락 효과의 '예약'이 모두 이것을 쓴다.
 */
export function bookingSets(rows: BookingRow[], since: string, now: Now = kstNow()): { upcoming: Set<string>; hold: Set<string> } {
  const upcoming = new Set<string>();
  const hold = new Set<string>();
  for (const b of rows) {
    if (!b.customer_id) continue;
    if (isActiveBooking(b, now)) {
      upcoming.add(b.customer_id);
      hold.add(b.customer_id);
    } else if (isHeldBooking(b, since)) {
      hold.add(b.customer_id);
    }
  }
  return { upcoming, hold };
}

/** 마지막 수집일이 한두 주 밀려도 '수집 뒤 지난 예약'을 잡게 넉넉히 거슬러 받는다. */
export const BOOKING_LOOKBACK_DAYS = 28;

/** 손님별 예약 판정 재료(bookingSets) — 4주 전부터. 수집일(since)은 화면이 같이 읽어 넘긴다. */
export async function recentBookingRows(
  supabase: ReturnType<typeof supabaseServer>,
  tenantId: string,
): Promise<BookingRow[]> {
  return fetchAllRows<BookingRow>((from, to) =>
    supabase.from('bookings').select('customer_id,date,time,status')
      .eq('tenant_id', tenantId).gte('date', kstDatePlus(-BOOKING_LOOKBACK_DAYS)).order('id').range(from, to));
}
