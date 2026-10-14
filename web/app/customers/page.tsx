export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { openDek, requireTenant } from '@/lib/tenant';
import { decryptPII } from '@/lib/crypto';
import { careState, fetchAllRows, isRealCustomer } from '@/lib/customers';
import { mergeSettings } from '@/lib/settings';
import { bookingSets, recentBookingRows } from '@/lib/bookings';
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
  prepaid_balance: number | null;
};

export default async function CustomersPage() {
  const { supabase, tenantId } = await requireTenant();

  const [{ data: tenant }, customers, bkRows, synced] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped,settings').eq('id', tenantId).maybeSingle(),
    fetchAllRows<Cust>((from, to) =>
      supabase
        .from('customers')
        .select('id,ext_id,pii_enc,visit_count,revisit_state,revisit_cycle_days,last_visit,first_visit,total_won,churned_at,visits_90d,visits_180d,visits_365d,gender,gender_manual,prepaid_balance')
        .order('id')
        .range(from, to)),
    // 예약 판정 재료 — '예약 있음'은 앞으로 올 예약만, 이탈위험·재방문도래는 수집 뒤 지난 예약도 뺀다(lib/bookings)
    recentBookingRows(supabase, tenantId),
    // 손님별 시술 갈래는 '시술' 필터를 고를 때만 받는다(api/customer-services) — 거래 전체를 매번 받지 않게
    lastSynced(supabase), // 재방문 판정의 기준일 — 휴가를 빼고 셀 때 쓴다(lib/customers careState)
  ]);

  const tRow = tenant as { dek_wrapped: string | null; settings: unknown } | null;
  const settings = mergeSettings(tRow?.settings);
  const asOf = synced?.date ?? kstNow().date;
  const { upcoming, hold } = bookingSets(bkRows, asOf);
  const dek = await openDek(tRow?.dek_wrapped);

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
    hasBooking: upcoming.has(c.id),
    held: hold.has(c.id), // 예약했거나 수집 뒤 예약 시각이 지난 분 — 홈 숫자 · 챙길 고객과 같은 판정
    hasPhone: decoded[i].hasPhone,
    tail: decoded[i].tail,
    churned: !!c.churned_at, // 디자이너가 직접 이탈로 표시한 고객
    // 사람이 지정한 값이 추정보다 우선한다(통계와 같은 기준).
    gender: (c.gender_manual === 'M' || c.gender_manual === 'F' ? c.gender_manual
             : c.gender === 'M' || c.gender === 'F' ? c.gender : null) as 'M' | 'F' | null,
    visits_90d: c.visits_90d,
    visits_180d: c.visits_180d,
    visits_365d: c.visits_365d,
    prepaid_balance: Math.max(0, c.prepaid_balance ?? 0), // 추정 — 줄에 '선불 52만', '선불 3개월+' 조건
  }));

  return (
    <main className="wrap">
      <div className="bar">
        <div className="ttl">고객 <span className="sect-n">{rows.length.toLocaleString()}명</span></div>
      </div>
      <div className="body">
        {/* 검색·조건(?filter= 포함)은 목록이 주소에서 직접 읽는다(lib/list-state) */}
        <CustomersList rows={rows} settings={settings} asOf={asOf} today={kstNow().date} />
      </div>
    </main>
  );
}
