import { awayDays } from './offdays';

// 테넌트 판정 기준(설정). 홈·고객필터·알림이 이 값으로 VIP·이탈 등을 판정한다.
export type TenantSettings = {
  vip_won: number; // VIP: 누적 매출 이상(원)
  vip_visits: number; // VIP: 누적 방문 횟수 이상(오래 다니신 분)
  vip_recent_months: number; // VIP: 최근 N개월 기준(3·6·12 중 하나 — 집계 창이 그 3개다)
  vip_recent_visits: number; //   그 기간에 K회 이상이면 VIP(자주 오시는 분)
  lapsed_months: number; // 이탈: N개월 초과 미방문이면 무조건 제외
  lapsed_soft_months: number; // 이탈(저방문): M개월 초과 &
  lapsed_soft_visits: number; //   방문 K회 미만이면 제외
  revenue_mid: number; // 매출 구간 경계(중, 원)
  revenue_high: number; // 매출 구간 경계(상, 원)
  booking_days_ahead: number; // 다가오는 예약 표시 기간(일)
  // 휴무 — 통계가 '영업한 날'끼리 견주는 데 쓴다(lib/offdays.ts).
  off_weekdays: number[]; // 정기 휴무 요일, 월=0 … 일=6
  off_dates: { from: string; to: string }[]; // 휴가·임시 휴무 기간(YYYY-MM-DD, 양 끝 포함)
};

export const DEFAULT_SETTINGS: TenantSettings = {
  vip_won: 1000000,
  vip_visits: 20, // 최근 활동 축이 생겨 '자주 오시는 분'을 따로 잡으므로 누적 기준은 높였다
  vip_recent_months: 6,
  vip_recent_visits: 4,
  lapsed_months: 12,
  lapsed_soft_months: 6,
  lapsed_soft_visits: 3,
  revenue_mid: 500000,
  revenue_high: 1000000,
  booking_days_ahead: 31,
  off_weekdays: [],
  off_dates: [],
};

type NumKey = { [K in keyof TenantSettings]: TenantSettings[K] extends number ? K : never }[keyof TenantSettings];
const NUM_KEYS = (Object.keys(DEFAULT_SETTINGS) as (keyof TenantSettings)[]).filter(
  (k): k is NumKey => typeof DEFAULT_SETTINGS[k] === 'number',
);

/** 휴가 기간을 몇 개까지 둘지 — 오래된 것부터 버린다(통계는 길어야 1~2년을 본다). */
export const OFF_DATES_MAX = 60;

/** 'YYYY-MM-DD' 이고 달력에 있는 날인가(2026-02-30 같은 날은 아니다). */
const isDay = (s: unknown): s is string => {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const t = Date.parse(s + 'T00:00:00Z');
  return !Number.isNaN(t) && new Date(t).toISOString().slice(0, 10) === s;
};

/** 정기 휴무 요일 — 0~6 정수만, 중복 없이 정렬. */
export function cleanWeekdays(raw: unknown): number[] {
  if (!Array.isArray(raw)) return [];
  return [...new Set(raw.filter((d): d is number => Number.isInteger(d) && d >= 0 && d <= 6))].sort((a, b) => a - b);
}

/**
 * 휴가 기간 — 올바른 날짜만, 거꾸로 넣으면 뒤집고, 겹치거나 맞닿은 기간은 하나로 합친다.
 * 합쳐 두면 '며칠 쉬었나'를 셀 때 같은 날을 두 번 세지 않는다. 날짜순, 최근 OFF_DATES_MAX 개.
 */
export function cleanOffDates(raw: unknown): { from: string; to: string }[] {
  if (!Array.isArray(raw)) return [];
  const rs = raw
    .filter((r): r is { from: string; to: string } => !!r && typeof r === 'object' && isDay((r as { from?: unknown }).from) && isDay((r as { to?: unknown }).to))
    .map((r) => (r.from <= r.to ? { from: r.from, to: r.to } : { from: r.to, to: r.from }))
    .sort((a, b) => (a.from < b.from ? -1 : a.from > b.from ? 1 : 0));
  const out: { from: string; to: string }[] = [];
  for (const r of rs) {
    const last = out[out.length - 1];
    const next = last ? new Date(Date.parse(last.to + 'T00:00:00Z') + 86400000).toISOString().slice(0, 10) : '';
    if (last && r.from <= next) {
      if (r.to > last.to) last.to = r.to;
    } else out.push({ ...r });
  }
  return out.slice(-OFF_DATES_MAX);
}

export function mergeSettings(raw: unknown): TenantSettings {
  const out: TenantSettings = { ...DEFAULT_SETTINGS, off_weekdays: [], off_dates: [] };
  if (raw && typeof raw === 'object') {
    const r = raw as Record<string, unknown>;
    for (const k of NUM_KEYS) {
      const v = r[k];
      if (typeof v === 'number' && Number.isFinite(v) && v >= 0) out[k] = v;
    }
    out.off_weekdays = cleanWeekdays(r.off_weekdays);
    out.off_dates = cleanOffDates(r.off_dates);
  }
  return out;
}

/** VIP 판정에 쓰는 고객 필드. visits_* 는 워커가 미리 집계해 둔 최근 방문 횟수. */
export type VipInput = {
  total_won: number;
  visit_count: number;
  visits_90d?: number | null;
  visits_180d?: number | null;
  visits_365d?: number | null;
};

/** 설정한 기간에 해당하는 최근 방문 횟수. 집계 창은 90/180/365일 셋뿐이라 가까운 쪽으로 매핑. */
export function recentVisitsOf(c: VipInput, s: TenantSettings): number {
  const v = s.vip_recent_months <= 3 ? c.visits_90d : s.vip_recent_months <= 6 ? c.visits_180d : c.visits_365d;
  return v ?? 0;
}

/**
 * VIP = 세 축 중 하나라도 해당.
 *  1) 누적 매출이 큰 분  2) 오래 꾸준히 다니신 분(누적 방문)  3) 최근에 자주 오시는 분
 * 3번이 없으면 '6년간 10번'과 '올해만 10번'이 똑같이 취급돼 지금 챙겨야 할 단골이 묻힌다.
 */
export function isVip(c: VipInput, s: TenantSettings): boolean {
  if ((c.total_won || 0) >= s.vip_won) return true;
  if (c.visit_count >= s.vip_visits) return true;
  return s.vip_recent_visits > 0 && recentVisitsOf(c, s) >= s.vip_recent_visits;
}

/**
 * 이탈 판정 — 설정의 기간 넘게 안 오셨나. 디자이너가 쉰 휴가 기간은 '안 오신 기간'에 넣지 않는다
 * (lib/offdays awayDays — 그동안은 오고 싶어도 못 왔다).
 */
export function isLapsed(c: { last_visit: string | null; visit_count: number }, s: TenantSettings): boolean {
  const days = c.last_visit ? awayDays(c.last_visit.slice(0, 10), new Date(Date.now()).toISOString().slice(0, 10), s) : Infinity;
  return days > s.lapsed_months * 30 || (days > s.lapsed_soft_months * 30 && c.visit_count < s.lapsed_soft_visits);
}
