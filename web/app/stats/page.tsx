export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { fetchAllRows } from '@/lib/customers';

function won(n: number): string {
  if (!n) return '0원';
  if (n >= 100000000) return (n / 100000000).toFixed(1) + '억원';
  if (n >= 10000) return Math.round(n / 10000).toLocaleString() + '만원';
  return n.toLocaleString() + '원';
}

const DOW = ['일', '월', '화', '수', '목', '금', '토'];

export default async function StatsPage() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) redirect('/');
  const tenantId = (mem as { tenant_id: string }).tenant_id;

  const [customers, txs] = await Promise.all([
    fetchAllRows<{ total_won: number; visit_count: number }>((from, to) =>
      supabase.from('customers').select('total_won,visit_count').eq('tenant_id', tenantId).order('id').range(from, to)),
    fetchAllRows<{ date: string; service: string | null; amount_won: number }>((from, to) =>
      supabase.from('transactions').select('date,service,amount_won').eq('tenant_id', tenantId).order('id').range(from, to)),
  ]);
  const cs = customers;
  const tx = txs;

  const totalRevenue = cs.reduce((s, c) => s + (c.total_won || 0), 0);
  const totalCustomers = cs.length;
  const totalVisits = tx.length;
  const avgPer = totalCustomers ? Math.round(totalRevenue / totalCustomers / 10000) : 0;

  // 리텐션(재방문율)
  const repeatCust = cs.filter((c) => c.visit_count >= 2).length;
  const newCust = totalCustomers - repeatCust;
  const retention = totalCustomers ? Math.round((repeatCust / totalCustomers) * 100) : 0;

  // 월별 매출(최근 6개월)
  const now = new Date();
  const months: { label: string; key: string; rev: number }[] = [];
  for (let i = 5; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push({ label: `${d.getMonth() + 1}월`, key: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`, rev: 0 });
  }
  const mmap = new Map(months.map((m) => [m.key, m]));
  for (const t of tx) {
    if (t.date) {
      const m = mmap.get(t.date.slice(0, 7));
      if (m) m.rev += t.amount_won || 0;
    }
  }
  const maxRev = Math.max(1, ...months.map((m) => m.rev));

  // 요일별 방문
  const days = DOW.map((label) => ({ label, count: 0 }));
  for (const t of tx) {
    if (t.date) {
      const g = new Date(t.date).getDay();
      if (g >= 0 && g <= 6) days[g].count++;
    }
  }
  const maxDow = Math.max(1, ...days.map((d) => d.count));

  // 시술별(건수 + 매출)
  const svc = new Map<string, { n: number; rev: number }>();
  for (const t of tx) {
    const s = (t.service || '').trim();
    if (!s) continue;
    const e = svc.get(s) || { n: 0, rev: 0 };
    e.n++;
    e.rev += t.amount_won || 0;
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

        <div className="card" style={{ padding: '14px 15px' }}>
          <div className="ch" style={{ padding: 0, marginBottom: 10 }}>월별 매출 (최근 6개월 · 만원)</div>
          <div className="bars">
            {months.map((m) => (
              <div className="b" key={m.key}>
                <div className="bv">{Math.round(m.rev / 10000)}</div>
                <div className="bar2" style={{ height: `${Math.round((m.rev / maxRev) * 80) + 3}px` }} />
                <div className="bl">{m.label}</div>
              </div>
            ))}
          </div>
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
