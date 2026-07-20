export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import { fetchAllRows, isRealCustomer } from '@/lib/customers';
import { mergeSettings } from '@/lib/settings';
import CustomersList from './customers-list';

type Cust = {
  id: string;
  ext_id: string | null;
  pii_enc: string | null;
  visit_count: number;
  revisit_state: string | null;
  last_visit: string | null;
  first_visit: string | null;
  total_won: number;
  churned_at: string | null;
};

// 시술명 → 대분류(필터용). 매칭 안 되면 제외.
function svcCat(s: string | null): string | null {
  if (!s) return null;
  if (/펌|매직|볼륨|셋팅|디지털|웨이브/.test(s)) return '펌';
  if (/염색|컬러|뿌리|새치|이노아|탈색|블리치|하이라이트|톤다운|톤업/.test(s)) return '염색';
  if (/클리닉|트리트|케어|앰플|두피|스켈프/.test(s)) return '클리닉';
  if (/컷|커트/.test(s)) return '컷';
  return null;
}

// 홈의 신호 타일(이탈위험/재방문도래/신규/VIP)에서 넘어올 때 초기 필터를 받는다.
const FILTERS = new Set(['overdue', 'due', 'new', 'vip', 'booking', 'nophone', 'churned']);

export default async function CustomersPage({
  searchParams,
}: {
  searchParams: { filter?: string };
}) {
  const initialFilter = searchParams?.filter && FILTERS.has(searchParams.filter) ? searchParams.filter : null;
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) redirect('/');
  const tenantId = (mem as { tenant_id: string }).tenant_id;

  const [{ data: tenant }, customers, bookings, txs] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped,settings').eq('id', tenantId).maybeSingle(),
    fetchAllRows<Cust>((from, to) =>
      supabase
        .from('customers')
        .select('id,ext_id,pii_enc,visit_count,revisit_state,last_visit,first_visit,total_won,churned_at')
        .order('id')
        .range(from, to)),
    fetchAllRows<{ customer_id: string | null }>((from, to) =>
      supabase.from('bookings').select('customer_id').order('id').range(from, to)),
    fetchAllRows<{ customer_id: string | null; service: string | null }>((from, to) =>
      supabase.from('transactions').select('customer_id,service').order('id').range(from, to)),
  ]);

  const tRow = tenant as { dek_wrapped: string | null; settings: unknown } | null;
  const settings = mergeSettings(tRow?.settings);
  let dek: Uint8Array | null = null;
  const dw = tRow?.dek_wrapped ?? null;
  if (dw) {
    try {
      dek = await unwrapDek(dw);
    } catch {
      dek = null;
    }
  }

  const bookingSet = new Set(
    (bookings as { customer_id: string | null }[]).map((b) => b.customer_id).filter(Boolean) as string[],
  );
  const svcMap = new Map<string, Set<string>>();
  for (const t of txs as { customer_id: string | null; service: string | null }[]) {
    if (!t.customer_id) continue;
    const cat = svcCat(t.service);
    if (!cat) continue;
    if (!svcMap.has(t.customer_id)) svcMap.set(t.customer_id, new Set());
    svcMap.get(t.customer_id)!.add(cat);
  }

  const list = ((customers as Cust[]) ?? []).filter((c) => isRealCustomer(c.ext_id));
  const decoded = await Promise.all(
    list.map(async (c) => {
      let name = '고객';
      let hasPhone = false;
      if (dek && c.pii_enc) {
        try {
          const p = await decryptPII(c.pii_enc, dek);
          if (typeof p.name === 'string' && p.name) name = p.name;
          hasPhone = !!p.phone;
        } catch {
          /* noop */
        }
      }
      return { name, hasPhone };
    }),
  );

  const rows = list.map((c, i) => ({
    id: c.id,
    name: decoded[i].name,
    visit_count: c.visit_count,
    total_won: c.total_won || 0,
    last_visit: c.last_visit,
    first_visit: c.first_visit,
    state: c.revisit_state,
    hasBooking: bookingSet.has(c.id),
    hasPhone: decoded[i].hasPhone,
    churned: !!c.churned_at, // 디자이너가 직접 이탈로 표시한 고객
    services: Array.from(svcMap.get(c.id) ?? []),
  }));

  return (
    <main className="wrap">
      <div className="bar">
        <Link href="/" className="back">‹ 홈</Link>
        <div className="ttl" style={{ marginLeft: 10 }}>고객 {rows.length}명</div>
      </div>
      <div className="body">
        <CustomersList rows={rows} settings={settings} initialFilter={initialFilter} />
      </div>
    </main>
  );
}
