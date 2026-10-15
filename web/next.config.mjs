import { securityHeaders } from './lib/security-headers.mjs';

/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // 화면 사이를 오갈 때 3분 안에 다시 연 화면은 받아 둔 것으로 바로 보여준다(기본 30초) — 탭을 오가며
    // 매번 뼈대 → 서버 렌더(전 고객 복호화)를 기다리지 않게. 수집이 주 1회라 그 사이 바뀔 숫자가 없고,
    // 손님 정보를 바꾸는 손잡이(메모 · 이탈 · 성별 · 사비 · 설정)는 router.refresh() 로 이 저장분을 비운다.
    // 앱을 다시 열 때(refresh-on-focus)도 비운다.
    staleTimes: { dynamic: 180 },
  },
  // 보안 응답 헤더 — 모든 경로(화면 · API)에(lib/security-headers.mjs, 개선 계획 v14 P0)
  async headers() {
    return [{ source: '/:path*', headers: securityHeaders(process.env.NEXT_PUBLIC_SUPABASE_URL) }];
  },
};
export default nextConfig;
