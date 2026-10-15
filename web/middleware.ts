import { type NextRequest, NextResponse } from 'next/server';
import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { securityHeaders } from './lib/security-headers.mjs';

// 보안 응답 헤더 — 미들웨어를 거치는 응답엔 next.config 의 headers 가 붙지 않는다(Cloudflare next-on-pages —
// 2026-10-15 로컬 workerd 로 확인: 로그인 화면에만 붙고 홈 · 설정 · API 엔 없었다). 그래서 여기서 직접 붙인다(개선 계획 v14 P0).
// 미들웨어를 안 거치는 곳(로그인 · 인증 콜백)은 next.config 가 붙인다.
const SECURITY = securityHeaders(process.env.NEXT_PUBLIC_SUPABASE_URL);

// 매 요청마다 Supabase 세션 쿠키를 갱신(만료 방지). App Router 표준 패턴.
export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  await supabase.auth.getUser();
  for (const h of SECURITY) response.headers.set(h.key, h.value);
  return response;
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|login|auth).*)'],
};
