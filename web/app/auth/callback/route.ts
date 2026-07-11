import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';

// 매직링크 콜백: 코드를 세션으로 교환 후 홈으로.
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get('code');
  if (code) {
    const supabase = supabaseServer();
    await supabase.auth.exchangeCodeForSession(code);
  }
  return NextResponse.redirect(origin);
}
