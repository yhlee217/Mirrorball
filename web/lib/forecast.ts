import { txKind } from './tx';
import { addDays } from './week';
import { isOffDay, workedDays, type OffDays } from './offdays';

/**
 * 이번 달 마감 예상(UX 계획 D8) — '이 속도면 이번 달 얼마'.
 *
 * 처음 계획(지금까지 + 예약 × 객단가)은 버렸다. 예약은 마지막 수집 때까지 잡힌 것뿐이고, 예약 없이
 * 오는 손님은 아예 빠져 늘 낮게 나온다. 대신 지금까지의 흐름으로 센다:
 *   예상 = 지금까지 매출 + 시술 매출의 '영업한 날 하루 평균' × 남은 영업일
 * - 영업일은 휴무 설정을 반영한다(lib/offdays) — 쉬는 날까지 매출이 날 것처럼 세면 높게 나온다.
 * - 선불 충전은 하루에 몇십~몇백만원이 한꺼번에 들어와 하루 평균을 크게 흔든다. 그래서 속도에서
 *   빼고 들어온 만큼만 더한다(남은 기간의 충전은 예상하지 않는다 — 그만큼 보수적이다).
 * - 기준일은 마지막 수집일. 그 뒤 날짜는 아직 비어 있어 '남은 영업일'로 센다.
 * - 범위: 지난 6개월 각 달의 같은 날짜에 같은 식으로 예상했다면 실제와 얼마나 어긋났나. 어긋남의
 *   가운데(중앙값)로 예상을 바로잡고, 가장 작고 큰 어긋남으로 범위를 정한다. 디자이너마다 자기
 *   기록으로 정해진다(매출이 들쭉날쭉하면 범위가 넓다). 그런 달이 3개 이상일 때만 범위를 낸다.
 */

/** 영업일이 이만큼 지나야 보여준다 — 월초 며칠로 한 달을 점치면 크게 틀린다. */
export const MIN_WORKED = 5;
const BACK_MONTHS = 6;
const MIN_BACK = 3;

export type FcTx = {
  date: string | null;
  kind: string | null;
  service: string | null;
  amount_won: number | null;
  covered_won: number | null;
};

/** 실매출 = 금액 − 선불 잔액으로 결제된 금액(통계 '이번 달'과 같은 규칙). */
const net = (t: FcTx) => (t.amount_won || 0) - (t.covered_won || 0);

function monthEnd(ym: string): string {
  const [y, m] = ym.split('-').map(Number);
  return new Date(Date.UTC(y, m, 0)).toISOString().slice(0, 10);
}

export function shiftMonth(ym: string, k: number): string {
  const [y, m] = ym.split('-').map(Number);
  const d = new Date(Date.UTC(y, m - 1 + k, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

/** ym 달의 day 일 — 그 달에 없는 날이면 말일(31일 → 9월 30일). */
function dayIn(ym: string, day: number): string {
  const last = Number(monthEnd(ym).slice(8));
  return `${ym}-${String(Math.min(day, last)).padStart(2, '0')}`;
}

/** 남은 영업일 — (after, end] 중 쉬기로 정하지 않은 날. 아직 오지 않은 날이라 방문 기록은 없다. */
function plannedDays(after: string, end: string, off: OffDays): number {
  let n = 0;
  for (let d = addDays(after, 1); d <= end; d = addDays(d, 1)) if (!isOffDay(d, off)) n++;
  return n;
}

type Pace = { soFar: number; worked: number; remaining: number; pred: number };

/** ym 달을 cut(포함)까지의 기록으로 예상한다. */
function pace(tx: FcTx[], ym: string, cut: string, off: OffDays, visited: Set<string>): Pace {
  const start = `${ym}-01`;
  let svc = 0;
  let charges = 0;
  for (const t of tx) {
    if (!t.date || t.date < start || t.date > cut) continue;
    if (txKind(t.kind, t.service) === 'charge') charges += net(t);
    else svc += net(t);
  }
  const worked = workedDays(start, cut, off, visited);
  const remaining = plannedDays(cut, monthEnd(ym), off);
  const soFar = svc + charges;
  return { soFar, worked, remaining, pred: soFar + (worked > 0 ? (svc / worked) * remaining : 0) };
}

const median = (xs: number[]) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];

export type Forecast = {
  show: boolean; // 영업일이 MIN_WORKED 이상 지났나
  worked: number; // 이번 달 지금까지 영업한 날
  remaining: number; // 남은 영업일(수집일 다음 날부터 말일까지, 휴무 제외)
  soFar: number; // 지금까지 매출(충전 포함)
  center: number; // 마감 예상(지난 달들의 어긋남으로 바로잡은 값, 지금까지 매출 아래로는 안 내려간다)
  low: number | null; // 범위 — 바로잡을 근거(지난 달)가 3개 미만이면 null
  high: number | null;
  months: number; // 범위를 낸 지난 달 수
  lastMonth: number; // 지난달 전체 매출
};

/** ym(이번 달)의 마감 예상. asOf = 마지막 수집일 — 이번 달 전이면 이번 달 기록이 없다(show false). */
export function monthForecast(tx: FcTx[], ym: string, asOf: string, off: OffDays, visited: Set<string>): Forecast {
  const total = (m: string) => tx.reduce((s, t) => (t.date && t.date.slice(0, 7) === m ? s + net(t) : s), 0);
  const lastMonth = total(shiftMonth(ym, -1));
  const start = `${ym}-01`;
  if (asOf < start) {
    return { show: false, worked: 0, remaining: plannedDays(addDays(start, -1), monthEnd(ym), off), soFar: 0,
      center: 0, low: null, high: null, months: 0, lastMonth };
  }
  const cut = asOf > monthEnd(ym) ? monthEnd(ym) : asOf;
  const now = pace(tx, ym, cut, off, visited);
  const day = Number(cut.slice(8));
  const errs: number[] = [];
  for (let k = 1; k <= BACK_MONTHS; k++) {
    const m = shiftMonth(ym, -k);
    const p = pace(tx, m, dayIn(m, day), off, visited);
    const actual = total(m);
    if (p.worked >= MIN_WORKED && p.pred > 0 && actual > 0) errs.push((actual - p.pred) / p.pred);
  }
  const ok = errs.length >= MIN_BACK && now.remaining > 0;
  const at = (e: number) => Math.max(now.soFar, now.pred * (1 + e)); // 이미 번 것보다 적게 끝날 수는 없다
  return {
    show: now.worked >= MIN_WORKED,
    worked: now.worked,
    remaining: now.remaining,
    soFar: now.soFar,
    center: ok ? at(median(errs)) : now.pred,
    low: ok ? at(Math.min(...errs)) : null,
    high: ok ? at(Math.max(...errs)) : null,
    months: errs.length,
    lastMonth,
  };
}
