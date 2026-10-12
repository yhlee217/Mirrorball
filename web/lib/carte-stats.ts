import { soonestCare } from './care-cycle';
import { agoWords, daysBetween, shortDate, spanWords } from './week';
import { windowEnd, type OffDays } from './offdays';

export { agoWords, shortDate };

/**
 * 카르테 숫자 타일 — 머리말('N회 방문 · 누적 X')과 같은 숫자를 또 보이던 타일을, 손님 앞에서
 * 바로 묻게 되는 것으로 바꿨다: 마지막 방문 · 다음 방문 · 잔액(또는 객단가) · 매출 순위.
 */

export type NextVisit =
  | { kind: 'booked'; date: string }
  | { kind: 'expected'; date: string; basis: string; estimated: boolean; overdueDays: number }
  | null;

/** 시술별 표준 주기 중 가장 짧은 것(lib/care-cycle soonestCare). 모르면 42일 — effectiveCycle 와 같은 기본값. */
function serviceCycle(services: (string | null)[]): { days: number; cat: string | null } {
  const best = soonestCare(services);
  return best ? { days: best.care.days, cat: best.care.cat } : { days: 42, cat: null };
}

/**
 * 다음 방문은 언제쯤일까(UX 계획 B2).
 *  1) 잡힌 예약이 있으면 그게 답이다.
 *  2) 방문 2회 이상: 마지막 방문 + 평소 주기(방문 간격 중앙값 — 워커의 revisit_cycle_days).
 *  3) 1회뿐: 그날 받은 시술의 표준 주기(lib/care-cycle.ts). 실측이 아니라 추정이라 그렇게 밝힌다.
 *     (2026-10-12 실측: 방문 2회 이상은 34~52% — 나머지 절반가량이 이 경우다.)
 * 그 사이 디자이너가 휴가를 갔으면 그만큼 늦춘다 — 그동안은 손님이 올 수 없었다(lib/offdays windowEnd).
 * overdueDays 는 예상일이 지났으면 지난 날수(아니면 0).
 */
export function nextVisit(o: {
  today: string;
  lastVisit: string | null;
  visitCount: number;
  cycleDays: number | null;
  lastServices: (string | null)[];
  bookedDate: string | null;
  off?: OffDays;
}): NextVisit {
  if (o.bookedDate) return { kind: 'booked', date: o.bookedDate };
  if (!o.lastVisit || o.visitCount < 1) return null;
  let days: number;
  let basis: string;
  let estimated: boolean;
  if (o.visitCount >= 2 && o.cycleDays && o.cycleDays > 0) {
    days = o.cycleDays;
    basis = `평소 ${spanWords(o.cycleDays)} 주기`;
    estimated = false;
  } else {
    const s = serviceCycle(o.lastServices);
    days = s.days;
    basis = s.cat ? `${s.cat} 기준 추정` : '추정';
    estimated = true;
  }
  const date = windowEnd(o.lastVisit, days, o.off ?? { off_weekdays: [], off_dates: [] });
  return { kind: 'expected', date, basis, estimated, overdueDays: Math.max(0, daysBetween(date, o.today)) };
}

/**
 * 누적 매출 상위 몇 %인가(UX 계획 B4). above = 나보다 매출이 큰 실고객 수, total = 실고객 수.
 * 같은 금액끼리는 같은 순위(가장 좋은 쪽)를 준다. 1등도 '상위 1%'로(0%는 어색하다).
 * 100 을 먼저 곱한다 — 7/100*100 은 7.000000000000001 이라 올림하면 8이 된다.
 */
export function rankPercent(above: number, total: number): number | null {
  if (!(total > 0) || above < 0 || above >= total) return null;
  return Math.max(1, Math.ceil(((above + 1) * 100) / total));
}
