import { isUpcoming, kstNow } from './kst';
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

/**
 * 실제로 '앞으로 올 예약'인가.
 *
 * DB 의 예약은 마지막 수집 시점에 미래였던 것들이다. 수집이 주 1회라 그중 최대 일주일치는
 * 이미 지나가 있다. 수집 주기에 기대지 말고 화면에서 항상 지금 시각으로 다시 걸러야 한다.
 */
export function isActiveBooking(b: {
  date: string | null;
  time: string | null;
  status?: string | null;
}): boolean {
  return !isCancelled(b.status) && isUpcoming(b.date, b.time);
}

/**
 * 앞으로 올 예약이 있는 고객 id — '챙길 고객'에서 빼는 데 쓴다(needsCare).
 * 오늘부터만 가져오고, 오늘 이미 지난 시각·취소·노쇼는 isActiveBooking 이 거른다.
 */
export async function bookedCustomerIds(
  supabase: ReturnType<typeof supabaseServer>,
  tenantId: string,
): Promise<Set<string>> {
  const rows = await fetchAllRows<{ customer_id: string | null; date: string | null; time: string | null; status: string | null }>(
    (from, to) => supabase.from('bookings').select('customer_id,date,time,status')
      .eq('tenant_id', tenantId).gte('date', kstNow().date).order('id').range(from, to),
  );
  return new Set(rows.filter((b) => b.customer_id && isActiveBooking(b)).map((b) => b.customer_id as string));
}
