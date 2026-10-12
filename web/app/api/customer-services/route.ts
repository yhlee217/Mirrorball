export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { getTenantId } from '@/lib/tenant';
import { fetchAllRows } from '@/lib/customers';
import { svcCat } from '@/lib/coach';

/**
 * 손님별 시술 갈래(펌 · 염색 · 클리닉 · 컷) — 고객 목록에서 '시술' 필터를 고를 때만 부른다.
 * 목록을 열 때마다 거래 전체를 받던 것을 필요할 때로 미뤘다(개선 계획 v4 0-3).
 * RLS 로 본인 테넌트 거래만 보인다. 수집이 주 1회라 잠깐 캐시해도 된다.
 */
export async function GET() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  const tenantId = await getTenantId(supabase);
  if (!tenantId) return NextResponse.json({ error: 'no tenant' }, { status: 400 });

  const txs = await fetchAllRows<{ customer_id: string | null; service: string | null }>((from, to) =>
    supabase.from('transactions').select('customer_id,service').eq('tenant_id', tenantId).order('id').range(from, to));
  const by = new Map<string, Set<string>>();
  for (const t of txs) {
    const cat = t.customer_id && t.service ? svcCat(t.service) : null;
    if (!cat) continue;
    if (!by.has(t.customer_id!)) by.set(t.customer_id!, new Set());
    by.get(t.customer_id!)!.add(cat);
  }
  const out: Record<string, string[]> = {};
  for (const [id, cats] of by) out[id] = [...cats];
  return NextResponse.json(out, { headers: { 'Cache-Control': 'private, max-age=300' } });
}
