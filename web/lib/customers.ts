import type { PostgrestError } from '@supabase/supabase-js';

// 실제 고객만 관리 대상 — 고객번호(숫자) ext_id 를 가진 고객. '손님' 등 미식별 워크인
// 집계는 이름 기반(비숫자) ext_id 라 관리 화면(홈·알림·목록)에서 제외한다.
export const isRealCustomer = (extId: string | null | undefined): boolean => /^\d+$/.test(extId ?? '');

// 디자이너가 직접 '이탈'로 표시한 고객. 자동 판정(revisit_state)은 추정일 뿐이라,
// 확실히 안 오시는 걸 아는 사람이 확정한 이 표시가 우선한다 → 챙길 고객·홈 신호에서 제외.
export const isChurned = (c: { churned_at?: string | null }): boolean => !!c.churned_at;

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
