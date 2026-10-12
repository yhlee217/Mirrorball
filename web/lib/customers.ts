import type { PostgrestError } from '@supabase/supabase-js';
import { isLapsed, type TenantSettings } from './settings';
import { awayDays } from './offdays';

// 실제 고객만 관리 대상 — 고객번호(숫자) ext_id 를 가진 고객. '손님' 등 미식별 워크인
// 집계는 이름 기반(비숫자) ext_id 라 관리 화면(홈·알림·목록)에서 제외한다.
export const isRealCustomer = (extId: string | null | undefined): boolean => /^\d+$/.test(extId ?? '');

// 디자이너가 직접 '이탈'로 표시한 고객. 자동 판정(revisit_state)은 추정일 뿐이라,
// 확실히 안 오시는 걸 아는 사람이 확정한 이 표시가 우선한다 → 챙길 고객·홈 신호에서 제외.
export const isChurned = (c: { churned_at?: string | null }): boolean => !!c.churned_at;

/** 워커가 쓰는 기본 주기 — 방문 간격을 모를 때(worker/scrape.py _derive 의 42). */
const DEFAULT_CYCLE = 42;
/** 평소 주기의 이 배수를 넘으면 이탈 위험(worker/scrape.py _derive 의 1.6). */
const OVERDUE_RATIO = 1.6;
const RANK: Record<string, number> = { due: 1, overdue: 2 };

/**
 * 휴가를 반영한 재방문 상태 — '재방문 도래(due)·이탈 위험(overdue)'은 워커가 수집 때 정하는데,
 * 그 사이 디자이너가 쉰 휴가 기간까지 '안 오신 날'로 센다. 그동안은 손님이 오고 싶어도 못 왔으니
 * 휴가 일수만큼 판정을 늦춘다(lib/offdays awayDays). 기준은 워커와 같다: 평소 주기(모르면 42일)
 * 이상이면 재방문 도래, 1.6배를 넘으면 이탈 위험. 정기 휴무는 평소 주기에 이미 들어 있어 빼지 않는다.
 *
 * asOf 는 워커가 판정한 날 = 마지막 수집일. 늦추기만 하고 앞당기지는 않는다 — 수집 뒤 지난 날로
 * 새로 위험해지는 건 다음 수집이 정한다(화면은 늘 수집 시점 기준이다).
 */
export function careState(
  c: { revisit_state: string | null; last_visit: string | null; revisit_cycle_days: number | null },
  s: TenantSettings,
  asOf: string,
): string | null {
  const raw = c.revisit_state;
  if ((raw !== 'due' && raw !== 'overdue') || !c.last_visit || !s.off_dates.length) return raw;
  const away = awayDays(c.last_visit.slice(0, 10), asOf, s);
  const cyc = c.revisit_cycle_days && c.revisit_cycle_days > 0 ? c.revisit_cycle_days : DEFAULT_CYCLE;
  const adj = away > cyc * OVERDUE_RATIO ? 'overdue' : away >= cyc ? 'due' : null;
  if (!adj) return null;
  return RANK[adj] < RANK[raw] ? adj : raw;
}

/**
 * '챙길 고객'인가 — 연락해서 다시 오시게 할 분. 판정은 여기 한 곳에서만 한다.
 * 홈 신호·홈 카드·챙길 고객 탭·고객 목록 필터·통계 '지금 할 일'이 모두 이걸로 센다.
 * 화면마다 따로 세면 '눌렀더니 인원이 다른' 일이 생긴다.
 *
 * 앞으로 올 예약이 있으면 뺀다. 추천 문구가 '편하신 시간에 예약 도와드릴게요'라서
 * 이미 예약한 분께 그대로 보내게 된다(2026-10-12 실측: 세 매장 368명 중 17명).
 * 재방문 상태는 휴가를 반영한 것(careState) — asOf(마지막 수집일)를 빠뜨릴 수 없게 필수로 받는다.
 * 실고객 여부(isRealCustomer)는 다른 집계에도 쓰여 호출부에서 먼저 거른다.
 */
export function needsCare(
  c: { revisit_state: string | null; last_visit: string | null; visit_count: number; revisit_cycle_days: number | null },
  o: { settings: TenantSettings; churned: boolean; booked: boolean; asOf: string },
): boolean {
  if (o.churned || o.booked) return false;
  const st = careState(c, o.settings, o.asOf);
  if (st !== 'overdue' && st !== 'due') return false;
  return !isLapsed(c, o.settings);
}

/**
 * '챙길 고객' 목록(할 일)에 올릴까 — needsCare 이면서 최근 연락하지 않은 분(lib/contact.ts).
 * 연락했다고 위험이 풀리진 않으니 이탈위험·재방문도래 타일과 고객 목록 필터는 needsCare 로
 * 세고, 할 일(챙길 고객 탭·홈 카드·'챙길 고객 N'·통계 '지금 할 일')만 이걸로 센다.
 * 각 숫자는 눌렀을 때 열리는 화면과 같은 기준이어야 한다.
 */
export function onCareList(
  c: { revisit_state: string | null; last_visit: string | null; visit_count: number; revisit_cycle_days: number | null },
  o: { settings: TenantSettings; churned: boolean; booked: boolean; contacted: boolean; asOf: string },
): boolean {
  return !o.contacted && needsCare(c, o);
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
