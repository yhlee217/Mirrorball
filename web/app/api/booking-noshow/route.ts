export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { getTenantId } from '@/lib/tenant';
import { noShowUpdate } from '@/lib/visits';

/**
 * 노쇼 표시 · 되돌리기 — 방문 탭 '예약 기준' 줄 · 상세보기 이력 맨 위 줄의 버튼(components/noshow-button). 예약 상태만 바꾼다(lib/visits
 * noShowUpdate — '노쇼·앱|원래 상태'). 자기 매장 예약만(RLS + 매장 조건), 시간이 지난 예약만 표시할 수 있다.
 * 다음 수집(일요일)이 지나면 그 주의 방문은 HandSOS 거래 기록으로 정해진다.
 */
export async function POST(request: Request) {
  const supabase = await supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ ok: false }, { status: 401 });
  const tenantId = await getTenantId(supabase);
  if (!tenantId) return NextResponse.json({ ok: false }, { status: 400 });

  const body = (await request.json().catch(() => ({}))) as { id?: unknown; undo?: unknown };
  const id = typeof body.id === 'string' && /^[0-9a-f-]{36}$/i.test(body.id) ? body.id : null;
  if (!id) return NextResponse.json({ ok: false }, { status: 400 });

  const { data: b } = await supabase
    .from('bookings')
    .select('id,date,time,status')
    .eq('id', id)
    .eq('tenant_id', tenantId)
    .maybeSingle();
  if (!b) return NextResponse.json({ ok: false }, { status: 404 });

  const next = noShowUpdate(b as { date: string | null; time: string | null; status: string | null }, body.undo === true);
  if (!next.ok) return NextResponse.json({ ok: false }, { status: 409 });
  const { error } = await supabase.from('bookings').update({ status: next.status }).eq('id', id).eq('tenant_id', tenantId);
  return NextResponse.json({ ok: !error });
}
