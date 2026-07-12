// 테넌트 판정 기준(설정). 홈·고객필터·알림이 이 값으로 VIP·이탈 등을 판정한다.
export type TenantSettings = {
  vip_won: number; // VIP: 누적 매출 이상(원)
  vip_visits: number; // VIP: 방문 횟수 이상
  lapsed_months: number; // 이탈: N개월 초과 미방문이면 무조건 제외
  lapsed_soft_months: number; // 이탈(저방문): M개월 초과 &
  lapsed_soft_visits: number; //   방문 K회 미만이면 제외
  revenue_mid: number; // 매출 구간 경계(중, 원)
  revenue_high: number; // 매출 구간 경계(상, 원)
  booking_days_ahead: number; // 다가오는 예약 표시 기간(일)
};

export const DEFAULT_SETTINGS: TenantSettings = {
  vip_won: 1000000,
  vip_visits: 10,
  lapsed_months: 12,
  lapsed_soft_months: 6,
  lapsed_soft_visits: 3,
  revenue_mid: 500000,
  revenue_high: 1000000,
  booking_days_ahead: 14,
};

const KEYS = Object.keys(DEFAULT_SETTINGS) as (keyof TenantSettings)[];

export function mergeSettings(raw: unknown): TenantSettings {
  const out = { ...DEFAULT_SETTINGS };
  if (raw && typeof raw === 'object') {
    for (const k of KEYS) {
      const v = (raw as Record<string, unknown>)[k];
      if (typeof v === 'number' && Number.isFinite(v) && v >= 0) out[k] = v;
    }
  }
  return out;
}

const DAY = 86400000;

export function isVip(c: { total_won: number; visit_count: number }, s: TenantSettings): boolean {
  return (c.total_won || 0) >= s.vip_won || c.visit_count >= s.vip_visits;
}

export function isLapsed(c: { last_visit: string | null; visit_count: number }, s: TenantSettings): boolean {
  const days = c.last_visit ? Math.floor((Date.now() - new Date(c.last_visit).getTime()) / DAY) : Infinity;
  return days > s.lapsed_months * 30 || (days > s.lapsed_soft_months * 30 && c.visit_count < s.lapsed_soft_visits);
}
