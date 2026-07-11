import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';

// 요청 컨텍스트(쿠키)로 인증된 서버 클라이언트. RLS 가 auth.uid() 기준으로 적용된다.
export function supabaseServer() {
  const cookieStore = cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
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
