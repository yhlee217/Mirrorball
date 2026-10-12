import { addDays, dowMon } from './week';
import { daysBetween } from './briefing';

/**
 * 휴무 — 디자이너가 설정에서 정한 쉬는 날(정기 휴무 요일 + 휴가·임시 휴무 기간).
 *
 * 통계는 '영업한 날'끼리 견준다. 이틀 쉰 주를 그냥 전주와 견주면 손님이 줄어든 것처럼 읽히고,
 * 휴가 간 요일은 한산한 요일로 잘못 꼽힌다.
 *
 * 영업한 날 = 쉬는 날로 정하지 않은 날, 또는 정했어도 실제로 방문이 있었던 날. 쉬는 요일을
 * 바꿨거나 그날 따로 나와 일했다면 기록이 설정보다 사실에 가깝다.
 */
export type OffDays = { off_weekdays: number[]; off_dates: { from: string; to: string }[] };

export const hasOffDays = (s: OffDays): boolean => s.off_weekdays.length > 0 || s.off_dates.length > 0;

/** 휴가·임시 휴무 기간 안인가(정기 휴무 요일은 따로). */
export function inVacation(date: string, s: OffDays): boolean {
  return s.off_dates.some((r) => date >= r.from && date <= r.to);
}

/** 쉬는 날로 정한 날인가 — 정기 휴무 요일이거나 휴가 기간. */
export function isOffDay(date: string, s: OffDays): boolean {
  return s.off_weekdays.includes(dowMon(date)) || inVacation(date, s);
}

/** [start, end] 중 영업한 날 수. visited = 방문이 있었던 날짜들. */
export function workedDays(start: string, end: string, s: OffDays, visited: Set<string>): number {
  let n = 0;
  for (let d = start; d <= end; d = addDays(d, 1)) if (!isOffDay(d, s) || visited.has(d)) n++;
  return n;
}

/** [start, end] 의 요일별(월=0) 영업한 날 수 — 요일 × 시간대를 '영업한 날 하루 평균'으로 내는 분모. */
export function workedByWeekday(start: string, end: string, s: OffDays, visited: Set<string>): number[] {
  const out = [0, 0, 0, 0, 0, 0, 0];
  for (let d = start; d <= end; d = addDays(d, 1)) if (!isOffDay(d, s) || visited.has(d)) out[dowMon(d)]++;
  return out;
}

/** [start, end] 안의 휴가 일수. off_dates 는 설정에서 겹치지 않게 합쳐 둔다(lib/settings cleanOffDates). */
function vacationDaysIn(start: string, end: string, s: OffDays): number {
  let n = 0;
  for (const r of s.off_dates) {
    const a = r.from > start ? r.from : start;
    const b = r.to < end ? r.to : end;
    if (a <= b) n += daysBetween(a, b) + 1;
  }
  return n;
}

/**
 * d 뒤로 '휴가를 빼고' window 일이 되는 날 — '90일 안에 다시 오셨나'의 끝.
 * 2주 휴가가 끼면 손님은 그만큼 늦게 올 수밖에 없다. 정기 휴무는 늘 있는 일이라 늘리지 않는다
 * (평소 주기에 이미 들어 있다). 늘린 구간에 또 휴가가 걸릴 수 있어 몇 번 되풀이한다.
 */
export function windowEnd(d: string, window: number, s: OffDays): string {
  let end = addDays(d, window);
  if (!s.off_dates.length) return end;
  let extra = 0;
  for (let i = 0; i < 6; i++) {
    const n = vacationDaysIn(addDays(d, 1), end, s);
    if (n === extra) break;
    extra = n;
    end = addDays(d, window + extra);
  }
  return end;
}
