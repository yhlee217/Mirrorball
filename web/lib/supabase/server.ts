import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { cookies } from 'next/headers';

// 요청 컨텍스트(쿠키)로 인증된 서버 클라이언트. RLS 가 auth.uid() 기준으로 적용된다.
// Next 15 부터 cookies() 는 기다려 읽는다(개선 계획 v14 P1) — 그래서 이 함수도 async, 부르는 곳은 await.
export async function supabaseServer() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // Server Component 에서 호출되면 무시(미들웨어가 세션 갱신 담당)
          }
        },
      },
    },
  );
}

/** 서버 클라이언트 타입 — lib 함수들이 인자로 받는다. */
export type ServerClient = Awaited<ReturnType<typeof supabaseServer>>;
