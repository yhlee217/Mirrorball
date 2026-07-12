export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import CustomersList from './customers-list';

type Cust = { id: string; pii_enc: string | null; visit_count: number; revisit_state: string | null; last_visit: string | null };

export default async function CustomersPage() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) redirect('/');
  const tenantId = (mem as { tenant_id: string }).tenant_id;

  const [{ data: tenant }, { data: customers }] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped').eq('id', tenantId).maybeSingle(),
    supabase
      .from('customers')
      .select('id,pii_enc,visit_count,revisit_state,last_visit')
      .order('visit_count', { ascending: false }),
  ]);

  let dek: Uint8Array | null = null;
  const dw = (tenant as { dek_wrapped: string | null } | null)?.dek_wrapped ?? null;
  if (dw) {
    try {
      dek = await unwrapDek(dw);
    } catch {
      dek = null;
    }
  }

  const list = (customers as Cust[]) ?? [];
  const names = await Promise.all(
    list.map(async (c) => {
      if (!dek || !c.pii_enc) return '고객';
      try {
        const p = await decryptPII(c.pii_enc, dek);
        return typeof p.name === 'string' ? p.name : '고객';
      } catch {
        return '고객';
      }
    }),
  );

  const rows = list.map((c, i) => ({
    id: c.id,
    name: names[i],
    visit_count: c.visit_count,
    state: c.revisit_state,
    last_visit: c.last_visit,
  }));

  return (
    <main className="wrap">
      <div className="bar">
        <Link href="/" className="back">‹ 홈</Link>
        <div className="ttl" style={{ marginLeft: 10 }}>고객 {rows.length}명</div>
      </div>
      <div className="body">
        <CustomersList rows={rows} />
      </div>
    </main>
  );
}
