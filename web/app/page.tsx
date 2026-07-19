export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import { fetchAllRows, isRealCustomer } from '@/lib/customers';
import { mergeSettings, isVip, isLapsed } from '@/lib/settings';
import { kstNow, kstDatePlus, isUpcoming } from '@/lib/kst';
import HomeView from './home-view';
import OnboardButton from './onboard-button';

type Cust = {
  id: string;
  ext_id: string | null;
  revisit_state: string | null;
  tier: string | null;
  visit_count: number;
  total_won: number;
  pii_enc: string | null;
  last_visit: string | null;
};
type Booking = { id: string; date: string; time: string | null; service: string | null; customer_id: string | null; pii_enc: string | null; staff: string | null; status: string | null; name?: string };

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
  const [{ data: tenant }, { data: bookings }, customers] = await Promise.all([
    supabase.from('tenants').select('salon_name,designer_name,dek_wrapped,settings').eq('id', tenantId).maybeSingle(),
    supabase
      .from('bookings')
      .select('id,date,time,service,customer_id,pii_enc,staff,status')
      .order('date', { ascending: true })
      .order('time', { ascending: true, nullsFirst: false })
      .limit(200),
    fetchAllRows<Cust>((from, to) =>
      supabase.from('customers').select('id,ext_id,revisit_state,tier,visit_count,total_won,pii_enc,last_visit').order('id').range(from, to)),
  ]);

  const t = tenant as { salon_name: string; designer_name: string | null; dek_wrapped: string | null; settings: unknown } | null;
  const settings = mergeSettings(t?.settings);
  const bk = (bookings as Booking[]) ?? [];
  const cust = (customers as Cust[]) ?? [];

  let dek: Uint8Array | null = null;
  if (t?.dek_wrapped) {
    try {
      dek = await unwrapDek(t.dek_wrapped);
    } catch {
      dek = null;
    }
  }
  const nameFrom = async (pii: string | null): Promise<string> => {
    if (!dek || !pii) return '고객';
    try {
      const p = await decryptPII(pii, dek);
      return typeof p.name === 'string' ? p.name : '고객';
    } catch {
      return '고객';
    }
  };

  // 이탈 판정은 설정(판정 기준)을 따른다 → 홈 '챙길 고객'·신호에서 제외
  const lapsed = (c: Cust) => isLapsed(c, settings);

  const signals = { overdue: 0, due: 0, new: 0, vip: 0 };
  for (const c of cust) {
    if (!isRealCustomer(c.ext_id)) continue; // '손님' 등 미식별 워크인 집계는 관리대상 제외
    if (c.revisit_state === 'overdue' || c.revisit_state === 'due') {
      if (!lapsed(c)) (signals as Record<string, number>)[c.revisit_state]++;
    } else if (c.revisit_state === 'new') {
      signals.new++;
    }
    if (isVip(c, settings)) signals.vip++;
  }

  const rank: Record<string, number> = { overdue: 0, due: 1 };
  const careBase = cust
    .filter((c) => isRealCustomer(c.ext_id) && (c.revisit_state === 'overdue' || c.revisit_state === 'due') && !lapsed(c))
    .sort((a, b) => rank[a.revisit_state as string] - rank[b.revisit_state as string] || b.visit_count - a.visit_count)
    .slice(0, 20);
  const careNames = await Promise.all(careBase.map((c) => nameFrom(c.pii_enc)));
  const care = careBase.map((c, i) => ({
    id: c.id,
    name: careNames[i],
    state: c.revisit_state as string,
    visit_count: c.visit_count,
    last_visit: c.last_visit,
  }));

  // 테넌트=한 디자이너라 예약은 이미 그 디자이너 것. booking_days_ahead 기간 내만, date+time 정렬 유지.
  // 예약 시각은 KST(HandSOS 기준). 엣지 런타임은 UTC 라 KST 로 계산해야 한국 새벽에 날짜가 안 밀린다.
  // isUpcoming 이 '오늘 이미 지난 시간'(10:00 예약을 11시에 보는 경우)도 걸러낸다.
  const bkCutoff = kstDatePlus(settings.booking_days_ahead);
  const bkVisible = bk.filter((b) => (b.date || '') <= bkCutoff && isUpcoming(b.date, b.time)).slice(0, 20);
  const bkNamed = await Promise.all(bkVisible.map(async (b) => ({ ...b, name: await nameFrom(b.pii_enc) })));

  // 오늘 다녀가신 분(매출 기준) — 방문 관리 진입점에 표시
  const { data: todayTx } = await supabase
    .from('transactions')
    .select('customer_id')
    .eq('date', kstNow().date)
    .limit(500);
  const todayVisits = new Set(
    ((todayTx as { customer_id: string | null }[]) ?? []).map((x) => x.customer_id).filter(Boolean),
  ).size;

  return (
    <HomeView
      designer={t?.designer_name ?? t?.salon_name ?? '디자이너'}
      totalCustomers={cust.length}
      todayVisits={todayVisits}
      signals={signals}
      care={care}
      bookings={bkNamed}
    />
  );
}
