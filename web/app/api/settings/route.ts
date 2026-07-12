export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { mergeSettings } from '@/lib/settings';

// 판정 기준(settings) + 매장/디자이너 이름 저장 — 인증 사용자의 테넌트(RLS: tenant_self).
export async function POST(request: Request) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) return NextResponse.json({ error: 'no tenant' }, { status: 400 });
  const tid = (mem as { tenant_id: string }).tenant_id;

  const body = await request.json();
  const update: Record<string, unknown> = { settings: mergeSettings(body.settings) };
  if (typeof body.designer_name === 'string') update.designer_name = body.designer_name.trim() || null;
  if (typeof body.salon_name === 'string' && body.salon_name.trim()) update.salon_name = body.salon_name.trim();

  const { error } = await supabase.from('tenants').update(update).eq('id', tid);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
