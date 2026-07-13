export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { supabaseServer } from '@/lib/supabase/server';
import { mergeSettings } from '@/lib/settings';

// 판정 기준(settings) + 매장/디자이너 이름 저장.
// tenants 는 멤버 직접 쓰기가 잠겨(RLS FOR SELECT, 마이그레이션 0008) 있으므로, 인증으로
// '본인 테넌트'를 확인한 뒤 화이트리스트 컬럼만 service_role 로 기록한다. plan/dek_wrapped/slug
// 등 민감 컬럼은 손대지 않는다(M1).
export async function POST(request: Request) {
  const auth = supabaseServer();
  const {
    data: { user },
  } = await auth.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  // 본인 소속 테넌트 확인은 RLS 로(자기 멤버십만 조회됨) → tid 는 반드시 본인 것.
  const { data: mem } = await auth.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) return NextResponse.json({ error: 'no tenant' }, { status: 400 });
  const tid = (mem as { tenant_id: string }).tenant_id;

  const body = await request.json();
  const update: Record<string, unknown> = { settings: mergeSettings(body.settings) };
  if (typeof body.designer_name === 'string') update.designer_name = body.designer_name.trim() || null;
  if (typeof body.salon_name === 'string' && body.salon_name.trim()) update.salon_name = body.salon_name.trim();

  // 화이트리스트 컬럼만 service_role 로 기록(tenants 쓰기 잠금 우회는 서버만).
  const admin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { persistSession: false } },
  );
  const { error } = await admin.from('tenants').update(update).eq('id', tid);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
