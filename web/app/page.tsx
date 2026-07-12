export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import HomeView from './home-view';
import OnboardButton from './onboard-button';

type Cust = {
  id: string;
  revisit_state: string | null;
  tier: string | null;
  visit_count: number;
  pii_enc: string | null;
  last_visit: string | null;
};
type Booking = { id: string; date: string; time: string | null; service: string | null; customer_id: string | null };

export default async function Page() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) {
    return (
      <main className="wrap">
        <div className="entry">
          <div className="brand">살롱 컨시어지</div>
          <p className="muted">아직 연결된 살롱이 없어요. 데모 데이터로 홈을 확인해보세요.</p>
          <OnboardButton />
        </div>
      </main>
    );
  }

  const tenantId = (mem as { tenant_id: string }).tenant_id;
  const [{ data: tenant }, { data: bookings }, { data: customers }] = await Promise.all([
    supabase.from('tenants').select('salon_name,designer_name,dek_wrapped').eq('id', tenantId).maybeSingle(),
    supabase.from('bookings').select('id,date,time,service,customer_id').order('date').limit(20),
    supabase.from('customers').select('id,revisit_state,tier,visit_count,pii_enc,last_visit'),
  ]);

  const t = tenant as { salon_name: string; designer_name: string | null; dek_wrapped: string | null } | null;
  const bk = (bookings as Booking[]) ?? [];
  const cust = (customers as Cust[]) ?? [];

  // 테넌트 DEK 언랩(이름 복호화용)
  let dek: Buffer | null = null;
  if (t?.dek_wrapped) {
    try {
      dek = unwrapDek(t.dek_wrapped);
    } catch {
      dek = null;
    }
  }
  const nameFrom = (pii: string | null): string => {
    if (!dek || !pii) return '고객';
    try {
      const p = decryptPII(pii, dek);
      return typeof p.name === 'string' ? p.name : '고객';
    } catch {
      return '고객';
    }
  };

  // 신호 집계
  const signals = { overdue: 0, due: 0, new: 0, vip: 0 };
  for (const c of cust) {
    if (c.revisit_state && c.revisit_state in signals) (signals as Record<string, number>)[c.revisit_state]++;
    if (c.tier === 'vip') signals.vip++;
  }

  // 오늘 챙길 고객: 이탈위험 → 재방문도래 순, 최대 20, 이름 복호화
  const rank: Record<string, number> = { overdue: 0, due: 1 };
  const care = cust
    .filter((c) => c.revisit_state === 'overdue' || c.revisit_state === 'due')
    .sort((a, b) => rank[a.revisit_state as string] - rank[b.revisit_state as string] || b.visit_count - a.visit_count)
    .slice(0, 20)
    .map((c) => ({
      id: c.id,
      name: nameFrom(c.pii_enc),
      state: c.revisit_state as string,
      visit_count: c.visit_count,
      last_visit: c.last_visit,
    }));

  // 예약 고객 이름
  const nameById: Record<string, string> = {};
  for (const b of bk) {
    if (b.customer_id) {
      const c = cust.find((x) => x.id === b.customer_id);
      if (c) nameById[b.customer_id] = nameFrom(c.pii_enc);
    }
  }

  return (
    <HomeView
      designer={t?.designer_name ?? t?.salon_name ?? '디자이너'}
      totalCustomers={cust.length}
      signals={signals}
      care={care}
      bookings={bk}
      nameById={nameById}
    />
  );
}
