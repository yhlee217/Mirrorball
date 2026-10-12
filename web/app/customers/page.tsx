export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { openDek, requireTenant } from '@/lib/tenant';
import { decryptPII } from '@/lib/crypto';
import { careState, fetchAllRows, isRealCustomer } from '@/lib/customers';
import { mergeSettings } from '@/lib/settings';
import { bookedCustomerIds } from '@/lib/bookings';
import { phoneTail } from '@/lib/contact';
import { lastSynced } from '@/lib/sync';
import { kstNow } from '@/lib/kst';
import CustomersList from './customers-list';

type Cust = {
  id: string;
  ext_id: string | null;
  pii_enc: string | null;
  visit_count: number;
  revisit_state: string | null;
  revisit_cycle_days: number | null;
  last_visit: string | null;
  first_visit: string | null;
  total_won: number;
  churned_at: string | null;
  gender: string | null;
  gender_manual: string | null;
  visits_90d: number | null;
  visits_180d: number | null;
  visits_365d: number | null;
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
const FILTERS = new Set(['overdue', 'due', 'new', 'vip', 'booking', 'nophone', 'churned', 'nogender']);

export default async function CustomersPage({
  searchParams,
}: {
  searchParams: { filter?: string };
}) {
  const initialFilter = searchParams?.filter && FILTERS.has(searchParams.filter) ? searchParams.filter : null;
  const { supabase, tenantId } = await requireTenant();

  const [{ data: tenant }, customers, bookingSet, txs, synced] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped,settings').eq('id', tenantId).maybeSingle(),
    fetchAllRows<Cust>((from, to) =>
      supabase
        .from('customers')
        .select('id,ext_id,pii_enc,visit_count,revisit_state,revisit_cycle_days,last_visit,first_visit,total_won,churned_at,visits_90d,visits_180d,visits_365d,gender,gender_manual')
        .order('id')
        .range(from, to)),
    // 앞으로 올 예약만 — 지난 예약·취소·노쇼는 빠진다. 홈·챙길 고객과 같은 판정이다.
    bookedCustomerIds(supabase, tenantId),
    fetchAllRows<{ customer_id: string | null; service: string | null }>((from, to) =>
      supabase.from('transactions').select('customer_id,service').order('id').range(from, to)),
    lastSynced(supabase), // 재방문 판정의 기준일 — 휴가를 빼고 셀 때 쓴다(lib/customers careState)
  ]);

  const tRow = tenant as { dek_wrapped: string | null; settings: unknown } | null;
  const settings = mergeSettings(tRow?.settings);
  const asOf = synced?.date ?? kstNow().date;
  const dek = await openDek(tRow?.dek_wrapped);

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
      let tail = ''; // 전화번호 뒷자리 4자리만 — 전체 번호는 화면으로 보내지 않는다
      if (dek && c.pii_enc) {
        try {
          const p = await decryptPII(c.pii_enc, dek);
          if (typeof p.name === 'string' && p.name) name = p.name;
          hasPhone = !!p.phone;
          tail = phoneTail(typeof p.phone === 'string' ? p.phone : null);
        } catch {
          /* noop */
        }
      }
      return { name, hasPhone, tail };
    }),
  );

  const rows = list.map((c, i) => ({
    id: c.id,
    name: decoded[i].name,
    visit_count: c.visit_count,
    total_won: c.total_won || 0,
    last_visit: c.last_visit,
    first_visit: c.first_visit,
    state: careState(c, settings, asOf), // 휴가를 반영한 재방문 상태 — 홈·챙길 고객과 같은 기준
    cycle: c.revisit_cycle_days,
    hasBooking: bookingSet.has(c.id),
    hasPhone: decoded[i].hasPhone,
    tail: decoded[i].tail,
    churned: !!c.churned_at, // 디자이너가 직접 이탈로 표시한 고객
    // 사람이 지정한 값이 추정보다 우선한다(통계와 같은 기준).
    gender: (c.gender_manual === 'M' || c.gender_manual === 'F' ? c.gender_manual
             : c.gender === 'M' || c.gender === 'F' ? c.gender : null) as 'M' | 'F' | null,
    visits_90d: c.visits_90d,
    visits_180d: c.visits_180d,
    visits_365d: c.visits_365d,
    services: Array.from(svcMap.get(c.id) ?? []),
  }));

  return (
    <main className="wrap">
      <div className="bar">
        <Link href="/" className="back">‹ 홈</Link>
        <div className="ttl" style={{ marginLeft: 10 }}>고객 {rows.length}명</div>
      </div>
      <div className="body">
        <CustomersList rows={rows} settings={settings} asOf={asOf} initialFilter={initialFilter} />
      </div>
    </main>
  );
}
