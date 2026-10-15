/**
 * 보안 응답 헤더(개선 계획 v14 P0) — next.config.mjs 가 모든 경로(화면 · API)에 붙인다.
 * 손님 이름 · 번호를 보여 주는 앱인데 헤더가 하나도 없었다(2026-10-15 실사).
 *
 *   틀 넣기 금지     — 다른 사이트가 앱을 iframe 에 넣어 누르게 하는 것(클릭재킹). CSP frame-ancestors + X-Frame-Options.
 *   nosniff          — 엉뚱한 파일을 스크립트로 읽히지 않게.
 *   same-origin      — 손님 상세 주소(/customer/<id>)가 바깥 사이트로 Referer 에 실려 가지 않게.
 *   Permissions      — 카메라 · 마이크 · 위치 · 결제 · USB 를 쓰지 않는다(공유 · 클립보드는 그대로).
 *   HSTS             — 늘 https 로.
 *
 * 콘텐츠 보안 정책(CSP) 전체는 '보고만'(Report-Only) — 막지 않고, 어긋나면 운영 기록에 남긴다(api/csp-report,
 * components/csp-watch, 0026). 한 주 어긋남이 없으면 막기로 바꾼다. 'unsafe-inline' 은 Next 가 화면을 여는 인라인
 * 스크립트 때문 — Next 14 의 nonce 방식은 알려진 XSS 가 있어 쓰지 않는다(GHSA-ffhc-5mcf-pf4q).
 */

/** Supabase 주소의 출처(https://xxx.supabase.co) — 없거나 이상하면 *.supabase.co. */
export function supabaseOrigin(url) {
  try {
    return url ? new URL(url).origin : 'https://*.supabase.co';
  } catch {
    return 'https://*.supabase.co';
  }
}

export function cspReportOnly(supabaseUrl) {
  const sb = supabaseOrigin(supabaseUrl);
  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data: blob: ${sb}`,
    "font-src 'self' data:",
    `connect-src 'self' ${sb}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "object-src 'none'",
    "manifest-src 'self'",
    "worker-src 'self'",
    'report-uri /api/csp-report',
  ].join('; ');
}

export function securityHeaders(supabaseUrl) {
  return [
    { key: 'Content-Security-Policy', value: "frame-ancestors 'none'" }, // 이것만은 바로 막는다 — 화면 동작과 무관
    { key: 'Content-Security-Policy-Report-Only', value: cspReportOnly(supabaseUrl) },
    { key: 'X-Frame-Options', value: 'DENY' },
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'Referrer-Policy', value: 'same-origin' },
    { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=(), payment=(), usb=()' },
    { key: 'Strict-Transport-Security', value: 'max-age=31536000' },
  ];
}
