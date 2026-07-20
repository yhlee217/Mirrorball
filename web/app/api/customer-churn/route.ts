export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';

// 이탈 고객 표시/해제 — RLS(tenant_rw)로 본인 테넌트 고객만 수정 가능.
// 되돌릴 수 있어야 하므로 삭제가 아니라 churned_at 토글이다.
export async function POST(request: Request) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  const body = await request.json();
  const id = body.customer_id;
  if (!id || typeof id !== 'string') return NextResponse.json({ error: 'no id' }, { status: 400 });

  const churned = body.churned === true;
  const { error } = await supabase
    .from('customers')
    .update({ churned_at: churned ? new Date().toISOString() : null })
    .eq('id', id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, churned });
}
