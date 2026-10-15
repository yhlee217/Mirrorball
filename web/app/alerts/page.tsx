export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { contactReader, openDek, requireTenant } from '@/lib/tenant';
import {
  careState,
  fetchAllRows,
  isRealCustomer,
  isChurned,
  needsCare,
  onCareList,
  firstCare,
  onFirstList,
  servicesOn,
  HELLO_DAYS,
} from '@/lib/customers';
import { mergeSettings } from '@/lib/settings';
import { bookingSets, recentBookingRows } from '@/lib/bookings';
import { withSeenVisits } from '@/lib/visits';
import { CONTACT_QUIET_DAYS, phoneDigits, recentlyContactedIds } from '@/lib/contact';
import { friendlyService } from '@/lib/service-name';
import { careFor, soonestCare } from '@/lib/care-cycle';
import { draftFor, whenWord } from '@/lib/drafts';
import { contactEffect, kstDay, type ContactRow } from '@/lib/effect';
import { lastSynced } from '@/lib/sync';
import { SyncChip } from '@/components/sync-chip';
import { kstNow } from '@/lib/kst';
import { txKind } from '@/lib/tx';
import { addDays, agoWords, dayLabel, daysBetween, spanWords } from '@/lib/week';
import { awayDays } from '@/lib/offdays';
import { lastContactDays, newOnList } from '@/lib/fresh';
import AlertsList from './alerts-list';
import { ScreenReady } from '@/components/screen-timer';

type Cust = {
  id: string;
  ext_id: string | null;
  pii_enc: string | null;
  revisit_state: string | null;
  revisit_cycle_days: number | null;
  last_visit: string | null;
  visit_count: number;
  churned_at: string | null;
  prepaid_balance: number | null;
};
type Tx = { customer_id: string | null; date: string | null; service: string | null; kind: string | null };

const COLS = 'id,ext_id,pii_enc,revisit_state,revisit_cycle_days,last_visit,visit_count,churned_at,prepaid_balance';
const EFFECT_DAYS = 28; // 연락 효과를 보는 기간 — 지난 4주
// 줄 순서 — 안부는 첫 방문 2주 안에만 뜨는 짧은 할 일이라 맨 위, 다시 오실 때는 맨 아래.
const ORDER: Record<string, number> = { hello: 0, overdue: 1, due: 2, back: 3 };

export default async function AlertsPage() {
  const { supabase, tenantId } = await requireTenant();
  const today = kstNow().date;

  const [{ data: tenant }, customers, firsts, bkRows, contacted, synced, recentContacts] = await Promise.all([
    supabase.from('tenants').select('designer_name,dek_wrapped,settings').eq('id', tenantId).maybeSingle(),
    fetchAllRows<Cust>((from, to) =>
      supabase.from('customers').select(COLS).eq('tenant_id', tenantId).in('revisit_state', ['overdue', 'due']).order('id').range(from, to)),
    // 첫 방문 손님(방문 1회) — 워커는 '신규'로만 두므로 따로 받는다. 1년 안이면 넉넉하다(lib/customers firstCare)
    fetchAllRows<Cust>((from, to) =>
      supabase.from('customers').select(COLS).eq('tenant_id', tenantId).eq('visit_count', 1).gte('last_visit', addDays(today, -365))
        .order('id').range(from, to)),
    recentBookingRows(supabase, tenantId), // 이미 예약한 분 · 수집 뒤 다녀가셨을 분께 '오랜만이에요'를 보내지 않게
    recentlyContactedIds(supabase, tenantId), // 최근 연락한 분은 할 일에서 잠시 뺀다
    lastSynced(supabase, tenantId), // 재방문 판정의 기준일(워커가 판정한 날) — 휴가를 빼고 셀 때 쓴다
    // 연락 효과(맨 위 한 줄) — 지난 4주 연락 기록
    fetchAllRows<ContactRow>((from, to) =>
      supabase.from('care_items').select('customer_id,sent_at').eq('tenant_id', tenantId).eq('kind', 'contact')
        .gte('sent_at', new Date(Date.now() - EFFECT_DAYS * 86400000).toISOString()).order('id').range(from, to)),
  ]);

  const tRow = tenant as { designer_name: string | null; dek_wrapped: string | null; settings: unknown } | null;
  const settings = mergeSettings(tRow?.settings);
  const designer = tRow?.designer_name?.trim() || null;
  const dek = await openDek(tRow?.dek_wrapped);
  const readContact = contactReader(dek);

  // 재방문 상태는 휴가를 반영한 것(careState) — 휴가 동안은 손님이 오고 싶어도 못 왔다.
  // DB 에서 due·overdue 만 받아도 되는 건, 휴가 반영은 판정을 늦추기만 하고 앞당기지 않아서다.
  const asOf = synced?.date ?? today;
  const stateOf = (c: Cust) => careState(c, settings, asOf);
  // 예약했거나 수집 뒤 예약 시각이 지난 분(다녀가셨을 분) — 다음 수집이 방문을 잡을 때까지 뺀다(lib/bookings)
  const held = bookingSets(bkRows, asOf).hold;
  const flags = (c: Cust) => ({ settings, churned: isChurned(c), booked: held.has(c.id), contacted: contacted.has(c.id), asOf });
  const real = ((customers as Cust[]) ?? []).filter((c) => isRealCustomer(c.ext_id));
  const realFirst = ((firsts as Cust[]) ?? []).filter((c) => isRealCustomer(c.ext_id));

  // 손님별 거래 — 마지막 시술(문구)과 첫 방문 날 받은 시술(주기·문구)에 쓴다. 50명씩 나눠 받는다:
  // 한 번에 묶으면 주소가 길어지고, 단골 몇 분의 긴 이력이 상한(3000행)을 채워 다른 분 시술이 빠질 수 있다.
  const txsOf = async (cs: Cust[]): Promise<Tx[]> => {
    const chunks: Cust[][] = [];
    for (let i = 0; i < cs.length; i += 50) chunks.push(cs.slice(i, i + 50));
    const parts = await Promise.all(
      chunks.map((part) => {
        const since = part.map((c) => (c.last_visit ?? '').slice(0, 10)).filter(Boolean).sort()[0] ?? '1970-01-01';
        return supabase
          .from('transactions')
          .select('customer_id,date,service,kind')
          .eq('tenant_id', tenantId)
          .in('customer_id', part.map((c) => c.id))
          .gte('date', since)
          .order('date', { ascending: false })
          .limit(3000);
      }),
    );
    return parts.flatMap(({ data }) => (data as Tx[] | null) ?? []);
  };

  const todo = real.filter((c) => onCareList(c, flags(c)));
  const firstById = new Map(realFirst.map((c) => [c.id, c]));
  const firstSvcs = servicesOn(await txsOf(realFirst), (id) => firstById.get(id)?.last_visit);
  const svcsOf = (c: Cust) => firstSvcs.get(c.id) ?? [];
  const firstKind = new Map(realFirst.map((c) => [c.id, onFirstList(c, svcsOf(c), flags(c))]));
  const firstTodo = realFirst.filter((c) => firstKind.get(c.id));
  // 연락해서 잠시 빠진 분 — 목록이 왜 줄었는지 밝힌다
  const quiet =
    real.filter((c) => needsCare(c, flags(c)) && contacted.has(c.id)).length +
    realFirst.filter((c) => contacted.has(c.id) && !isChurned(c) && !held.has(c.id) && firstCare(c, svcsOf(c), settings, asOf))
      .length;

  // 이번 주 새로 오른 분(lib/fresh) — 지난주 수집 땐 목록에 없던 분. 84명 앞에서 '어디서부터'를 맨 위에 모은다(v10 P1).
  // 연락 뒤 숨김이 끝나 다시 오른 분도 — 마지막 연락일은 연락 효과용 4주 기록에서.
  const lastContact = lastContactDays(recentContacts);
  const freshOf = (c: Cust, state: string) =>
    newOnList(state, c, { settings, asOf, today, services: svcsOf(c), lastContact: lastContact.get(c.id) });

  // 전원을 그린다 — 화면은 50명씩 펼친다(alerts-list). 머리말 숫자와 목록이 같은 사람을 가리키게.
  const rows: { c: Cust; state: string; fresh: boolean }[] = [
    ...todo.map((c) => ({ c, state: stateOf(c) as string })),
    ...firstTodo.map((c) => ({ c, state: firstKind.get(c.id) as string })),
  ].map((r) => ({ ...r, fresh: freshOf(r.c, r.state) })).sort((a, b) =>
    Number(b.fresh) - Number(a.fresh) || // 새로 오른 분 먼저 — 그 안에서는 아래 순서 그대로
    ORDER[a.state] - ORDER[b.state] ||
    // 같은 상태 안에서는 선불 잔액이 남은 분 먼저 — 이미 받은 돈이라 다시 오시게 하기 가장 쉽다(v5 P3)
    Number((b.c.prepaid_balance ?? 0) > 0) - Number((a.c.prepaid_balance ?? 0) > 0) ||
    (a.state === 'hello' || a.state === 'back'
      ? (a.c.last_visit ?? '').localeCompare(b.c.last_visit ?? '') // 첫 방문은 오래된 분부터 — 곧 목록에서 내려간다
      : b.c.visit_count - a.c.visit_count));

  const [contacts, lastTx] = await Promise.all([Promise.all(rows.map((r) => readContact(r.c.pii_enc))), txsOf(todo)]);
  // 2회 이상 손님의 마지막 시술 — 최신 거래부터 오므로 손님마다 처음 만난 시술. 충전·제품은 건너뛴다.
  const lastSvc = new Map<string, string>();
  for (const t of lastTx) {
    if (t.customer_id && t.service && !lastSvc.has(t.customer_id) && txKind(t.kind, t.service) === 'service') {
      lastSvc.set(t.customer_id, t.service);
    }
  }

  // 연락 효과 — 지난 4주 연락한 분이 그 뒤 오셨나(lib/effect). 그분들의 연락 뒤 방문만 받는다.
  const effSince = addDays(today, -(EFFECT_DAYS - 1));
  const effIds = [...new Set(recentContacts.map((r) => r.customer_id).filter(Boolean) as string[])];
  const effDay = recentContacts.map((r) => (r.sent_at ? kstDay(r.sent_at) : '')).filter(Boolean).sort()[0] ?? effSince;
  const effChunks: string[][] = [];
  for (let i = 0; i < effIds.length; i += 50) effChunks.push(effIds.slice(i, i + 50));
  const effTx = (
    await Promise.all(effChunks.map((ids) =>
      supabase.from('transactions').select('customer_id,date,service,kind').eq('tenant_id', tenantId).in('customer_id', ids).gte('date', effDay).limit(3000)))
  ).flatMap(({ data }) => (data as Tx[] | null) ?? []);
  const effVisits = new Map<string, string[]>();
  for (const t of effTx) {
    if (!t.customer_id || !t.date || txKind(t.kind, t.service) !== 'service') continue;
    effVisits.set(t.customer_id, [...(effVisits.get(t.customer_id) ?? []), t.date]);
  }
  // '예약'도 같은 판정 — 연락 뒤 예약하고 다녀가신 분이 수집 전까지 '효과 없음'으로 빠지지 않게
  // '오심'도 지금 기준 — 연락 뒤 예약 시간이 지나 다녀가신 분(예약 기준)도 센다(v9 P2, lib/visits withSeenVisits)
  const effect = effIds.length ? contactEffect(recentContacts, withSeenVisits(effVisits, bkRows, synced), held, effSince) : null;

  const items = rows.map(({ c, state, fresh }, i) => {
    const name = contacts[i].name;
    const last = c.last_visit ? c.last_visit.slice(0, 10) : null;
    const days = last ? daysBetween(last, today) : null;
    const vac = last ? daysBetween(last, asOf) - awayDays(last, asOf, settings) : 0;
    let why: string;
    let note: string;
    let draft: string;
    if (state === 'hello' || state === 'back') {
      // 첫 방문 손님 — 그날 받은 시술 중 주기가 가장 짧은 것이 문구·주기를 정한다(카르테 다음 방문과 같다)
      const pick = soonestCare(svcsOf(c));
      const raw = pick?.service ?? svcsOf(c)[0] ?? null;
      const svc = friendlyService(raw) || null;
      const care = pick?.care ?? null;
      if (state === 'hello') {
        why = ['안부', days !== null ? agoWords(days) : null, care?.cat ?? svc].filter(Boolean).join(' · ');
        note = [last ? `첫 방문 ${dayLabel(last)}` : null, `첫 방문 ${HELLO_DAYS}일 안에만 떠요`].filter(Boolean).join(' · ');
        draft = draftFor({ kind: 'hello', name, designer, svc, care, days, when: last ? whenWord(last, today) : undefined });
      } else {
        why = ['다시 오실 때', days !== null ? `${spanWords(days)}째` : null, care?.cat ?? svc].filter(Boolean).join(' · ');
        note = [
          last ? `첫 방문 ${dayLabel(last)}` : null,
          care ? `${care.cat} 보통 ${spanWords(care.days)}` : null,
          `${spanWords((care?.days ?? 42) * 2)} 지나면 목록에서 내려가요`,
          vac > 0 ? `휴가 ${vac}일은 빼고 셈` : null,
        ].filter(Boolean).join(' · ');
        draft = draftFor({ kind: 'back', name, designer, svc, care, days });
      }
    } else {
      const rawSvc = lastSvc.get(c.id);
      const svc = friendlyService(rawSvc); // 고객 문구용(직급·성별 표기 제거)
      const care = careFor(rawSvc); // 시술별 표준 관리주기·표현(분류는 원본 메뉴명으로)
      // 사유는 한 줄 조각 — '2개월째 · 평소 5주 · 뿌리염색'(UX 계획 v3). 날짜·표준 주기는 펼친 곳에.
      why = [
        last ? `${spanWords(daysBetween(last, asOf))}째` : null,
        c.revisit_cycle_days ? `평소 ${spanWords(c.revisit_cycle_days)}` : null,
        care?.cat ?? (svc || null),
      ].filter(Boolean).join(' · ');
      // 펼친 곳의 한 줄 — 마지막 방문일, 휴가를 빼고 셌으면 그 일수(달력보다 판정이 늦은 까닭)
      note = [last ? `마지막 방문 ${dayLabel(last)}` : null, vac > 0 ? `휴가 ${vac}일은 빼고 셈` : null].filter(Boolean).join(' · ');
      draft = draftFor({
        kind: state === 'overdue' ? 'overdue' : 'due', name, designer, svc: svc || null, care, days,
        loyal: c.visit_count >= settings.vip_visits, cycleDays: c.revisit_cycle_days,
      });
    }
    // 선불 잔액은 디자이너만 본다 — 추정이라 손님 문자(draft)엔 넣지 않는다
    return { id: c.id, name, phone: phoneDigits(contacts[i].phone), state, why, note, draft, prepaid: Math.max(0, c.prepaid_balance ?? 0), fresh };
  });

  return (
    <main className="wrap">
      <div className="bar">
        <div className="ttl">챙길 고객 <span className="sect-n">{items.length.toLocaleString()}명</span></div>
        <SyncChip synced={synced} />
      </div>
      <div className="body">
        <AlertsList items={items} quiet={quiet} quietDays={CONTACT_QUIET_DAYS} effect={effect} button={settings.contact_button} />
      </div>
      <ScreenReady />
    </main>
  );
}
