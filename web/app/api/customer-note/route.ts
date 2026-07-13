export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';

// 고객 메모·취향 태그 저장 — RLS(tenant_rw)로 본인 테넌트 고객만 수정 가능.
export async function POST(request: Request) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  const body = await request.json();
  const id = body.customer_id;
  if (!id || typeof id !== 'string') return NextResponse.json({ error: 'no id' }, { status: 400 });

  const memo = typeof body.memo === 'string' ? body.memo.slice(0, 2000) : null;
  const tags = Array.isArray(body.prefer_tags)
    ? [...new Set(body.prefer_tags.filter((t: unknown) => typeof t === 'string' && (t as string).trim()).map((t: string) => t.trim()))].slice(0, 20)
    : [];

  const { error } = await supabase.from('customers').update({ memo, prefer_tags: tags }).eq('id', id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
