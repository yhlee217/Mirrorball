/**
 * 연락 효과 — 챙길 고객에서 문자·전화·복사를 한 뒤 그 손님이 오셨나(개선 계획 v4 P2).
 *
 * 연락 기록(care_items, kind='contact')과 방문(거래)을 맞춰 본다. 사람 단위로 센다 — 같은 분께
 * 여러 번 연락해도 한 번, 그 기간의 첫 연락일 기준. '오심'은 연락한 날 이후의 방문(수집이 주 1회라
 * 최대 한 주 늦게 잡힌다), '예약'은 아직 안 오셨지만 지금 잡혀 있는 예약. 연락이 원인이라는 증거는
 * 아니다 — 연락 안 한 분과 견줄 수 있는 곳(첫 방문 손님)에서만 견준다.
 */

export type ContactRow = { customer_id: string | null; sent_at: string | null };
export type Effect = { contacted: number; came: number; booked: number };

/** 연락 시각(UTC ISO) → KST 날짜. 거래 날짜가 KST 라 같은 기준으로 견준다. */
export const kstDay = (iso: string): string => new Date(Date.parse(iso) + 9 * 3600000).toISOString().slice(0, 10);

/** 손님별 첫 연락일(KST) — since 이후의 연락만. */
export function firstContacts(contacts: ContactRow[], since = '0000-00-00'): Map<string, string> {
  const out = new Map<string, string>();
  for (const c of contacts) {
    if (!c.customer_id || !c.sent_at) continue;
    const day = kstDay(c.sent_at);
    if (day < since) continue;
    const prev = out.get(c.customer_id);
    if (!prev || day < prev) out.set(c.customer_id, day);
  }
  return out;
}

const tally = (rows: [string, string][], visits: Map<string, string[]>, booked: Set<string>): Effect => {
  let came = 0;
  let bk = 0;
  for (const [id, day] of rows) {
    if ((visits.get(id) ?? []).some((d) => d >= day)) came++;
    else if (booked.has(id)) bk++;
  }
  return { contacted: rows.length, came, booked: bk };
};

/** since 이후 연락한 분 중 그 뒤 오신 분 · 아직 안 오셨지만 예약이 잡힌 분. visits = 손님별 방문일. */
export function contactEffect(
  contacts: ContactRow[],
  visits: Map<string, string[]>,
  booked: Set<string>,
  since: string,
): Effect {
  return tally([...firstContacts(contacts, since)], visits, booked);
}

/**
 * 손님 갈래별 — 연락하던 때 첫 방문 손님(그 전 방문 1회)이었나, 2회 이상이었나. 첫 방문 안부가
 * 들어온 뒤로 두 갈래의 결과가 다를 수 있어 나눠 본다(통계 '더 보기').
 */
export function contactEffectByGroup(
  contacts: ContactRow[],
  visits: Map<string, string[]>,
  booked: Set<string>,
): { first: Effect; repeat: Effect } {
  const first: [string, string][] = [];
  const repeat: [string, string][] = [];
  for (const row of firstContacts(contacts)) {
    const before = (visits.get(row[0]) ?? []).filter((d) => d < row[1]).length;
    if (before === 1) first.push(row);
    else if (before >= 2) repeat.push(row);
  }
  return { first: tally(first, visits, booked), repeat: tally(repeat, visits, booked) };
}

/** 첫 방문 안부가 처음 뜬 날 — 기능을 켠 2026-10-12 에 '첫 방문 14일 안'이던 손님부터. */
export const HELLO_SINCE = '2026-09-28';

/**
 * 첫 방문 손님 — 안부를 보낸 분과 안 보낸 분 중 다시 오신 분(두 번째 방문). 첫 방문이 since 이후인 분만.
 * 첫 방문 뒤 시간이 지나야 결과가 나오므로 몇 달 쌓여야 견줄 만하다(화면 ? 에 밝힌다).
 */
export function helloEffect(
  contacts: ContactRow[],
  visits: Map<string, string[]>,
  since = HELLO_SINCE,
): { sent: { n: number; back: number }; unsent: { n: number; back: number } } {
  const contacted = firstContactsAfterFirst(contacts, visits);
  const sent = { n: 0, back: 0 };
  const unsent = { n: 0, back: 0 };
  for (const [id, ds] of visits) {
    if (!ds.length || ds[0] < since) continue;
    const g = contacted.has(id) ? sent : unsent;
    g.n++;
    if (ds.length >= 2) g.back++;
  }
  return { sent, unsent };
}

/** 첫 방문 뒤(두 번째 방문 전)에 연락한 손님 — 안부를 받은 분. */
function firstContactsAfterFirst(contacts: ContactRow[], visits: Map<string, string[]>): Set<string> {
  const out = new Set<string>();
  for (const [id, day] of firstContacts(contacts)) {
    const ds = visits.get(id) ?? [];
    if (ds.length && day >= ds[0] && (ds.length < 2 || day <= ds[1])) out.add(id);
  }
  return out;
}
