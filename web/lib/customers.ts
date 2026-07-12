import type { PostgrestError } from '@supabase/supabase-js';

/**
 * Supabase/PostgREST 는 요청당 최대 1000행(하드캡)만 반환한다.
 * 1000행이 넘을 수 있는 조회는 range 로 나눠 전부 가져와야 한다
 * (안 그러면 홈·고객목록·통계가 1000행만 본다).
 * makeQuery 는 반드시 안정 정렬(.order)과 .range(from, to) 를 포함해야 한다.
 */
export async function fetchAllRows<T = Record<string, unknown>>(
  makeQuery: (from: number, to: number) => PromiseLike<{ data: T[] | null; error: PostgrestError | null }>,
): Promise<T[]> {
  const PAGE = 1000;
  const out: T[] = [];
  for (let from = 0; ; from += PAGE) {
    const { data, error } = await makeQuery(from, from + PAGE - 1);
    if (error) throw error;
    const rows = (data ?? []) as T[];
    out.push(...rows);
    if (rows.length < PAGE) break;
  }
  return out;
}
