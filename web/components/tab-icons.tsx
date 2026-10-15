/**
 * 하단 탭 아이콘 — 선으로 그린 흑백 아이콘(2026-10-15 "앱 하단에 아이콘들 흑백으로"). 색 이모지(🏠 👥 ⏳ ✅)는 폰마다
 * 모양 · 색이 달라 탭바만 알록달록했다. 선 색은 글자색(currentColor)을 따른다 — 고른 탭은 진하게, 나머지는 회색(.tab).
 * 화면 측정 견본(scripts/ui-audit/render.cjs)도 같은 아이콘을 그린다.
 */
export type TabIconName = 'home' | 'customers' | 'care' | 'visits';

const PATHS: Record<TabIconName, React.ReactNode> = {
  // 집
  home: (
    <>
      <path d="M3.5 10.5 12 3.5l8.5 7" />
      <path d="M5.5 9v10.5a1 1 0 0 0 1 1H10v-6h4v6h3.5a1 1 0 0 0 1-1V9" />
    </>
  ),
  // 두 사람 — 손님들
  customers: (
    <>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20.5a6.5 6.5 0 0 1 13 0" />
      <path d="M15.5 4.7a3.5 3.5 0 0 1 0 6.6" />
      <path d="M18 14.3a6.5 6.5 0 0 1 3.5 6.2" />
    </>
  ),
  // 모래시계 — 아직 안 오신 분(⏳ 과 같은 뜻)
  care: (
    <>
      <path d="M6 3h12M6 21h12" />
      <path d="M7.5 3c0 4.5 4.5 6 4.5 9s-4.5 4.5-4.5 9" />
      <path d="M16.5 3c0 4.5-4.5 6-4.5 9s4.5 4.5 4.5 9" />
    </>
  ),
  // 동그라미 안의 체크 — 다녀가신 분(✅ 과 같은 뜻)
  visits: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m8 12.4 2.8 2.8L16.2 9.8" />
    </>
  ),
};

export function TabIcon({ name }: { name: TabIconName }) {
  return (
    <svg viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {PATHS[name]}
    </svg>
  );
}
