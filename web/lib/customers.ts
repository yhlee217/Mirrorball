import type { PostgrestError } from '@supabase/supabase-js';
import { isLapsed, type TenantSettings } from './settings';
import { awayDays } from './offdays';
import { daysBetween } from './week';
import { soonestCare } from './care-cycle';
import { txKind } from './tx';

// 실제 고객만 관리 대상 — 고객번호(숫자) ext_id 를 가진 고객. '손님' 등 미식별 워크인
// 집계는 이름 기반(비숫자) ext_id 라 관리 화면(홈·알림·목록)에서 제외한다.
export const isRealCustomer = (extId: string | null | undefined): boolean => /^\d+$/.test(extId ?? '');

// 디자이너가 직접 '이탈'로 표시한 고객. 자동 판정(revisit_state)은 추정일 뿐이라,
// 확실히 안 오시는 걸 아는 사람이 확정한 이 표시가 우선한다 → 챙길 고객·홈 신호에서 제외.
export const isChurned = (c: { churned_at?: string | null }): boolean => !!c.churned_at;

/** 워커가 쓰는 기본 주기 — 방문 간격을 모를 때(worker/scrape.py _derive 의 42). */
export const DEFAULT_CYCLE = 42;
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

/** 선불 잔액을 남긴 채 이 날수를 넘겨 안 오신 분 — 통계 알약 · 고객 목록 필터가 같은 기준(개선 계획 v5 P3). */
export const PREPAID_AWAY_DAYS = 90;

/**
 * 선불 잔액을 남긴 채 발길이 끊긴 분인가. 이미 받은 돈이라 다시 오시게 하기 가장 쉬운 손님이고, 오래
 * 두면 환불 요청·불만으로 돌아온다. 잔액은 워커의 추정(결제수단이 기록되지 않는다)이라 화면에만 쓴다 —
 * 손님 문자엔 넣지 않는다. 디자이너가 이탈로 표시한 분은 뺀다. today 는 KST 날짜.
 */
export function prepaidAway(
  c: { prepaid_balance: number | null; last_visit: string | null; churned_at?: string | null },
  today: string,
): boolean {
  if ((c.prepaid_balance ?? 0) <= 0 || !c.last_visit || c.churned_at) return false;
  return daysBetween(c.last_visit.slice(0, 10), today) > PREPAID_AWAY_DAYS;
}

/** 첫 방문 안부를 띄우는 기간 — 첫 방문 뒤 이 날수 안. 수집이 주 1회라 두 번의 수집에 걸친다. */
export const HELLO_DAYS = 14;

export type FirstCare = 'hello' | 'back';

/**
 * 첫 방문 손님(방문 1회)을 챙길 때인가(개선 계획 v4 P1). 워커는 이분들을 '신규(new)'로만 두어
 * 재방문 판정(due·overdue)에 걸리지 않았다 — 신규 넷 중 셋이 다시 안 오는데(2026-10-12 실측 22%)
 * 할 일 목록 밖에 있었다.
 *   hello — 첫 방문 뒤 HELLO_DAYS 안: 예약 권유 없는 안부(+ 오래 두고 쓸 관리 팁)
 *   back  — 그날 받은 시술의 표준 주기 ~ 그 두 배(휴가는 뺀다): 다시 오실 때. 두 배를 넘기면 내린다 —
 *           처음 한 번 오신 분을 몇 달씩 목록에 두면 지금 챙길 분이 묻힌다. 설정의 이탈 판정(6개월에
 *           3회 미만 등)이 먼저 걸리면 거기서 끝.
 * services = 그날 받은 원본 메뉴명들(주기는 가장 짧은 것 — lib/care-cycle soonestCare). asOf = 마지막 수집일.
 */
export function firstCare(
  c: { visit_count: number; last_visit: string | null },
  services: (string | null | undefined)[],
  s: TenantSettings,
  asOf: string,
): FirstCare | null {
  if (c.visit_count !== 1 || !c.last_visit) return null;
  const day = c.last_visit.slice(0, 10);
  const ago = daysBetween(day, asOf);
  if (ago < 0) return null;
  if (ago < HELLO_DAYS) return 'hello';
  const cyc = soonestCare(services)?.care.days ?? DEFAULT_CYCLE;
  const away = awayDays(day, asOf, s);
  if (away < cyc || away > cyc * 2) return null;
  return isLapsed(c, s) ? null : 'back';
}

/** 첫 방문 손님의 할 일 — firstCare 이면서 이탈 표시·잡힌 예약·최근 연락이 없는 분(onCareList 와 같은 규칙). */
export function onFirstList(
  c: { visit_count: number; last_visit: string | null },
  services: (string | null | undefined)[],
  o: { settings: TenantSettings; churned: boolean; booked: boolean; contacted: boolean; asOf: string },
): FirstCare | null {
  if (o.churned || o.booked || o.contacted) return null;
  return firstCare(c, services, o.settings, o.asOf);
}

/**
 * 손님별로 그날(dayOf) 받은 시술의 원본 메뉴명 — 충전·제품은 뺀다. 첫 방문 손님의 주기·문구에 쓴다
 * (주기 판단엔 '남자컷'처럼 원본 이름이 필요하다 — lib/care-cycle).
 */
export function servicesOn(
  txs: { customer_id: string | null; date: string | null; service: string | null; kind: string | null }[],
  dayOf: (id: string) => string | null | undefined,
): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const t of txs) {
    if (!t.customer_id || !t.service || !t.date) continue;
    const day = dayOf(t.customer_id);
    if (!day || t.date.slice(0, 10) !== day.slice(0, 10)) continue;
    if (txKind(t.kind, t.service) !== 'service') continue;
    const list = out.get(t.customer_id) ?? [];
    if (!list.includes(t.service)) list.push(t.service);
    out.set(t.customer_id, list);
  }
  return out;
}

/**
 * Supabase/PostgREST 는 요청당 최대 1000행(하드캡)만 반환한다.
 * 1000행이 넘을 수 있는 조회는 range 로 나눠 전부 가져와야 한다
 * (안 그러면 홈·고객목록·통계가 1000행만 본다).
 * makeQuery 는 반드시 안정 정렬(.order)과 .range(from, to) 를 포함해야 한다.
 *
 * 첫 쪽이 꽉 차면 다음 쪽들은 BATCH 개씩 한꺼번에 받는다 — 1만 행이면 차례로 열 번 기다리던 것이
 * 첫 쪽 + 세 묶음, 네 번이 된다(개선 계획 v4 0-3). 끝을 넘긴 쪽은 빈 배열이라 해가 없다.
 */
const PAGE = 1000;
const BATCH = 4;

export async function fetchAllRows<T = Record<string, unknown>>(
  makeQuery: (from: number, to: number) => PromiseLike<{ data: T[] | null; error: PostgrestError | null }>,
): Promise<T[]> {
  const page = async (n: number): Promise<T[]> => {
    const { data, error } = await makeQuery(n * PAGE, n * PAGE + PAGE - 1);
    if (error) throw error;
    return (data ?? []) as T[];
  };
  const out = await page(0);
  if (out.length < PAGE) return out;
  for (let n = 1; ; n += BATCH) {
    const parts = await Promise.all(Array.from({ length: BATCH }, (_, i) => page(n + i)));
    for (const p of parts) out.push(...p);
    if (parts.some((p) => p.length < PAGE)) return out;
  }
}
