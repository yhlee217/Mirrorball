import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';

// 소개 저장 — 인증 사용자의 테넌트 profiles 업데이트(RLS: profile_owner).
export async function POST(request: Request) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) return NextResponse.json({ error: 'no tenant' }, { status: 400 });

  const body = await request.json();
  const { error } = await supabase
    .from('profiles')
    .update({
      tagline: typeof body.tagline === 'string' ? body.tagline : null,
      bio: typeof body.bio === 'string' ? body.bio : null,
      location: typeof body.location === 'string' ? body.location : null,
      services: Array.isArray(body.services) ? body.services : [],
      faq: Array.isArray(body.faq) ? body.faq : [],
      updated_at: new Date().toISOString(),
    })
    .eq('tenant_id', (mem as { tenant_id: string }).tenant_id);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
