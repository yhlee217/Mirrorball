import { txKind } from './tx';
import { addDays, dowMon } from './week';
import { daysBetween } from './week';
import { windowEnd, workedByWeekday, type OffDays } from './offdays';

export { dowMon };

/**
 * 통계를 '변화'로(UX 계획 P2) — 평생 누적 숫자는 보고 나서 할 게 없다. 최근 신규가 다시 오는지(D2),
 * 언제 바쁜지(D4), 어떤 시술이 손님을 다시 부르는지(D5), 손님이 줄고 있는지(D3)를 센다.
 * 화면(app/stats/page.tsx)은 결과를 놓기만 한다.
 *
 * 기준일(asOf)은 오늘이 아니라 마지막 수집일이다. 수집 뒤 날짜는 비어 있어서, 오늘로 세면
 * 덜 찬 기간을 다 찬 것처럼 읽게 된다.
 *
 * 휴무(설정)를 반영한다 — 요일 × 시간대는 '영업한 날 하루 평균'으로, '90일 안에 다시'는 휴가 기간만큼
 * 늘려서 센다(lib/offdays.ts). 휴무가 없으면 예전과 같은 숫자가 나온다.
 */

const NO_OFF: OffDays = { off_weekdays: [], off_dates: [] };

/** 다시 오셨는지 보는 기간 — 표준 주기 중 가장 긴 펌(90일, lib/care-cycle)까지 들어오게. */
export const BACK_DAYS = 90;

export type TrendTx = {
  customer_id: string | null;
  date: string | null;
  time?: string | null;
  kind: string | null;
  service: string | null;
};
export type Visit = { customer_id: string; date: string; time: string | null };

/** 시술 거래 → 방문. 같은 손님·같은 날은 한 번, 시각은 그날 가장 이른 것(방문 관리와 같은 기준). */
export function toVisits(tx: TrendTx[]): Visit[] {
  const m = new Map<string, Visit>();
  for (const t of tx) {
    if (!t.customer_id || !t.date || txKind(t.kind, t.service) !== 'service') continue;
    const time = t.time && t.time.trim() ? t.time.trim() : null;
    const k = `${t.customer_id}|${t.date}`;
    const v = m.get(k);
    if (!v) m.set(k, { customer_id: t.customer_id, date: t.date, time });
    else if (time && (!v.time || time < v.time)) v.time = time;
  }
  return [...m.values()];
}

/** 손님별 방문 날짜(오름차순). */
export function datesByCustomer(visits: Visit[]): Map<string, string[]> {
  const m = new Map<string, string[]>();
  for (const v of visits) {
    const a = m.get(v.customer_id);
    if (a) a.push(v.date);
    else m.set(v.customer_id, [v.date]);
  }
  for (const a of m.values()) a.sort();
  return m;
}

/** d 바로 다음 방문이 end 까지 있으면 그 날짜. dates 는 오름차순. */
function nextWithin(dates: string[] | undefined, d: string, end: string): string | null {
  if (!dates) return null;
  for (const x of dates) if (x > d) return x <= end ? x : null;
  return null;
}

/** 'YYYY-MM' 의 마지막 날. */
function monthEnd(ym: string): string {
  const [y, m] = ym.split('-').map(Number);
  return new Date(Date.UTC(y, m, 0)).toISOString().slice(0, 10);
}

/** asOf 가 속한 달 바로 앞의 n개월(오래된 것부터). */
function monthsBefore(asOf: string, n: number): string[] {
  const [y, m] = asOf.split('-').map(Number);
  const out: string[] = [];
  for (let i = n; i >= 1; i--) {
    const d = new Date(Date.UTC(y, m - 1 - i, 1));
    out.push(`${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`);
  }
  return out;
}

export type Cohort = { month: string; label: string; total: number; back: number; open: boolean };

/**
 * 신규 손님이 다시 오나(D2) — 첫 방문 달별 'N명 중 M명이 90일 안에 다시'.
 * 달마다 같은 기간을 줘야 견줄 수 있다('한 번이라도 다시'로 세면 오래된 달일수록 유리하다).
 * 90일이 아직 다 안 지난 달은 open — 숫자가 더 늘 수 있다.
 * 디자이너당 신규가 한 달 열댓 명이라 %는 한두 명에 크게 흔들린다 → 화면은 'N명 중 M명'으로 쓴다.
 * 첫 방문은 실고객의 first_visit(워커 집계 — 홈 '첫 방문'과 같은 값). medianDays 는 다시 오신
 * 분들이 첫 방문 뒤 며칠 만에 오셨는지(중앙값). 90일 사이에 휴가가 끼면 그만큼 늘려서 본다.
 */
export function newcomerCohorts(
  firsts: { id: string; first_visit: string | null }[],
  byCust: Map<string, string[]>,
  asOf: string,
  off: OffDays = NO_OFF,
  months = 6,
  window = BACK_DAYS,
): { cohorts: Cohort[]; medianDays: number | null } {
  const ms = monthsBefore(asOf, months);
  const at = new Map(ms.map((m, i) => [m, i]));
  const cohorts: Cohort[] = ms.map((m) => ({
    month: m,
    label: `${Number(m.slice(5))}월`,
    total: 0,
    back: 0,
    open: windowEnd(monthEnd(m), window, off) > asOf,
  }));
  const gaps: number[] = [];
  for (const c of firsts) {
    const i = c.first_visit ? at.get(c.first_visit.slice(0, 7)) : undefined;
    if (i === undefined || !c.first_visit) continue;
    cohorts[i].total++;
    const next = nextWithin(byCust.get(c.id), c.first_visit, windowEnd(c.first_visit, window, off));
    if (next) {
      cohorts[i].back++;
      gaps.push(daysBetween(c.first_visit, next));
    }
  }
  gaps.sort((a, b) => a - b);
  return { cohorts, medianDays: gaps.length ? gaps[Math.floor(gaps.length / 2)] : null };
}

export const DOW_MON = ['월', '화', '수', '목', '금', '토', '일'] as const;
export const BANDS = ['오전', '12–14시', '14–16시', '16–18시', '18시~'] as const;

/** 시각 → 시간대 칸(오전·12·14·16·18시~). 읽을 수 없으면 null. */
export function bandOf(time: string | null): number | null {
  const h = time ? Number(/^(\d{1,2}):/.exec(time)?.[1]) : NaN;
  if (!Number.isFinite(h)) return null;
  return h < 12 ? 0 : h < 14 ? 1 : h < 16 ? 2 : h < 18 ? 3 : 4;
}

/** 영업한 날이 이만큼 안 되는 요일은 '가장 붐빔 · 한산'을 고를 때 견주지 않는다 — 며칠의 평균은 한 날에 크게 흔들린다. */
export const MIN_HEAT_DAYS = 4;

/**
 * 언제 바쁘고 언제 한가하지(D4) — 요일 × 시간대. grid[시간대][요일(월=0)] 은 방문 수,
 * avg 는 그 요일에 영업한 날 하루 평균(days = 요일별 영업한 날 수). 휴가 간 요일이 한산한 요일로
 * 꼽히지 않게 평균으로 견준다.
 * 정기 휴무 요일(off_weekdays)은 따로 나와 일한 날이 있어도 휴무(off)로 두고 칸 · 평균에서 뺀다 — 전에는 그날만
 * '영업한 날'로 세어, 예외로 이틀 일한 수요일이 이틀 평균으로 '가장 붐빔'에 꼽혔다(2026-10-21 hayewoni, 화 · 수 휴무).
 * 뺀 날 · 방문은 offWorked · offVisits 로 따로 센다. 영업한 날이 MIN_HEAT_DAYS 보다 적은 요일(긴 휴가 등)은 thin —
 * 칸은 칠하되 '가장 붐빔 · 한산' 비교와 진하기 기준(max)에서 뺀다.
 * 시각은 그날 첫 시술 시각. 시각이 비어 있는 방문은 칸에 넣지 않고 noTime 으로 따로 센다
 * (2026-10-12 실측: 시각 채움 95~99%).
 */
export function weekHeat(
  visits: Visit[],
  since: string,
  asOf: string,
  off: OffDays = NO_OFF,
): {
  grid: number[][]; avg: number[][]; days: number[]; off: boolean[]; thin: boolean[]; max: number; total: number;
  noTime: number; offWorked: number; offVisits: number;
} {
  const isOffW = DOW_MON.map((_, d) => off.off_weekdays.includes(d));
  const grid = BANDS.map(() => DOW_MON.map(() => 0));
  const visited = new Set<string>();
  const offDates = new Set<string>();
  let total = 0;
  let noTime = 0;
  let offVisits = 0;
  for (const v of visits) {
    if (v.date < since || v.date > asOf) continue;
    const d = dowMon(v.date);
    if (isOffW[d]) {
      offVisits++;
      offDates.add(v.date);
      continue;
    }
    visited.add(v.date);
    const b = bandOf(v.time);
    if (b === null) {
      noTime++;
      continue;
    }
    grid[b][d]++;
    total++;
  }
  const days = workedByWeekday(since, asOf, off, visited).map((n, d) => (isOffW[d] ? 0 : n));
  const avg = grid.map((row) => row.map((n, d) => (days[d] ? n / days[d] : 0)));
  const thin = days.map((n, d) => !isOffW[d] && n > 0 && n < MIN_HEAT_DAYS);
  const counted = (d: number) => !isOffW[d] && !thin[d];
  return {
    grid,
    avg,
    days,
    off: isOffW,
    thin,
    max: Math.max(0, ...avg.flatMap((row) => row.filter((_, d) => counted(d)))),
    total,
    noTime,
    offWorked: offDates.size,
    offVisits,
  };
}

export type SvcRow = { service: string; count: number; avg: number; back: number; base: number };

/**
 * 어떤 시술이 남는 장사인가(D5) — 시술별 건수·객단가·90일 안에 다시 오신 비율(since~asOf).
 * 객단가는 받은 금액 그대로 — 선불 잔액으로 결제한 건도 시술 가격은 같다.
 * 다시 오신 비율은 90일이 다 지난 시술만 센다(최근 시술은 아직 돌아올 시간이 안 됐다).
 * 워크인 집계('손님')는 여러 사람이 한 번호를 써서 '다시 옴'이 부풀므로 실고객만 센다.
 * 충전·제품은 시술이 아니라 뺀다. 90일 사이에 휴가가 끼면 그만큼 늘려서 본다.
 */
export function serviceTable(
  tx: (TrendTx & { amount_won: number | null })[],
  byCust: Map<string, string[]>,
  realIds: Set<string>,
  since: string,
  asOf: string,
  off: OffDays = NO_OFF,
  top = 6,
  window = BACK_DAYS,
): SvcRow[] {
  const acc = new Map<string, { count: number; sum: number; back: number; base: number }>();
  for (const t of tx) {
    if (!t.date || t.date < since || t.date > asOf || txKind(t.kind, t.service) !== 'service') continue;
    const s = (t.service || '').trim();
    if (!s) continue;
    const e = acc.get(s) ?? { count: 0, sum: 0, back: 0, base: 0 };
    e.count++;
    e.sum += t.amount_won || 0;
    const end = t.customer_id && realIds.has(t.customer_id) ? windowEnd(t.date, window, off) : null;
    if (t.customer_id && end && end <= asOf) {
      e.base++;
      if (nextWithin(byCust.get(t.customer_id), t.date, end)) e.back++;
    }
    acc.set(s, e);
  }
  return [...acc.entries()]
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, top)
    .map(([service, e]) => ({ service, count: e.count, avg: Math.round(e.sum / e.count), back: e.back, base: e.base }));
}

/**
 * 손님이 빠져나가고 있나(D3) — 활성 고객(그날까지 90일 안에 방문한 실고객) 수. 지난 달들의
 * 말일마다 세고, 마지막 점은 수집일. 이탈 위험의 '추이'는 지난 시점의 판정이 저장돼 있지 않아
 * 세지 않는다.
 */
export function activeTrend(
  byCust: Map<string, string[]>,
  realIds: Set<string>,
  asOf: string,
  points = 6,
  window = BACK_DAYS,
): { date: string; label: string; count: number }[] {
  const ends = [...monthsBefore(asOf, points - 1).map(monthEnd), asOf];
  return ends.map((p, i) => {
    const from = addDays(p, -window);
    let count = 0;
    for (const id of realIds) {
      const ds = byCust.get(id);
      if (ds && ds.some((x) => x > from && x <= p)) count++;
    }
    const [, m, d] = p.split('-').map(Number);
    return { date: p, label: i === ends.length - 1 ? `${m}.${d}` : `${m}월`, count };
  });
}

/**
 * 통계가 받는 거래 기간(개선 계획 v12 P0) — 가장 멀리 보는 계산(추천 적중률)이 2년(730일). 수집이 한 달까지 밀려도
 * 그 2년이 다 들어오게 31일을 더 받는다. 전에는 매장 거래 전부를 받았다(해마다 느려진다).
 */
export const STATS_DAYS = 730 + 31;

/**
 * 2년보다 오래된 이력이 답을 바꾸는 계산을 위한 방문 날짜(손님별, 오름차순) — 손님 표의 첫 방문을 앞에 더하고(첫 방문 안부
 * 효과가 맨 앞 날짜를 '첫 방문'으로 읽는다), 연락한 분은 전체 이력으로 바꾼다(연락 효과가 연락 전 방문 수로 첫 방문 손님 ·
 * 단골을 가른다). since = 받은 거래의 첫날 — 첫 방문이 그 뒤면 이미 들어 있다.
 */
export function withOlderHistory(
  byCust: Map<string, string[]>,
  firsts: { id: string; first_visit: string | null }[],
  full: Map<string, string[]>,
  since: string,
): Map<string, string[]> {
  const out = new Map(byCust);
  for (const c of firsts) {
    const f = c.first_visit?.slice(0, 10);
    if (!f || f >= since) continue;
    const ds = out.get(c.id) ?? [];
    if (!ds.length || ds[0] > f) out.set(c.id, [f, ...ds]);
  }
  for (const [id, ds] of full) out.set(id, ds);
  return out;
}
