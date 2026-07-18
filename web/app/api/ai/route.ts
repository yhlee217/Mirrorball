export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { templateImprove } from '@/lib/coach';

// 온디맨드 문구 다듬기(무료 템플릿). Cloudflare Workers AI 바인딩 연결은 배포 안정화 후
// 별도 단계에서 붙인다(@cloudflare/next-on-pages 의 getRequestContext 로 env.AI 접근).
// 자동 호출 금지 — 디자이너가 '다듬기' 누를 때만 호출된다(사용량이 작게 유지됨).
export async function POST(request: Request) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  const body = await request.json();
  const kind = String(body.kind || '');
  const ctx = (body.context && typeof body.context === 'object' ? body.context : {}) as Record<string, string>;

  return NextResponse.json({ text: templateImprove(kind, ctx), source: 'template' });
}
