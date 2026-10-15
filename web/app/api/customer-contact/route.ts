export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { CONTACT_VIAS, contactSince, type ContactVia } from '@/lib/contact';

// '연락함' 기록·되돌리기 — 챙길 고객 카드에서 문자·전화·문구 복사를 누르면 남는다.
// RLS(tenant_rw)로 본인 테넌트 고객만. 테넌트는 요청 값이 아니라 고객 행에서 가져온다.
// 문구 본문은 저장하지 않는다(이름이 들어간다 — lib/contact.ts 참고).
export async function POST(request: Request) {
  const supabase = await supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  const body = await request.json().catch(() => ({}));
  const id = body.customer_id;
  if (!id || typeof id !== 'string') return NextResponse.json({ error: 'no id' }, { status: 400 });

  // 되돌리기 — 잘못 눌렀을 때. 최근 기간 안의 연락 기록만 지운다(오래된 기록은 건드리지 않는다).
  if (body.undo === true) {
    const { error } = await supabase
      .from('care_items')
      .delete()
      .eq('customer_id', id)
      .eq('kind', 'contact')
      .gte('sent_at', contactSince());
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ ok: true, contacted: false });
  }

  const via = (CONTACT_VIAS as readonly string[]).includes(body.via) ? (body.via as ContactVia) : null;
  if (!via) return NextResponse.json({ error: 'bad via' }, { status: 400 });

  const { data: c, error: ce } = await supabase.from('customers').select('tenant_id').eq('id', id).maybeSingle();
  if (ce) return NextResponse.json({ error: ce.message }, { status: 500 });
  if (!c) return NextResponse.json({ error: 'not found' }, { status: 404 });

  const { error } = await supabase.from('care_items').insert({
    tenant_id: (c as { tenant_id: string }).tenant_id,
    customer_id: id,
    kind: 'contact',
    why: via,
    sent_at: new Date().toISOString(),
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, contacted: true });
}
