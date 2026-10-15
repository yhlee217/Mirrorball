import { DEFAULT_CYCLE, HELLO_DAYS } from './customers';
import { CONTACT_QUIET_DAYS, type ContactLog } from './contact';
import { kstDay } from './effect';
import { awayDays } from './offdays';
import { soonestCare } from './care-cycle';
import type { TenantSettings } from './settings';
import { addDays, daysBetween } from './week';

/**
 * '이번 주 새로'(개선 계획 v10 P1) — 챙길 고객에 이번 수집으로 새로 오른 분.
 *
 * 한 매장 84명(UX 계획 v3 실측)을 50명씩 펼치는 목록이라 '이번 주엔 누구부터'가 없었다 — 연락 기록이 생긴 10.12 뒤
 * 세 매장 모두 연락 0명(2026-10-15 매일 감시). 목록 판정(lib/customers)은 그대로 두고, 지난주 수집(asOf − 7일) 땐
 * 목록에 없던 분을 맨 위에 모은다. 지금 목록에 있는 분(onCareList · onFirstList)에만 묻는다.
 */
export const NEW_DAYS = 7; // 수집이 주 1회 — 지난 수집과 이번 수집 사이

/**
 * 지난주 수집 땐 챙길 고객이 아니었나. state = 지금 목록의 상태(due · overdue · hello · back).
 *   due · overdue — 그때는 평소 주기(휴가를 뺀 날)가 아직 안 됐다 — 지금 판정(careState)과 같은 셈
 *   hello         — 첫 방문이 지난주 수집 뒤(그 전이면 그때도 안부였다)
 *   back          — 그때는 안부(첫 방문 14일 안)도, 다시 오실 때(주기 ~ 두 배)도 아니었다
 * 그리고 연락 뒤 숨김(CONTACT_QUIET_DAYS)이 지난 7일 안에 끝나 다시 오른 분. 예약 · 이탈 표시가 풀려 돌아온 분은
 * 드물어 따지지 않는다(그분들은 '새로' 없이 제자리에).
 */
export function newOnList(
  state: string,
  c: { last_visit: string | null; revisit_cycle_days: number | null },
  o: {
    settings: TenantSettings;
    asOf: string; // 마지막 수집일(판정 기준일)
    today: string; // KST — 숨김이 끝난 날을 견준다
    services?: (string | null | undefined)[]; // 첫 방문 손님 — 그날 받은 시술(주기)
    lastContact?: string | null; // 이 손님의 마지막 연락일(KST)
  },
): boolean {
  if (o.lastContact) {
    const back = addDays(o.lastContact, CONTACT_QUIET_DAYS); // 숨김이 끝난 날
    if (back > addDays(o.today, -NEW_DAYS) && back <= o.today) return true;
  }
  if (!c.last_visit) return false;
  const day = c.last_visit.slice(0, 10);
  const prev = addDays(o.asOf, -NEW_DAYS); // 지난주 수집
  if (day > prev) return true; // 지난 수집 뒤의 방문 — 이번 주 첫 방문(안부)
  if (state === 'hello') return false;
  const away = awayDays(day, prev, o.settings);
  if (state === 'back') {
    if (daysBetween(day, prev) < HELLO_DAYS) return false; // 그때는 안부였다
    const cyc = soonestCare(o.services ?? [])?.care.days ?? DEFAULT_CYCLE;
    return away < cyc || away > cyc * 2;
  }
  const cyc = c.revisit_cycle_days && c.revisit_cycle_days > 0 ? c.revisit_cycle_days : DEFAULT_CYCLE;
  return away < cyc;
}

/** 손님별 마지막 연락일(KST) — 숨김이 끝난 날을 셀 때. */
export function lastContactDays(rows: ContactLog[]): Map<string, string> {
  const out = new Map<string, string>();
  for (const r of rows) {
    if (!r.customer_id || !r.sent_at) continue;
    const d = kstDay(r.sent_at);
    const cur = out.get(r.customer_id);
    if (!cur || d > cur) out.set(r.customer_id, d);
  }
  return out;
}
