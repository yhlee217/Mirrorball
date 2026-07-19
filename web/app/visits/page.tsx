export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import { fetchAllRows, isRealCustomer } from '@/lib/customers';
import { friendlyService } from '@/lib/service-name';
import { careFor } from '@/lib/care-cycle';
import { kstNow } from '@/lib/kst';
import VisitsList from './visits-list';

// 방문 관리 — '다녀가신 분'을 챙기는 화면(알림 탭이 '아직 안 오신 분'을 챙기는 것과 짝).
// 리뷰 요청 문구는 원래 노출 탭에 있었는데, 성격상 고객 관리라 이쪽으로 옮겼다.

type Tx = { customer_id: string | null; date: string; time: string | null; service: string | null; amount_won: number };
type Cust = { id: string; ext_id: string | null; pii_enc: string | null; visit_count: number };

const DAY = 86400000;
const KST = 9 * 3600000;

export default async function VisitsPage() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) redirect('/');
  const tenantId = (mem as { tenant_id: string }).tenant_id;

  const today = kstNow().date;
  const since = new Date(Date.now() + KST - 13 * DAY).toISOString().slice(0, 10); // 최근 14일

  const [{ data: tenant }, txs] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped').eq('id', tenantId).maybeSingle(),
    fetchAllRows<Tx>((from, to) =>
      supabase
        .from('transactions')
        .select('customer_id,date,time,service,amount_won')
        .gte('date', since)
        .order('id')
        .range(from, to)),
  ]);

  // 같은 날 여러 시술은 한 번의 방문으로 묶는다.
  const byVisit = new Map<
    string,
    { customer_id: string; date: string; time: string | null; services: string[]; amount: number }
  >();
  for (const t of txs) {
    if (!t.customer_id || !t.date) continue;
    const k = `${t.customer_id}|${t.date}`;
    const e = byVisit.get(k) ?? { customer_id: t.customer_id, date: t.date, time: null, services: [], amount: 0 };
    if (t.service) e.services.push(t.service);
    e.amount += t.amount_won || 0;
    if (t.time && (!e.time || t.time < e.time)) e.time = t.time; // 같은 날 여러 건이면 가장 이른 시각 = 방문 시각
    byVisit.set(k, e);
  }
  const visits = [...byVisit.values()]
    .sort((a, b) => (a.date !== b.date ? (a.date < b.date ? 1 : -1) : (a.time ?? '') < (b.time ?? '') ? 1 : -1))
    .slice(0, 60);

  const ids = [...new Set(visits.map((v) => v.customer_id))];
  const custs: Cust[] = ids.length
    ? (((await supabase.from('customers').select('id,ext_id,pii_enc,visit_count').in('id', ids)).data as Cust[]) ?? [])
    : [];
  const cmap = new Map(custs.map((c) => [c.id, c]));

  const dw = (tenant as { dek_wrapped: string | null } | null)?.dek_wrapped ?? null;
  let dek: Uint8Array | null = null;
  if (dw) {
    try {
      dek = await unwrapDek(dw);
    } catch {
      dek = null;
    }
  }
  const nameFrom = async (pii: string | null): Promise<string> => {
    if (!dek || !pii) return '고객';
    try {
      const p = await decryptPII(pii, dek);
      return typeof p.name === 'string' && p.name ? p.name : '고객';
    } catch {
      return '고객';
    }
  };

  const items = await Promise.all(
    visits
      .filter((v) => isRealCustomer(cmap.get(v.customer_id)?.ext_id ?? null))
      .map(async (v) => {
        const c = cmap.get(v.customer_id)!;
        const name = await nameFrom(c.pii_enc);
        const rawMain = v.services[0] ?? null;
        const svc = [...new Set(v.services.map((s) => friendlyService(s)).filter(Boolean))].join(' + ');
        return {
          id: v.customer_id,
          name,
          date: v.date,
          time: v.time,
          service: svc,
          amount: v.amount,
          visit_count: c.visit_count,
          tip: careFor(rawMain)?.tip ?? '', // 그날 받은 시술의 홈케어 안내
        };
      }),
  );

  const yesterday = new Date(Date.now() + KST - DAY).toISOString().slice(0, 10);

  return (
    <main className="wrap">
      <div className="body">
        <div className="hello">
          <div className="e">
            <span>Visits</span>
          </div>
          <h2>방문 관리</h2>
          <div className="s">최근 다녀가신 분 — 리뷰 요청하고 메모 남기기 좋아요</div>
        </div>
        <VisitsList items={items} today={today} yesterday={yesterday} />
      </div>
    </main>
  );
}
