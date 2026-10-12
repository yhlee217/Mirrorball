export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { requireUser, getTenantId, openDek, nameReader } from '@/lib/tenant';
import { fetchAllRows, isRealCustomer, isChurned, needsCare, onCareList } from '@/lib/customers';
import { mergeSettings, isVip } from '@/lib/settings';
import { kstDatePlus, kstNow, isUpcoming } from '@/lib/kst';
import { bookedCustomerIds, isCancelled } from '@/lib/bookings';
import { recentlyContactedIds } from '@/lib/contact';
import { lastSynced } from '@/lib/sync';
import { lastWeek, spanLabel, weekNums, type WeekTx } from '@/lib/week';
import { gapLine, lastServices, latestRecent, memoLines, visitTag } from '@/lib/briefing';
import HomeView, { type Brief } from './home-view';
import OnboardButton from './onboard-button';

type Cust = {
  id: string;
  ext_id: string | null;
  revisit_state: string | null;
  tier: string | null;
  visit_count: number;
  total_won: number;
  pii_enc: string | null;
  first_visit: string | null;
  last_visit: string | null;
  churned_at: string | null;
  visits_90d: number | null;
  visits_180d: number | null;
  visits_365d: number | null;
};
type Booking = { id: string; date: string; time: string | null; service: string | null; customer_id: string | null; pii_enc: string | null; status: string | null };
type Detail = { id: string; revisit_cycle_days: number | null; prepaid_balance: number | null; memo_ai: string | null; memo_ai_recent: string | null };
type LastTx = { customer_id: string | null; date: string | null; service: string | null; kind: string | null };

// 브리핑은 앞으로 7일 — 주 1회 수집 리듬에 맞춘다. 그 뒤 예약은 접어 둔다.
const SOON_DAYS = 7;

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

  const today = kstNow().date;
  const [{ data: tenant }, { data: bookings }, customers, synced, booked, contacted] = await Promise.all([
    supabase.from('tenants').select('salon_name,designer_name,dek_wrapped,settings').eq('id', tenantId).maybeSingle(),
    // 오늘부터 — 날짜 조건 없이 오름차순 200건을 받으면 지난 예약이 쌓일 때 앞으로 올 예약이 잘린다
    supabase
      .from('bookings')
      .select('id,date,time,service,customer_id,pii_enc,status')
      .eq('tenant_id', tenantId)
      .gte('date', today)
      .order('date', { ascending: true })
      .order('time', { ascending: true, nullsFirst: false })
      .limit(200),
    fetchAllRows<Cust>((from, to) =>
      supabase.from('customers').select('id,ext_id,revisit_state,tier,visit_count,total_won,pii_enc,first_visit,last_visit,churned_at,visits_90d,visits_180d,visits_365d').order('id').range(from, to)),
    lastSynced(supabase), // 주 1회라 '이 화면이 언제 기준인지'를 밝혀야 한다
    bookedCustomerIds(supabase, tenantId), // 이미 예약한 손님은 챙길 고객이 아니다
    recentlyContactedIds(supabase, tenantId), // 최근 연락한 분은 '할 일'에서 잠시 빠진다
  ]);

  const t = tenant as { salon_name: string; designer_name: string | null; dek_wrapped: string | null; settings: unknown } | null;
  const settings = mergeSettings(t?.settings);
  const bk = (bookings as Booking[]) ?? [];
  const cust = (customers as Cust[]) ?? [];
  const byId = new Map(cust.map((c) => [c.id, c]));

  const dek = await openDek(t?.dek_wrapped);
  const nameFrom = nameReader(dek);

  // 이탈위험·재방문도래 신호는 needsCare 로 센다 — 설정의 이탈 판정, 이탈 표시, 이미 잡힌 예약을
  // 모두 뺀다. 고객 목록의 같은 필터와 숫자가 같아야 믿을 수 있다.
  const isCareTarget = (c: Cust) => needsCare(c, { settings, churned: isChurned(c), booked: booked.has(c.id) });
  // '챙길 고객 N명'(할 일)은 최근 연락한 분도 뺀다 — 눌러서 열리는 챙길 고객 탭과 같은 숫자여야 한다.
  // 타일(이탈위험·재방문도래)은 손님 상태라 연락 여부와 무관하게 위 기준으로 센다.
  const isTodo = (c: Cust) =>
    onCareList(c, { settings, churned: isChurned(c), booked: booked.has(c.id), contacted: contacted.has(c.id) });

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
  const real = cust.filter((c) => isRealCustomer(c.ext_id));
  const careCount = real.filter(isTodo).length;
  const careQuiet = real.filter((c) => isCareTarget(c) && contacted.has(c.id)).length;

  // 예약 — 앞으로 7일은 브리핑, 그 뒤(설정의 표시 기간까지)는 접어 둔다.
  // 예약 시각은 KST(HandSOS 기준). isUpcoming 이 '오늘 이미 지난 시간'도 걸러낸다.
  const bkCutoff = kstDatePlus(settings.booking_days_ahead);
  const soonEnd = kstDatePlus(SOON_DAYS - 1);
  const upcoming = bk.filter((b) => (b.date || '') <= bkCutoff && isUpcoming(b.date, b.time));
  const soon = upcoming.filter((b) => b.date <= soonEnd).slice(0, 40);
  const later = upcoming.filter((b) => b.date > soonEnd).slice(0, 30);

  // 브리핑 재료는 예약 손님 몇 명 것만 따로 읽는다 — 메모 정리(memo_ai)는 길어서 전체 고객과 함께
  // 받지 않는다. 미식별 워크인 집계('손님')에 묶인 예약은 남의 메모가 섞이므로 붙이지 않는다.
  const known = (b: Booking) => !!b.customer_id && isRealCustomer(byId.get(b.customer_id)?.ext_id);
  const ids = [...new Set(soon.filter((b) => !isCancelled(b.status) && known(b)).map((b) => b.customer_id as string))];
  const lastDates = [...new Set(ids.map((id) => byId.get(id)?.last_visit).filter(Boolean) as string[])];
  const wk = lastWeek(synced?.date, today);

  const [weekTx, details, lastTx] = await Promise.all([
    fetchAllRows<WeekTx>((from, to) =>
      supabase.from('transactions').select('customer_id,date,kind,service,amount_won,covered_won')
        .eq('tenant_id', tenantId).gte('date', wk.prev.start).lte('date', wk.cur.end).order('id').range(from, to)),
    ids.length
      ? supabase.from('customers').select('id,revisit_cycle_days,prepaid_balance,memo_ai,memo_ai_recent').in('id', ids)
          .then((r) => (r.data as Detail[] | null) ?? [])
      : Promise.resolve([] as Detail[]),
    // '지난번에 뭘 했나' — 각자의 마지막 방문일 거래만. 손님당 몇 건이라 1000행 상한에 닿지 않는다.
    ids.length && lastDates.length
      ? supabase.from('transactions').select('customer_id,date,service,kind').in('customer_id', ids).in('date', lastDates)
          .then((r) => (r.data as LastTx[] | null) ?? [])
      : Promise.resolve([] as LastTx[]),
  ]);

  // 지난 한 주 — 첫 방문은 실고객만 센다(워크인 집계는 '첫 방문'이 의미가 없다).
  const firsts = real.map((c) => c.first_visit);
  const week = {
    label: spanLabel(wk.cur),
    cur: weekNums(weekTx, firsts, wk.cur),
    prev: weekNums(weekTx, firsts, wk.prev),
  };

  const det = new Map(details.map((d) => [d.id, d]));
  const lastSvc = lastServices(lastTx, (id) => byId.get(id)?.last_visit);
  const toBrief = async (b: Booking): Promise<Brief> => {
    const name = await nameFrom(b.pii_enc);
    const off = isCancelled(b.status);
    const base = { id: b.id, date: b.date, time: b.time, service: b.service, customer_id: b.customer_id, status: b.status, name, off };
    if (off) return { ...base, tag: null, gap: null, last: null, prefer: [], recent: null, prepaid: 0 };
    // 손님 기록에 연결되지 않은 예약 — 고객번호·전화·이름 어느 것으로도 못 찾았다는 뜻이라 첫 방문으로 본다
    if (!b.customer_id) return { ...base, tag: '첫 방문', gap: null, last: null, prefer: [], recent: null, prepaid: 0 };
    const c = byId.get(b.customer_id);
    const d = det.get(b.customer_id);
    if (!c || !known(b)) return { ...base, tag: null, gap: null, last: null, prefer: [], recent: null, prepaid: 0 };
    return {
      ...base,
      tag: visitTag(c.visit_count),
      gap: gapLine(c.last_visit, b.date, d?.revisit_cycle_days),
      last: lastSvc.get(c.id) ?? null,
      prefer: memoLines(d?.memo_ai, 2),
      recent: latestRecent(d?.memo_ai_recent),
      prepaid: d?.prepaid_balance ?? 0,
    };
  };
  const [briefs, laterRows] = await Promise.all([
    Promise.all(soon.map(toBrief)),
    Promise.all(later.map(async (b) => ({ ...b, name: await nameFrom(b.pii_enc), off: isCancelled(b.status) }))),
  ]);

  return (
    <HomeView
      designer={t?.designer_name ?? t?.salon_name ?? '디자이너'}
      synced={synced}
      today={today}
      signals={signals}
      week={week}
      careCount={careCount}
      careQuiet={careQuiet}
      briefs={briefs}
      later={laterRows}
    />
  );
}
