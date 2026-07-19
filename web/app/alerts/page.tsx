export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import { fetchAllRows, isRealCustomer } from '@/lib/customers';
import { mergeSettings, isLapsed } from '@/lib/settings';
import { friendlyService } from '@/lib/service-name';
import { careFor } from '@/lib/care-cycle';
import AlertsList from './alerts-list';

type Cust = {
  id: string;
  ext_id: string | null;
  pii_enc: string | null;
  revisit_state: string | null;
  revisit_cycle_days: number | null;
  last_visit: string | null;
  visit_count: number;
};

export default async function AlertsPage() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) redirect('/');
  const tenantId = (mem as { tenant_id: string }).tenant_id;

  const [{ data: tenant }, customers] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped,settings').eq('id', tenantId).maybeSingle(),
    fetchAllRows<Cust>((from, to) =>
      supabase.from('customers').select('id,ext_id,pii_enc,revisit_state,revisit_cycle_days,last_visit,visit_count').in('revisit_state', ['overdue', 'due']).order('id').range(from, to)),
  ]);

  const tRow = tenant as { dek_wrapped: string | null; settings: unknown } | null;
  const settings = mergeSettings(tRow?.settings);
  let dek: Uint8Array | null = null;
  const dw = tRow?.dek_wrapped ?? null;
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
      return typeof p.name === 'string' ? p.name : '고객';
    } catch {
      return '고객';
    }
  };

  const base = ((customers as Cust[]) ?? [])
    .filter((c) => isRealCustomer(c.ext_id) && !isLapsed(c, settings))
    .sort((a, b) => (a.revisit_state === 'overdue' ? 0 : 1) - (b.revisit_state === 'overdue' ? 0 : 1) || b.visit_count - a.visit_count)
    .slice(0, 50);
  const names = await Promise.all(base.map((c) => nameFrom(c.pii_enc)));

  // 개인화용: 각 고객의 마지막 시술
  const ids = base.map((c) => c.id);
  const lastSvc = new Map<string, string>();
  if (ids.length) {
    const { data: txs } = await supabase
      .from('transactions')
      .select('customer_id,date,service')
      .in('customer_id', ids)
      .order('date', { ascending: false })
      .limit(3000);
    for (const t of (txs as { customer_id: string | null; service: string | null }[]) ?? []) {
      if (t.customer_id && t.service && !lastSvc.has(t.customer_id)) lastSvc.set(t.customer_id, t.service);
    }
  }
  const monthsOf = (d: string | null) => (d ? Math.max(1, Math.round((Date.now() - new Date(d).getTime()) / 2592000000)) : null);

  const items = base.map((c, i) => {
    const name = names[i];
    const m = monthsOf(c.last_visit);
    const rawSvc = lastSvc.get(c.id);
    const svc = friendlyService(rawSvc); // 고객 문구용(직급·성별 표기 제거)
    const care = careFor(rawSvc); // 시술별 표준 관리주기·표현(분류는 원본 메뉴명으로)
    const loyal = c.visit_count >= settings.vip_visits;
    const std = care ? ` · ${care.cat} 표준 ${care.days}일` : '';
    const why =
      c.revisit_state === 'overdue'
        ? `마지막 방문 ${c.last_visit ?? '-'}${m ? ` · ${m}개월 미방문` : ''} · 평소 ${c.revisit_cycle_days ?? '-'}일 주기${std}`
        : `재방문 시기 · 마지막 방문 ${c.last_visit ?? '-'}${c.revisit_cycle_days ? ` · 주기 ${c.revisit_cycle_days}일` : ''}${std}`;
    let draft: string;
    if (c.revisit_state === 'overdue') {
      const open = loyal
        ? `${name}님, 오랜만이에요! 벌써 ${m}개월 됐네요. 늘 찾아주셔서 감사해요 🙏`
        : `${name}님, ${m ? m + '개월 만이에요' : '오랜만이에요'}! 잘 지내셨어요? 😊`;
      const mid =
        care && svc
          ? ` 지난 ${svc} ${care.phrase} 한번 뵙고 싶어서 연락드려요.`
          : svc
            ? ` 지난 ${svc} 이제 슬슬 관리할 시기라 생각나서 연락드려요.`
            : ` 슬슬 컨디션 체크 겸 한번 뵙고 싶어서요.`;
      draft = `${open}${mid} 편하신 때 편하게 연락 주세요!`;
    } else {
      draft =
        care && svc
          ? `${name}님, 지난 ${svc} ${care.phrase} 연락드려요. 편하신 시간에 예약 도와드릴게요!`
          : `${name}님, ${svc ? '지난 ' + svc : '지난 시술'} 이제 관리해주실 시기예요${c.revisit_cycle_days ? ` (평소 ${c.revisit_cycle_days}일 주기)` : ''}. 편하신 시간에 예약 도와드릴게요!`;
    }
    return { id: c.id, name, state: c.revisit_state as string, why, draft };
  });

  return (
    <main className="wrap">
      <div className="bar">
        <div className="ttl">오늘 챙길 고객</div>
      </div>
      <div className="body">
        <div className="sec-h">자동 발송 X · 문구만 복사해서 직접</div>
        <AlertsList items={items} />
      </div>
    </main>
  );
}
