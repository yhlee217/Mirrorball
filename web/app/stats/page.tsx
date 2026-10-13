export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { requireTenant } from '@/lib/tenant';
import { kstNow } from '@/lib/kst';
import { lastSynced } from '@/lib/sync';
import { SyncChip } from '@/components/sync-chip';
import { BackButton } from '@/components/back-button';
import { fetchAllRows, isRealCustomer, isChurned, onCareList, onFirstList, prepaidAway, servicesOn } from '@/lib/customers';
import { mergeSettings } from '@/lib/settings';
import { bookedCustomerIds, isActiveBooking } from '@/lib/bookings';
import { recentlyContactedIds } from '@/lib/contact';
import { addDays, shortDate } from '@/lib/week';
import { activeTrend, datesByCustomer, newcomerCohorts, serviceTable, toVisits, weekHeat } from '@/lib/trends';
import { hasOffDays, workedDays } from '@/lib/offdays';
import { monthForecast } from '@/lib/forecast';
import { backtest, pairStats, visitsByCustomer } from '@/lib/recommend';
import { contactEffectByGroup, helloEffect, kstDay, type ContactRow } from '@/lib/effect';
import {
  SummaryCard,
  CohortCard,
  HeatCard,
  MonthCard,
  ServiceCard,
  GenderCard,
  RecommendHitCard,
  ContactEffectCard,
  TotalsCard,
  type GenderStat,
} from './cards';

export default async function StatsPage() {
  const { supabase, tenantId } = await requireTenant();

  const kToday = kstNow().date;
  const [y0, m0] = kToday.split('-').map(Number);
  const monthLast = new Date(Date.UTC(y0, m0, 0)).toISOString().slice(0, 10);
  const [{ data: tenant }, customers, txs, booked, contacted, synced, { data: bkLeftRows }, contactRows] = await Promise.all([
    supabase.from('tenants').select('settings').eq('id', tenantId).maybeSingle(),
    fetchAllRows<{ id: string; ext_id: string | null; total_won: number; visit_count: number; gender: string | null;
                   age_band: string | null; gender_src: string | null; gender_manual: string | null; revisit_cycle_days: number | null;
                   revisit_state: string | null; churned_at: string | null; first_visit: string | null; last_visit: string | null;
                   prepaid_balance: number | null;
                   visits_90d: number | null; visits_180d: number | null; visits_365d: number | null }>((from, to) =>
      supabase.from('customers')
        .select('id,ext_id,total_won,visit_count,gender,gender_manual,age_band,gender_src,revisit_cycle_days,revisit_state,churned_at,first_visit,last_visit,prepaid_balance,visits_90d,visits_180d,visits_365d')
        .eq('tenant_id', tenantId).order('id').range(from, to)),
    fetchAllRows<{ customer_id: string | null; date: string; time: string | null; service: string | null; amount_won: number;
                   kind: string | null; covered_won: number | null }>((from, to) =>
      supabase.from('transactions').select('customer_id,date,time,service,amount_won,kind,covered_won').eq('tenant_id', tenantId).order('id').range(from, to)),
    bookedCustomerIds(supabase, tenantId),
    recentlyContactedIds(supabase, tenantId),
    lastSynced(supabase),
    // 이번 달 남은 기간에 잡힌 예약 — 마감 예상 옆에 참고로만(예상 금액에는 섞지 않는다)
    supabase.from('bookings').select('date,time,status').eq('tenant_id', tenantId)
      .gte('date', kToday).lte('date', monthLast).limit(1000),
    // 연락 효과(더 보기) — 연락 기록 전부(문자·전화·복사, 시각만 남는다)
    fetchAllRows<ContactRow>((from, to) =>
      supabase.from('care_items').select('customer_id,sent_at').eq('tenant_id', tenantId).eq('kind', 'contact')
        .order('id').range(from, to)),
  ]);
  // '손님' 등 미식별 워크인은 관리 대상이 아니다 — 홈·챙길 고객·고객목록과 같은 기준으로 뺀다.
  // 통계만 포함하고 있어서 고객수·재방문율·객단가가 부풀고, 성별은 전부 '미상'으로 쌓였다.
  // 이탈 판정 기준(설정)을 따라야 홈 신호와 숫자가 어긋나지 않는다.
  const settings = mergeSettings((tenant as { settings: unknown } | null)?.settings);
  const cs = customers.filter((c) => isRealCustomer(c.ext_id));
  const tx = txs;

  const totalRevenue = cs.reduce((s, c) => s + (c.total_won || 0), 0);
  const totalCustomers = cs.length;
  // 평생 두 번 이상 오신 고객 — 예전 '재방문율' 카드의 숫자. 이제는 신규 카드 아래 한 줄로만 둔다.
  const repeatCust = cs.filter((c) => c.visit_count >= 2).length;

  // 방문 = 시술을 받은 (손님, 날짜). 충전·제품만 산 날은 방문이 아니다(홈·방문 관리와 같은 기준).
  // '변화'를 재는 기준일은 마지막 수집일 — 그 뒤 날짜는 아직 비어 있다(lib/trends.ts).
  const asOf = synced?.date ?? kstNow().date;
  const visits = toVisits(tx);
  const byCust = datesByCustomer(visits);
  const realIds = new Set(cs.map((c) => c.id));
  // 휴무(설정)를 반영한다 — 요일 × 시간대는 영업한 날 하루 평균, '90일 안에 다시'는 휴가만큼 늘려서.
  const cohort = newcomerCohorts(cs, byCust, asOf, settings); // D2
  const heat = weekHeat(visits, addDays(asOf, -182), asOf, settings); // D4 — 최근 6개월(26주)
  const svcRows = serviceTable(tx, byCust, realIds, addDays(asOf, -364), asOf, settings); // D5 — 최근 1년
  const active = activeTrend(byCust, realIds, asOf); // D3
  // 선불 잔액(D6) — 손님별 추정 잔액의 합. 앞으로 시술로 갚을 돈이라 매출과 따로 본다.
  const prepaidSum = cs.reduce((s, c) => s + Math.max(0, c.prepaid_balance || 0), 0);
  const prepaidN = cs.filter((c) => (c.prepaid_balance || 0) > 0).length;
  // 선불을 남긴 채 3개월 넘게 안 오신 분 — 고객 목록 '선불 3개월+'와 같은 기준(KST 오늘)
  const prepaidGone = cs.filter((c) => prepaidAway(c, kToday)).length;

  // 실매출 = 결제 금액 − 선불 잔액으로 결제된 금액.
  // 충전과 그 충전금으로 한 시술을 둘 다 더하면 이중 계상이라, 한 규칙으로 걷어낸다.
  const net = (t: { amount_won: number; covered_won: number | null }) =>
    (t.amount_won || 0) - (t.covered_won || 0);

  // 월별 매출(최근 6개월). 거래 날짜가 KST 라 '이번 달'도 KST 로 잡는다(엣지는 UTC).
  const [ky, km] = kstNow().date.split('-').map(Number);
  const months: { label: string; key: string; rev: number; partial: boolean }[] = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date(Date.UTC(ky, km - 1 - i, 1));
    months.push({
      label: `${d.getUTCMonth() + 1}월`,
      key: `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`,
      rev: 0,
      // 이번 달은 아직 안 끝났고, 게다가 수집이 주 1회라 마지막 며칠이 통째로 빠져 있다.
      // 다른 달과 같은 막대로 그리면 '이번 달 매출이 떨어졌다'로 잘못 읽힌다.
      partial: i === 0,
    });
  }
  const mmap = new Map(months.map((m) => [m.key, m]));
  for (const t of tx) {
    if (t.date) {
      const m = mmap.get(t.date.slice(0, 7));
      if (m) m.rev += net(t);
    }
  }
  // 달마다 영업한 날 — 휴가 간 달의 매출이 낮은 까닭이 막대 밑에 바로 보이게. 휴무를 정했을 때만.
  // 진행 중인 달은 마지막 수집일까지만 센다(그 뒤는 아직 비어 있다).
  const visitedDays = new Set(visits.map((v) => v.date));
  const showWork = hasOffDays(settings);
  const monthWork = months.map((m) => {
    const [y, mo] = m.key.split('-').map(Number);
    const end = m.partial ? asOf : new Date(Date.UTC(y, mo, 0)).toISOString().slice(0, 10);
    return workedDays(`${m.key}-01`, end, settings, visitedDays);
  });
  // ── 성별(시술명 추정) ──
  // 판정된 고객만으로 비교한다. 미상을 0으로 섞으면 평균이 무너지므로 분모에서 뺀다.
  // 추정이라 판정률을 함께 보여주지 않으면 오해를 부른다.
  type G = 'M' | 'F';
  const gStat: Record<G, { n: number; rev: number; visits: number; cyc: number[] }> = {
    M: { n: 0, rev: 0, visits: 0, cyc: [] },
    F: { n: 0, rev: 0, visits: 0, cyc: [] },
  };
  let gNoClue = 0;   // 성별이 적힌 시술을 받은 적이 없는 고객
  let gProxy = 0;    // 남·여가 섞여 대신 결제로 보이는 고객
  let gManual = 0;   // 디자이너가 직접 지정한 고객
  let kidCount = 0;
  for (const c of cs) {
    if (c.age_band === 'kid') kidCount++;
    // 사람이 지정했으면 그게 맞다 — 추정보다 우선한다.
    const picked = c.gender_manual === 'M' || c.gender_manual === 'F' ? c.gender_manual : null;
    if (picked) gManual++;
    const eff = picked ?? c.gender;
    const g = eff === 'M' || eff === 'F' ? (eff as G) : null;
    if (!g) {
      if (c.gender_src === 'proxy') gProxy++;
      else gNoClue++;
      continue;
    }
    gStat[g].n++;
    gStat[g].rev += c.total_won || 0;
    gStat[g].visits += c.visit_count || 0;
    if (c.revisit_cycle_days) gStat[g].cyc.push(c.revisit_cycle_days);
  }
  const gDecided = gStat.M.n + gStat.F.n;
  const gRev = gStat.M.rev + gStat.F.rev;
  const median = (xs: number[]) => {
    if (!xs.length) return 0;
    const a = [...xs].sort((x, y) => x - y);
    return a[Math.floor(a.length / 2)];
  };
  const gOne = (g: G) => ({
    n: gStat[g].n,
    perVisit: gStat[g].visits ? Math.round(gStat[g].rev / gStat[g].visits) : 0,
    cycle: median(gStat[g].cyc),
    share: gRev ? Math.round((gStat[g].rev / gRev) * 100) : 0,
  });
  const gender: GenderStat = {
    M: gOne('M'),
    F: gOne('F'),
    unknown: gNoClue + gProxy,
    noClue: gNoClue,
    proxy: gProxy,
    manual: gManual,
    rate: totalCustomers ? Math.round((gDecided / totalCustomers) * 100) : 0,
    kids: kidCount,
    total: totalCustomers,
  };

  // ── 이번 달 (지난달 같은 기간과 비교) ──
  // 누적 매출은 평생 수치라 보고 나서 할 게 없다. 진행 중인 달을 지난달 '같은 날짜까지'와
  // 견줘야 늘었는지 줄었는지가 판단이 된다(달 전체와 비교하면 월초엔 늘 줄어 보인다).
  // 그 '같은 날짜'는 오늘이 아니라 마지막 수집일 — 수집 뒤 날짜는 아직 비어 있어 이번 달만 손해를 본다.
  const thisMonth = kToday.slice(0, 7);
  const dayOfMonth = Number((asOf.slice(0, 7) === thisMonth ? asOf : kToday).slice(8, 10));
  const prevMonth = (() => {
    const [y, m] = thisMonth.split('-').map(Number);
    return m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, '0')}`;
  })();
  const period = { now: { rev: 0, visits: 0 }, prev: { rev: 0, visits: 0 } };
  const which = (date: string) => {
    if (Number(date.slice(8, 10)) > dayOfMonth) return null; // 지난달도 같은 날짜까지만
    const mm = date.slice(0, 7);
    return mm === thisMonth ? period.now : mm === prevMonth ? period.prev : null;
  };
  for (const t of tx) {
    const b = t.date ? which(t.date) : null;
    if (b) b.rev += net(t);
  }
  // 방문은 거래 건수가 아니라 시술 방문 수 — 충전 한 건·같은 날 두 시술이 방문을 부풀리지 않게
  for (const v of visits) {
    const b = which(v.date);
    if (b) b.visits++;
  }
  // 쉰 날이 다르면 그대로 견줄 수 없다 — 영업한 날 하루 평균 매출로 견준다. 영업일이 같으면 그냥
  // 견준 것과 같은 숫자다(휴무를 안 정한 매장은 예전과 같다).
  const upTo = (ym: string) => {
    const [y, m] = ym.split('-').map(Number);
    const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
    return `${ym}-${String(Math.min(dayOfMonth, last)).padStart(2, '0')}`;
  };
  const work = {
    now: workedDays(`${thisMonth}-01`, upTo(thisMonth), settings, visitedDays),
    prev: workedDays(`${prevMonth}-01`, upTo(prevMonth), settings, visitedDays),
  };
  const revDelta =
    period.prev.rev > 0 && work.now > 0 && work.prev > 0
      ? Math.round(((period.now.rev / work.now - period.prev.rev / work.prev) / (period.prev.rev / work.prev)) * 100)
      : null;

  // ── 마감 예상 ── 이 속도면 이번 달 얼마(lib/forecast). 예약은 수집 때까지 잡힌 것뿐이라 금액에 섞지 않고
  // 남은 기간 잡힌 수만 곁에 둔다.
  const fc = monthForecast(tx, thisMonth, asOf, settings, visitedDays);
  const bkLeft = ((bkLeftRows as { date: string; time: string | null; status: string | null }[] | null) ?? [])
    .filter((b) => isActiveBooking(b)).length;

  // ── 다음 시술 추천이 맞았나 ── 최근 1년 방문마다 그 전 기록만으로 권했다면(lib/recommend backtest)
  // 1년을 되짚되 그 앞 1년 이력까지만 있으면 된다 — 2년치만 넘긴다(큰 매장에서 화면이 느려지지 않게)
  const recVisits = visitsByCustomer(tx.filter((t) => t.date >= addDays(asOf, -730)));
  const hits = backtest(recVisits, pairStats(recVisits, asOf), realIds, addDays(asOf, -364), asOf, settings);

  // ── 지금 할 일 ── 홈 신호와 같은 기준으로 센다(숫자가 다르면 어느 쪽을 믿을지 모른다)
  // 누르면 챙길 고객 탭이 열린다 — 그 목록과 같은 '할 일' 기준(최근 연락한 분 제외)
  // 첫 방문 손님(안부·다시 오실 때)도 함께 — 챙길 고객 탭·홈과 같은 숫자(lib/customers onFirstList)
  const flagsOf = (c: (typeof cs)[number]) =>
    ({ settings, churned: isChurned(c), booked: booked.has(c.id), contacted: contacted.has(c.id), asOf });
  const byIdCs = new Map(cs.map((c) => [c.id, c]));
  const oneSvcs = servicesOn(tx, (id) => (byIdCs.get(id)?.visit_count === 1 ? byIdCs.get(id)?.last_visit : null));
  const careCount =
    cs.filter((c) => onCareList(c, flagsOf(c))).length +
    cs.filter((c) => c.visit_count === 1 && onFirstList(c, oneSvcs.get(c.id) ?? [], flagsOf(c))).length;

  const span = dayOfMonth > 1 ? `1–${dayOfMonth}일` : '1일';

  // 연락 효과 — 실고객만(워크인 집계는 연락 대상이 아니다). byCust = 손님별 방문일(오름차순)
  const realContacts = contactRows.filter((r) => r.customer_id && realIds.has(r.customer_id));
  const contactSince = realContacts.map((r) => (r.sent_at ? kstDay(r.sent_at) : '')).filter(Boolean).sort()[0] ?? null;
  const realVisits = new Map([...byCust].filter(([id]) => realIds.has(id)));

  return (
    <main className="wrap">
      <div className="bar">
        <BackButton />
        <div className="ttl" style={{ marginLeft: 10 }}>통계</div>
        <SyncChip synced={synced} />
      </div>
      <div className="body">
        {/* 이번 달 잘 되고 있나 + 할 일 — 누적 수치는 보고 나서 할 게 없어 '더 보기'로 */}
        <SummaryCard
          span={span}
          work={showWork || work.now !== work.prev ? work : null}
          rev={period.now.rev}
          revDelta={revDelta}
          visits={period.now.visits}
          prevVisits={period.prev.visits}
          fc={fc}
          bkLeft={bkLeft}
          active={active}
          prepaid={{ sum: prepaidSum, n: prepaidN }}
          careCount={careCount}
          unknownGender={gNoClue + gProxy}
          prepaidGone={prepaidGone}
        />

        {/* 평생 재방문율(두 번 이상/전체)은 최근 변화가 안 보인다 → 최근 신규가 다시 오는지로 */}
        <CohortCard
          cohorts={cohort.cohorts}
          medianDays={cohort.medianDays}
          repeat={repeatCust}
          total={totalCustomers}
          vacation={settings.off_dates.length > 0}
        />
        {/* 요일만 보던 막대를 요일 × 시간대로 — 같은 요일도 오전과 저녁은 다르다 */}
        <HeatCard heat={heat} hasOff={showWork} />
        <MonthCard months={months} work={showWork ? monthWork : null} syncLabel={synced ? shortDate(synced.date) : null} />

        {/* 자주 볼 일 없는 것들 — 접어 둔다(UX 계획 v3 결정 5) */}
        <details className="more-sec">
          <summary>더 보기 <span className="sect-n">시술별 · 성별 · 연락 효과 · 적중률 · 누적</span></summary>
          <ServiceCard rows={svcRows} vacation={settings.off_dates.length > 0} />
          {gDecided > 0 ? <GenderCard g={gender} /> : null}
          <ContactEffectCard
            groups={contactEffectByGroup(realContacts, realVisits, booked)}
            hello={helloEffect(realContacts, realVisits)}
            since={contactSince}
          />
          <RecommendHitCard hits={hits} />
          <TotalsCard customers={totalCustomers} revenue={totalRevenue} tx={tx.length} />
        </details>
      </div>
    </main>
  );
}
