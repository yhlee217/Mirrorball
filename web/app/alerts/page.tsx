export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { contactReader, openDek, requireTenant } from '@/lib/tenant';
import { careState, fetchAllRows, isRealCustomer, isChurned, needsCare, onCareList } from '@/lib/customers';
import { mergeSettings } from '@/lib/settings';
import { bookedCustomerIds } from '@/lib/bookings';
import { CONTACT_QUIET_DAYS, phoneDigits, recentlyContactedIds } from '@/lib/contact';
import { friendlyService } from '@/lib/service-name';
import { careFor } from '@/lib/care-cycle';
import { lastSynced, syncLine } from '@/lib/sync';
import { kstNow } from '@/lib/kst';
import { daysBetween } from '@/lib/week';
import { awayDays } from '@/lib/offdays';
import AlertsList from './alerts-list';

type Cust = {
  id: string;
  ext_id: string | null;
  pii_enc: string | null;
  revisit_state: string | null;
  revisit_cycle_days: number | null;
  last_visit: string | null;
  visit_count: number;
  churned_at: string | null;
};

export default async function AlertsPage() {
  const { supabase, tenantId } = await requireTenant();

  const [{ data: tenant }, customers, booked, contacted, synced] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped,settings').eq('id', tenantId).maybeSingle(),
    fetchAllRows<Cust>((from, to) =>
      supabase.from('customers').select('id,ext_id,pii_enc,revisit_state,revisit_cycle_days,last_visit,visit_count,churned_at').in('revisit_state', ['overdue', 'due']).order('id').range(from, to)),
    bookedCustomerIds(supabase, tenantId), // 이미 예약한 분께 '예약 도와드릴게요'를 보내지 않게
    recentlyContactedIds(supabase, tenantId), // 최근 연락한 분은 할 일에서 잠시 뺀다
    lastSynced(supabase), // 재방문 판정의 기준일(워커가 판정한 날) — 휴가를 빼고 셀 때 쓴다
  ]);

  const tRow = tenant as { dek_wrapped: string | null; settings: unknown } | null;
  const settings = mergeSettings(tRow?.settings);
  const dek = await openDek(tRow?.dek_wrapped);
  const readContact = contactReader(dek);

  // 재방문 상태는 휴가를 반영한 것(careState) — 휴가 동안은 손님이 오고 싶어도 못 왔다.
  // DB 에서 due·overdue 만 받아도 되는 건, 휴가 반영은 판정을 늦추기만 하고 앞당기지 않아서다.
  const asOf = synced?.date ?? kstNow().date;
  const stateOf = (c: Cust) => careState(c, settings, asOf);
  const flags = (c: Cust) => ({ settings, churned: isChurned(c), booked: booked.has(c.id), contacted: contacted.has(c.id), asOf });
  const real = ((customers as Cust[]) ?? []).filter((c) => isRealCustomer(c.ext_id));
  // 연락해서 잠시 빠진 분 — 목록이 왜 줄었는지 밝힌다
  const quiet = real.filter((c) => needsCare(c, flags(c)) && contacted.has(c.id)).length;
  const base = real
    .filter((c) => onCareList(c, flags(c)))
    .sort((a, b) => (stateOf(a) === 'overdue' ? 0 : 1) - (stateOf(b) === 'overdue' ? 0 : 1) || b.visit_count - a.visit_count)
    .slice(0, 50);
  const contacts = await Promise.all(base.map((c) => readContact(c.pii_enc)));
  const names = contacts.map((x) => x.name);

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
    const state = stateOf(c) as string;
    // 휴가를 빼고 셌으면 밝힌다 — 달력으로 세면 더 오래돼 보이는데 판정이 늦은 까닭
    const vac = c.last_visit ? daysBetween(c.last_visit.slice(0, 10), asOf) - awayDays(c.last_visit.slice(0, 10), asOf, settings) : 0;
    const vacNote = vac > 0 ? ` · 휴가 ${vac}일은 빼고 셈` : '';
    const why =
      state === 'overdue'
        ? `마지막 방문 ${c.last_visit ?? '-'}${m ? ` · ${m}개월 미방문` : ''} · 평소 ${c.revisit_cycle_days ?? '-'}일 주기${std}${vacNote}`
        : `재방문 시기 · 마지막 방문 ${c.last_visit ?? '-'}${c.revisit_cycle_days ? ` · 주기 ${c.revisit_cycle_days}일` : ''}${std}${vacNote}`;
    let draft: string;
    if (state === 'overdue') {
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
    return { id: c.id, name, phone: phoneDigits(contacts[i].phone), state, why, draft };
  });

  // 이탈·재방문 판정은 월 단위라 주 1회 수집으로도 충분하지만, 어느 시점 기준인지는 밝힌다.
  const basis = syncLine(synced);

  return (
    <main className="wrap">
      <div className="bar">
        <div className="ttl">챙길 고객</div>
      </div>
      <div className="body">
        <div className="sec-h">자동 발송 X · 문자·전화는 버튼으로 바로{basis ? ` · ${basis}` : ''}</div>
        <AlertsList items={items} quiet={quiet} quietDays={CONTACT_QUIET_DAYS} />
      </div>
    </main>
  );
}
