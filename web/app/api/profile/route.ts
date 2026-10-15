export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { getTenantId } from '@/lib/tenant';

// 소개 저장 — 인증 사용자의 테넌트 profiles 업데이트(RLS: profile_owner).
export async function POST(request: Request) {
  const supabase = await supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  // 화면이 보여 주는 매장과 같은 매장(lib/tenant getTenantId) — 전에는 정렬 없이 첫 소속이라, 데모와 실제 매장에 함께
  // 속한 계정은 다른 매장에 저장될 수 있었다(개선 계획 v11 P0).
  const tenantId = await getTenantId(supabase);
  if (!tenantId) return NextResponse.json({ error: 'no tenant' }, { status: 400 });

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
    .eq('tenant_id', tenantId);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
