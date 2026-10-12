export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { requireUser, getTenantId, openDek, nameReader } from '@/lib/tenant';
import { fetchAllRows, isRealCustomer, isChurned, needsCare } from '@/lib/customers';
import { mergeSettings, isVip } from '@/lib/settings';
import { kstDatePlus, kstNow, isUpcoming } from '@/lib/kst';
import { bookedCustomerIds } from '@/lib/bookings';
import { lastSynced } from '@/lib/sync';
import { txKind } from '@/lib/tx';
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
  churned_at: string | null;
  visits_90d: number | null;
  visits_180d: number | null;
  visits_365d: number | null;
};
type Booking = { id: string; date: string; time: string | null; service: string | null; customer_id: string | null; pii_enc: string | null; staff: string | null; status: string | null; name?: string };

export default async function Page() {
  // 홈만은 소속이 없을 때 리다이렉트가 아니라 온보딩 화면을 보여주므로 requireTenant 를 쓰지 않는다.
  const { supabase } = await requireUser();
  const tenantId = await getTenantId(supabase);
  if (!tenantId) {
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

  const [{ data: tenant }, { data: bookings }, customers, synced, booked] = await Promise.all([
    supabase.from('tenants').select('salon_name,designer_name,dek_wrapped,settings').eq('id', tenantId).maybeSingle(),
    // 오늘부터 — 날짜 조건 없이 오름차순 200건을 받으면 지난 예약이 쌓일 때 앞으로 올 예약이 잘린다
    supabase
      .from('bookings')
      .select('id,date,time,service,customer_id,pii_enc,staff,status')
      .gte('date', kstNow().date)
      .order('date', { ascending: true })
      .order('time', { ascending: true, nullsFirst: false })
      .limit(200),
    fetchAllRows<Cust>((from, to) =>
      supabase.from('customers').select('id,ext_id,revisit_state,tier,visit_count,total_won,pii_enc,last_visit,churned_at,visits_90d,visits_180d,visits_365d').order('id').range(from, to)),
    lastSynced(supabase), // 주 1회라 '이 화면이 언제 기준인지'를 밝혀야 한다
    bookedCustomerIds(supabase, tenantId), // 이미 예약한 손님은 챙길 고객이 아니다
  ]);

  const t = tenant as { salon_name: string; designer_name: string | null; dek_wrapped: string | null; settings: unknown } | null;
  const settings = mergeSettings(t?.settings);
  const bk = (bookings as Booking[]) ?? [];
  const cust = (customers as Cust[]) ?? [];

  const dek = await openDek(t?.dek_wrapped);
  const nameFrom = nameReader(dek);

  // 이탈위험·재방문도래 신호와 '챙길 고객' 목록은 needsCare 하나로 센다 — 설정의 이탈 판정,
  // 이탈 표시, 이미 잡힌 예약을 모두 뺀다. 타일·칩·카드·탭 숫자가 같아야 믿을 수 있다.
  const isCareTarget = (c: Cust) => needsCare(c, { settings, churned: isChurned(c), booked: booked.has(c.id) });

  const signals = { overdue: 0, due: 0, new: 0, vip: 0 };
  for (const c of cust) {
    if (!isRealCustomer(c.ext_id)) continue; // '손님' 등 미식별 워크인 집계는 관리대상 제외
    if (isChurned(c)) continue; // 디자이너가 직접 이탈로 표시 — 모든 신호에서 제외
    if (c.revisit_state === 'overdue' || c.revisit_state === 'due') {
      if (isCareTarget(c)) (signals as Record<string, number>)[c.revisit_state]++;
    } else if (c.revisit_state === 'new') {
      signals.new++;
    }
    if (isVip(c, settings)) signals.vip++;
  }

  const rank: Record<string, number> = { overdue: 0, due: 1 };
  const careBase = cust
    .filter((c) => isRealCustomer(c.ext_id) && isCareTarget(c))
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

  // 방문 관리 진입점 숫자 — 그 화면이 보여주는 창(최근 14일)과 같은 기준으로 센다.
  // '오늘' 기준이면 눌러 들어갔을 때 14일치가 나와 숫자와 화면이 어긋난다.
  // 충전만 하고 간 날은 '방문'이 아니다 — 시술 거래만 센다(집계 기준과 동일).
  const recentTx = await fetchAllRows<{ customer_id: string | null; kind: string | null; service: string | null }>((from, to) =>
    supabase.from('transactions').select('customer_id,kind,service').gte('date', kstDatePlus(-13)).order('id').range(from, to));
  const recentVisits = new Set(
    recentTx.filter((x) => txKind(x.kind, x.service) === 'service').map((x) => x.customer_id).filter(Boolean),
  ).size;

  return (
    <HomeView
      designer={t?.designer_name ?? t?.salon_name ?? '디자이너'}
      synced={synced}
      recentVisits={recentVisits}
      signals={signals}
      care={care}
      bookings={bkNamed}
    />
  );
}
