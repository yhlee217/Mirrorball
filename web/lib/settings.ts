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

export function isLapsed(c: { last_visit: string | null; visit_count: number }, s: TenantSettings): boolean {
  const days = c.last_visit ? Math.floor((Date.now() - new Date(c.last_visit).getTime()) / DAY) : Infinity;
  return days > s.lapsed_months * 30 || (days > s.lapsed_soft_months * 30 && c.visit_count < s.lapsed_soft_visits);
}
