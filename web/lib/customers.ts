import type { PostgrestError } from '@supabase/supabase-js';
import { isLapsed, type TenantSettings } from './settings';

// 실제 고객만 관리 대상 — 고객번호(숫자) ext_id 를 가진 고객. '손님' 등 미식별 워크인
// 집계는 이름 기반(비숫자) ext_id 라 관리 화면(홈·알림·목록)에서 제외한다.
export const isRealCustomer = (extId: string | null | undefined): boolean => /^\d+$/.test(extId ?? '');

// 디자이너가 직접 '이탈'로 표시한 고객. 자동 판정(revisit_state)은 추정일 뿐이라,
// 확실히 안 오시는 걸 아는 사람이 확정한 이 표시가 우선한다 → 챙길 고객·홈 신호에서 제외.
export const isChurned = (c: { churned_at?: string | null }): boolean => !!c.churned_at;

/**
 * '챙길 고객'인가 — 연락해서 다시 오시게 할 분. 판정은 여기 한 곳에서만 한다.
 * 홈 신호·홈 카드·챙길 고객 탭·고객 목록 필터·통계 '지금 할 일'이 모두 이걸로 센다.
 * 화면마다 따로 세면 '눌렀더니 인원이 다른' 일이 생긴다.
 *
 * 앞으로 올 예약이 있으면 뺀다. 추천 문구가 '편하신 시간에 예약 도와드릴게요'라서
 * 이미 예약한 분께 그대로 보내게 된다(2026-10-12 실측: 세 매장 368명 중 17명).
 * 실고객 여부(isRealCustomer)는 다른 집계에도 쓰여 호출부에서 먼저 거른다.
 */
export function needsCare(
  c: { revisit_state: string | null; last_visit: string | null; visit_count: number },
  o: { settings: TenantSettings; churned: boolean; booked: boolean },
): boolean {
  if (o.churned || o.booked) return false;
  if (c.revisit_state !== 'overdue' && c.revisit_state !== 'due') return false;
  return !isLapsed(c, o.settings);
}

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
