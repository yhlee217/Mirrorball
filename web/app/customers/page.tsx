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

  let dek: Buffer | null = null;
  const dw = (tenant as { dek_wrapped: string | null } | null)?.dek_wrapped ?? null;
  if (dw) {
    try {
      dek = unwrapDek(dw);
    } catch {
      dek = null;
    }
  }

  const rows = ((customers as Cust[]) ?? []).map((c) => {
    let name = '고객';
    if (dek && c.pii_enc) {
      try {
        const p = decryptPII(c.pii_enc, dek);
        if (typeof p.name === 'string') name = p.name;
      } catch {
        // 폴백
      }
    }
    return { id: c.id, name, visit_count: c.visit_count, state: c.revisit_state, last_visit: c.last_visit };
  });

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
