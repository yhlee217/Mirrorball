import { NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import { supabaseServer } from '@/lib/supabase/server';

// 데모 온보딩: 로그인 사용자에게 데모 테넌트+멤버십+운영 데이터를 생성.
// service_role 로 RLS 우회(서버 전용). PII 없이 운영 필드만 시드.
export async function POST() {
  const auth = supabaseServer();
  const {
    data: { user },
  } = await auth.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  const admin = createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
    { auth: { persistSession: false } },
  );

  const { data: existing } = await admin
    .from('memberships')
    .select('tenant_id')
    .eq('user_id', user.id)
    .maybeSingle();
  if (existing) return NextResponse.json({ ok: true, tenant_id: existing.tenant_id });

  const slug = 'demo-' + user.id.slice(0, 8);
  const { data: t, error: te } = await admin
    .from('tenants')
    .insert({ slug, salon_name: '데모 살롱' })
    .select('id')
    .single();
  if (te || !t) return NextResponse.json({ error: te?.message ?? 'tenant insert failed' }, { status: 500 });
  const tenantId = t.id as string;

  await admin.from('memberships').insert({ tenant_id: tenantId, user_id: user.id, role: 'owner' });

  const today = new Date();
  const d = (offset: number) => {
    const x = new Date(today);
    x.setDate(x.getDate() + offset);
    return x.toISOString().slice(0, 10);
  };

  const { data: custs } = await admin
    .from('customers')
    .insert([
      { tenant_id: tenantId, ext_id: 'D001', visit_count: 6, last_visit: d(-40), revisit_cycle_days: 35, revisit_state: 'overdue', tier: 'vip', prefer_tags: ['펌', '내추럴'] },
      { tenant_id: tenantId, ext_id: 'D002', visit_count: 3, last_visit: d(-33), revisit_cycle_days: 30, revisit_state: 'due' },
      { tenant_id: tenantId, ext_id: 'D003', visit_count: 1, last_visit: d(-5), revisit_state: 'new' },
      { tenant_id: tenantId, ext_id: 'D004', visit_count: 8, last_visit: d(-12), tier: 'vip' },
    ])
    .select('id,ext_id');

  const byExt = (e: string) =>
    (custs as { id: string; ext_id: string }[] | null)?.find((c) => c.ext_id === e)?.id ?? null;

  await admin.from('bookings').insert([
    { tenant_id: tenantId, customer_id: byExt('D001'), date: d(0), time: '14:00', service: '뿌리염색', ext_id: 'B1' },
    { tenant_id: tenantId, customer_id: byExt('D002'), date: d(1), time: '11:30', service: '클리닉', ext_id: 'B2' },
  ]);

  return NextResponse.json({ ok: true, tenant_id: tenantId });
}
