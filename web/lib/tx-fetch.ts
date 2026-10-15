import type { PostgrestError } from '@supabase/supabase-js';
import type { supabaseServer } from './supabase/server';
import { fetchAllRows } from './customers';

type Sb = ReturnType<typeof supabaseServer>;

/**
 * 손님 몇 명의 거래 — 50명씩 나눠 한꺼번에, 묶음마다 끝까지 받는다(fetchAllRows — 1000행 상한에 잘리지 않게).
 * 매장 거래를 통째로 받아 몇 명 것만 골라 쓰던 곳(홈)이 쓴다(개선 계획 v12 P0). since · until 은 날짜(양 끝 포함).
 */
export async function txsOfCustomers<T>(
  supabase: Sb,
  tenantId: string,
  ids: string[],
  cols: string,
  since: string | null,
  until: string | null,
): Promise<T[]> {
  const chunks: string[][] = [];
  for (let i = 0; i < ids.length; i += 50) chunks.push(ids.slice(i, i + 50));
  const parts = await Promise.all(
    chunks.map((part) =>
      fetchAllRows<T>((from, to) => {
        let q = supabase.from('transactions').select(cols).eq('tenant_id', tenantId).in('customer_id', part);
        if (since) q = q.gte('date', since);
        if (until) q = q.lte('date', until);
        return q.order('id').range(from, to) as unknown as PromiseLike<{ data: T[] | null; error: PostgrestError | null }>;
      }),
    ),
  );
  return parts.flat();
}
