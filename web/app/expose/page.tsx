export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import { fetchAllRows, isRealCustomer } from '@/lib/customers';
import Coach from './coach';

type RCust = { id: string; ext_id: string | null; pii_enc: string | null; last_visit: string | null };

export default async function ExposePage() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) redirect('/');
  const tenantId = (mem as { tenant_id: string }).tenant_id;

  const day = 86400000;
  const since30 = new Date(Date.now() - 30 * day).toISOString().slice(0, 10);
  const since14 = new Date(Date.now() - 14 * day).toISOString().slice(0, 10);

  const [{ data: tenant }, txs, { data: recent }] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped,salon_name').eq('id', tenantId).maybeSingle(),
    fetchAllRows<{ service: string | null }>((from, to) =>
      supabase.from('transactions').select('service').gte('date', since30).order('id').range(from, to)),
    supabase
      .from('customers')
      .select('id,ext_id,pii_enc,last_visit')
      .gte('last_visit', since14)
      .order('last_visit', { ascending: false })
      .limit(40),
  ]);

  const salon = (tenant as { salon_name: string } | null)?.salon_name || '';
  const dw = (tenant as { dek_wrapped: string | null } | null)?.dek_wrapped ?? null;
  let dek: Uint8Array | null = null;
  if (dw) {
    try {
      dek = await unwrapDek(dw);
    } catch {
      dek = null;
    }
  }
  const nameFrom = async (pii: string | null): Promise<string> => {
    if (!dek || !pii) return '고객';
    try {
      const p = await decryptPII(pii, dek);
      return typeof p.name === 'string' && p.name ? p.name : '고객';
    } catch {
      return '고객';
    }
  };

  // 최근 인기 시술
  const svcN = new Map<string, number>();
  for (const t of txs) {
    const s = (t.service || '').trim();
    if (s) svcN.set(s, (svcN.get(s) || 0) + 1);
  }
  const topServices = [...svcN.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5).map(([service, count]) => ({ service, count }));

  // 리뷰 요청 대상: 최근 방문 실고객
  const cand = ((recent as RCust[]) ?? []).filter((c) => isRealCustomer(c.ext_id)).slice(0, 8);
  const names = await Promise.all(cand.map((c) => nameFrom(c.pii_enc)));
  const lastSvc = new Map<string, string>();
  const ids = cand.map((c) => c.id);
  if (ids.length) {
    const { data: cs } = await supabase
      .from('transactions')
      .select('customer_id,date,service')
      .in('customer_id', ids)
      .order('date', { ascending: false })
      .limit(1000);
    for (const t of (cs as { customer_id: string | null; service: string | null }[]) ?? []) {
      if (t.customer_id && t.service && !lastSvc.has(t.customer_id)) lastSvc.set(t.customer_id, t.service);
    }
  }
  const reviewTargets = cand.map((c, i) => ({
    id: c.id,
    name: names[i],
    last_visit: c.last_visit,
    service: lastSvc.get(c.id) ?? null,
  }));

  return (
    <main className="wrap">
      <div className="bar">
        <div className="ttl">노출 · 마케팅</div>
      </div>
      <div className="body">
        <p className="note" style={{ marginTop: 0 }}>
          최근 시술·고객 데이터로 만든 제안이에요. 문구는 복사해서 쓰고, ‘AI로 다듬기’로 더 자연스럽게 바꿀 수 있어요.
        </p>
        <Coach salon={salon} topServices={topServices} reviewTargets={reviewTargets} />
      </div>
    </main>
  );
}
