export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';

// '사비 결제' 표시 토글 — 이 시술은 선불 잔액이 아니라 따로 결제했다는 표시.
// POS 에 결제수단이 없어 잔액은 추정이고, 그 추정을 사람이 고치는 유일한 손잡이다.
// RLS(tenant_rw)로 본인 테넌트 거래만 수정된다. 수집 업서트는 이 컬럼을 보내지 않으므로
// (merge-duplicates) 여기서 넣은 값이 주간 수집에 덮이지 않는다.
export async function POST(request: Request) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  const body = await request.json();
  const id = body.transaction_id;
  if (!id || typeof id !== 'string') return NextResponse.json({ error: 'no id' }, { status: 400 });

  const pocket = body.pocket === true;
  const { error } = await supabase
    .from('transactions')
    .update({ paid_out_of_pocket: pocket ? true : null })
    .eq('id', id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, pocket });
}
