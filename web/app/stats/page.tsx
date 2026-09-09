export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { won } from '@/lib/format';
import { requireTenant } from '@/lib/tenant';
import { kstNow } from '@/lib/kst';
import { lastSynced } from '@/lib/sync';
import { txKind } from '@/lib/tx';
import { fetchAllRows, isRealCustomer, isChurned } from '@/lib/customers';
import { isLapsed, mergeSettings } from '@/lib/settings';

const DOW = ['일', '월', '화', '수', '목', '금', '토'];

export default async function StatsPage() {
  const { supabase, tenantId } = await requireTenant();

  const [{ data: tenant }, customers, txs] = await Promise.all([
    supabase.from('tenants').select('settings').eq('id', tenantId).maybeSingle(),
    fetchAllRows<{ ext_id: string | null; total_won: number; visit_count: number; gender: string | null;
                   age_band: string | null; gender_src: string | null; gender_manual: string | null; revisit_cycle_days: number | null;
                   revisit_state: string | null; churned_at: string | null; last_visit: string | null;
                   visits_90d: number | null; visits_180d: number | null; visits_365d: number | null }>((from, to) =>
      supabase.from('customers')
        .select('ext_id,total_won,visit_count,gender,gender_manual,age_band,gender_src,revisit_cycle_days,revisit_state,churned_at,last_visit,visits_90d,visits_180d,visits_365d')
        .eq('tenant_id', tenantId).order('id').range(from, to)),
    fetchAllRows<{ date: string; service: string | null; amount_won: number; kind: string | null; covered_won: number | null }>((from, to) =>
      supabase.from('transactions').select('date,service,amount_won,kind,covered_won').eq('tenant_id', tenantId).order('id').range(from, to)),
  ]);
  // '손님' 등 미식별 워크인은 관리 대상이 아니다 — 홈·챙길 고객·고객목록과 같은 기준으로 뺀다.
  // 통계만 포함하고 있어서 고객수·재방문율·객단가가 부풀고, 성별은 전부 '미상'으로 쌓였다.
  // 이탈 판정 기준(설정)을 따라야 홈 신호와 숫자가 어긋나지 않는다.
  const settings = mergeSettings((tenant as { settings: unknown } | null)?.settings);
  const cs = customers.filter((c) => isRealCustomer(c.ext_id));
  const tx = txs;

  const totalRevenue = cs.reduce((s, c) => s + (c.total_won || 0), 0);
  const totalCustomers = cs.length;
  const totalVisits = tx.length;
  const avgPer = totalCustomers ? Math.round(totalRevenue / totalCustomers / 10000) : 0;

  // 리텐션(재방문율)
  const repeatCust = cs.filter((c) => c.visit_count >= 2).length;
  const newCust = totalCustomers - repeatCust;
  const retention = totalCustomers ? Math.round((repeatCust / totalCustomers) * 100) : 0;

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
  const maxRev = Math.max(1, ...months.map((m) => m.rev));
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
  const gRate = totalCustomers ? Math.round((gDecided / totalCustomers) * 100) : 0;
  const gRev = gStat.M.rev + gStat.F.rev;
  const median = (xs: number[]) => {
    if (!xs.length) return 0;
    const a = [...xs].sort((x, y) => x - y);
    return a[Math.floor(a.length / 2)];
  };
  const perVisit = (g: G) => (gStat[g].visits ? Math.round(gStat[g].rev / gStat[g].visits) : 0);

  // ── 이번 달 (지난달 같은 기간과 비교) ──
  // 누적 매출은 평생 수치라 보고 나서 할 게 없다. 진행 중인 달을 지난달 '같은 날짜까지'와
  // 견줘야 늘었는지 줄었는지가 판단이 된다(달 전체와 비교하면 월초엔 늘 줄어 보인다).
  const kToday = kstNow().date;
  const dayOfMonth = Number(kToday.slice(8, 10));
  const thisMonth = kToday.slice(0, 7);
  const prevMonth = (() => {
    const [y, m] = thisMonth.split('-').map(Number);
    return m === 1 ? `${y - 1}-12` : `${y}-${String(m - 1).padStart(2, '0')}`;
  })();
  const period = { now: { rev: 0, visits: 0 }, prev: { rev: 0, visits: 0 } };
  for (const t of tx) {
    if (!t.date) continue;
    const mm = t.date.slice(0, 7);
    const dd = Number(t.date.slice(8, 10));
    if (dd > dayOfMonth) continue;               // 지난달도 같은 날짜까지만
    if (mm === thisMonth) { period.now.rev += net(t); period.now.visits++; }
    else if (mm === prevMonth) { period.prev.rev += net(t); period.prev.visits++; }
  }
  const revDelta = period.prev.rev ? Math.round(((period.now.rev - period.prev.rev) / period.prev.rev) * 100) : null;

  // ── 지금 할 일 ── 홈 신호와 같은 기준으로 센다(숫자가 다르면 어느 쪽을 믿을지 모른다)
  let careCount = 0;
  for (const c of cs) {
    if (isChurned(c)) continue;
    if ((c.revisit_state === 'overdue' || c.revisit_state === 'due') && !isLapsed(c, settings)) careCount++;
  }

  const synced = await lastSynced(supabase);

  // 요일별 방문
  const days = DOW.map((label) => ({ label, count: 0 }));
  for (const t of tx) {
    if (t.date) {
      const g = new Date(t.date).getDay();
      if (g >= 0 && g <= 6) days[g].count++;
    }
  }
  const maxDow = Math.max(1, ...days.map((d) => d.count));
  // 막대만 보고 '그래서 뭘 하지'를 떠올리긴 어렵다 — 가장 붐비는/한산한 요일을 말로 짚어준다.
  const busiest = days.reduce((a, b) => (b.count > a.count ? b : a));
  const quietest = days.filter((d) => d.count > 0).reduce((a, b) => (b.count < a.count ? b : a), days[0]);

  // 시술별(건수 + 매출)
  const svc = new Map<string, { n: number; rev: number }>();
  for (const t of tx) {
    const s = (t.service || '').trim();
    if (!s) continue;
    const e = svc.get(s) || { n: 0, rev: 0 };
    e.n++;
    e.rev += net(t);
    svc.set(s, e);
  }
  const topSvc = [...svc.entries()].sort((a, b) => b[1].n - a[1].n).slice(0, 6);
  const maxSvc = Math.max(1, ...topSvc.map(([, v]) => v.n));

  return (
    <main className="wrap">
      <div className="bar">
        <Link href="/" className="back">‹ 홈</Link>
        <div className="ttl" style={{ marginLeft: 10 }}>기록 · 통계</div>
      </div>
      <div className="body">
        {/* 이번 달 — 누적 수치는 보고 나서 할 게 없다. 지난달 같은 날짜까지와 견줘야 판단이 된다. */}
        <div className="card" style={{ padding: '14px 15px' }}>
          <div className="ch" style={{ padding: 0, marginBottom: 8 }}>
            이번 달 <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: 10 }}>
              · {dayOfMonth}일까지 · 지난달 같은 기간과 비교</span>
          </div>
          <div className="mth">
            <div>
              <span className="ml">매출</span>
              <b>{won(period.now.rev)}</b>
              {revDelta !== null && (
                <span className={'delta ' + (revDelta >= 0 ? 'up' : 'down')}>
                  {revDelta >= 0 ? '▲' : '▼'} {Math.abs(revDelta)}%
                </span>
              )}
            </div>
            <div>
              <span className="ml">방문</span>
              <b>{period.now.visits.toLocaleString()}건</b>
              <span className="delta">지난달 {period.prev.visits.toLocaleString()}건</span>
            </div>
          </div>
        </div>

        {/* 지금 할 일 — 통계를 보고 '그래서 뭘 하지'로 이어지게. 숫자는 홈 신호와 같은 기준. */}
        {(careCount > 0 || gNoClue + gProxy > 0) && (
          <div className="card todo">
            <div className="ch">지금 할 일</div>
            {careCount > 0 && (
              <Link href="/alerts" className="li li-link">
                <div className="bd">
                  <div className="nm">챙길 고객 {careCount.toLocaleString()}명</div>
                  <div className="sub">재방문 시기가 됐거나 오래 안 오신 분들이에요</div>
                </div>
                <span className="rt" style={{ fontSize: 18, color: '#B4B2A9' }} aria-hidden>›</span>
              </Link>
            )}
            {gNoClue + gProxy > 0 && (
              <Link href="/customers?filter=nogender" className="li li-link">
                <div className="bd">
                  <div className="nm">성별 미상 {(gNoClue + gProxy).toLocaleString()}명</div>
                  <div className="sub">아는 분만 채우면 아래 성별 비교가 정확해져요</div>
                </div>
                <span className="rt" style={{ fontSize: 18, color: '#B4B2A9' }} aria-hidden>›</span>
              </Link>
            )}
          </div>
        )}

        <div className="stat-grid">
          <div className="stat"><div className="sn">{won(totalRevenue)}</div><div className="sl">누적 매출</div></div>
          <div className="stat"><div className="sn">{totalVisits.toLocaleString()}</div><div className="sl">누적 방문</div></div>
          <div className="stat"><div className="sn">{totalCustomers.toLocaleString()}</div><div className="sl">전체 고객</div></div>
          <div className="stat"><div className="sn">{avgPer.toLocaleString()}만원</div><div className="sl">고객당 평균</div></div>
        </div>

        <div className="card" style={{ padding: '14px 15px' }}>
          <div className="ch" style={{ padding: 0, marginBottom: 8 }}>재방문율 (리텐션)</div>
          <div className="reten">
            <div className="reten-n">{retention}%</div>
            <div className="reten-b">
              <div className="reten-fill" style={{ width: `${retention}%` }} />
            </div>
          </div>
          <div className="set-row" style={{ marginTop: 6, color: 'var(--muted)' }}>
            재방문 고객 {repeatCust.toLocaleString()}명 · 신규(1회) {newCust.toLocaleString()}명
          </div>
        </div>

        {gDecided > 0 && (
          <div className="card" style={{ padding: '14px 15px' }}>
            <div className="ch" style={{ padding: 0, marginBottom: 10 }}>
              고객 성별 <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: 10 }}>· 시술명 추정</span>
            </div>

            {/* ① 구성 — 판정된 고객 기준임을 막대에서도 드러낸다 */}
            <div className="gbar">
              <div className="gm" style={{ width: `${Math.round((gStat.M.n / totalCustomers) * 100)}%` }} />
              <div className="gf" style={{ width: `${Math.round((gStat.F.n / totalCustomers) * 100)}%` }} />
              <div className="gu" style={{ width: `${Math.round(((gNoClue + gProxy) / totalCustomers) * 100)}%` }} />
            </div>
            <div className="glegend">
              <span><i className="gm" />남성 {gStat.M.n.toLocaleString()}명</span>
              <span><i className="gf" />여성 {gStat.F.n.toLocaleString()}명</span>
              <span><i className="gu" />미상 {(gNoClue + gProxy).toLocaleString()}명</span>
            </div>

            {/* ②③ 객단가·재방문 주기·매출 비중 — 판정된 고객끼리만 비교 */}
            <div className="tablewrap" style={{ marginTop: 12 }}>
              <table className="gtab">
                <thead>
                  <tr><th></th><th>남성</th><th>여성</th></tr>
                </thead>
                <tbody>
                  <tr>
                    <td>고객</td>
                    <td>{gStat.M.n.toLocaleString()}명</td>
                    <td>{gStat.F.n.toLocaleString()}명</td>
                  </tr>
                  <tr>
                    <td>객단가<span className="sub2">방문 1회당</span></td>
                    <td>{won(perVisit('M'))}</td>
                    <td>{won(perVisit('F'))}</td>
                  </tr>
                  <tr>
                    <td>재방문 주기<span className="sub2">중앙값</span></td>
                    <td>{median(gStat.M.cyc) || '-'}일</td>
                    <td>{median(gStat.F.cyc) || '-'}일</td>
                  </tr>
                  <tr>
                    <td>매출 비중<span className="sub2">판정 고객 중</span></td>
                    <td>{gRev ? Math.round((gStat.M.rev / gRev) * 100) : 0}%</td>
                    <td>{gRev ? Math.round((gStat.F.rev / gRev) * 100) : 0}%</td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* ④ 아동·학생 */}
            {kidCount > 0 && (
              <div className="set-row" style={{ marginTop: 10 }}>
                본인이 아동·학생으로 보이는 고객 <b>{kidCount.toLocaleString()}명</b>
                <span style={{ color: 'var(--muted)' }}> ({Math.round((kidCount / totalCustomers) * 100)}%)</span>
              </div>
            )}

            <p className="note">
              메뉴에 성별이 적힌 시술(남자컷·여자컷 등)로 추정해 <b>{gRate}%</b>가 판정됐어요
              {gManual > 0 ? <> (그중 <b>{gManual.toLocaleString()}명</b>은 직접 지정)</> : null}.
              미상인 고객은 카르테에서 성별을 직접 지정하면 바로 반영됩니다.
              미상 {(gNoClue + gProxy).toLocaleString()}명은 —
              성별이 적힌 시술을 받은 적이 없는 고객 <b>{gNoClue.toLocaleString()}명</b>
              (다운펌·앞머리컷·뿌리염색처럼 메뉴에 성별이 없는 시술만 받은 경우)과,
              남·여가 섞여 대신 결제로 보이는 고객 <b>{gProxy.toLocaleString()}명</b>입니다.
              둘 다 위 비교에서 제외했어요. 미상 고객은 방문 횟수가 평균의 절반 수준이라
              객단가·주기 비교에 미치는 영향은 크지 않습니다.
            </p>
          </div>
        )}

        <div className="card" style={{ padding: '14px 15px' }}>
          <div className="ch" style={{ padding: 0, marginBottom: 10 }}>월별 매출 (최근 6개월 · 만원)</div>
          <div className="bars">
            {months.map((m) => (
              <div className="b" key={m.key}>
                <div className="bv">{Math.round(m.rev / 10000)}</div>
                <div
                  className={`bar2${m.partial ? ' partial' : ''}`}
                  style={{ height: `${Math.round((m.rev / maxRev) * 80) + 3}px` }}
                />
                <div className="bl">{m.label}{m.partial ? '*' : ''}</div>
              </div>
            ))}
          </div>
          <p className="note">
            * 이번 달은 아직 진행 중이고{synced ? ` ${synced.label} 수집 기준이라` : ' 수집 시점 기준이라'} 마지막 며칠이 빠져 있어요.
            다른 달과 바로 비교하지 마세요.
          </p>
        </div>

        <div className="card" style={{ padding: '14px 15px' }}>
          <div className="ch" style={{ padding: 0, marginBottom: 10 }}>요일별 방문</div>
          <div className="bars">
            {days.map((d) => (
              <div className="b" key={d.label}>
                <div className="bv">{d.count}</div>
                <div className="bar2 sage" style={{ height: `${Math.round((d.count / maxDow) * 80) + 3}px` }} />
                <div className="bl">{d.label}</div>
              </div>
            ))}
          </div>
          {busiest.count > 0 && busiest.label !== quietest.label && (
            <p className="note">
              <b>{busiest.label}요일</b>이 가장 붐비고 <b>{quietest.label}요일</b>이 가장 한산해요.
              한산한 날로 예약을 옮겨드릴 수 있는 분이 있는지 살펴보세요.
            </p>
          )}
        </div>

        <div className="card" style={{ padding: '14px 15px' }}>
          <div className="ch" style={{ padding: 0, marginBottom: 10 }}>시술별 (건수 · 매출)</div>
          {topSvc.length ? (
            topSvc.map(([s, v]) => (
              <div className="svc" key={s}>
                <div className="svn">{s}</div>
                <div className="svbar"><div className="svfill" style={{ width: `${Math.round((v.n / maxSvc) * 100)}%` }} /></div>
                <div className="svc-c">{v.n}건<br />{won(v.rev)}</div>
              </div>
            ))
          ) : (
            <div className="empty">시술 데이터가 없어요</div>
          )}
        </div>

        <p className="note">거래 {totalVisits.toLocaleString()}건 · 고객 {totalCustomers.toLocaleString()}명 기준.</p>
      </div>
    </main>
  );
}
