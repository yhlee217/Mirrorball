export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { contactReader, openDek, requireTenant } from '@/lib/tenant';
import { phoneDigits, smsHref } from '@/lib/contact';
import { draftFor, whenWord } from '@/lib/drafts';
import { daysBetween } from '@/lib/week';
import { fetchAllRows, isRealCustomer } from '@/lib/customers';
import { mergeSettings } from '@/lib/settings';
import { friendlyService } from '@/lib/service-name';
import { careFor } from '@/lib/care-cycle';
import { kstNow } from '@/lib/kst';
import { lastSynced } from '@/lib/sync';
import { SyncChip } from '@/components/sync-chip';
import { txKind } from '@/lib/tx';
import { noShowsSinceSync, visitOrdinals, visitsSinceSync } from '@/lib/visits';
import VisitsList, { type Item } from './visits-list';
import { ScreenReady } from '@/components/screen-timer';

// 방문 관리 — '다녀가신 분'을 챙기는 화면('챙길 고객' 탭이 '아직 안 오신 분'을 맡는 것과 짝).
// 리뷰 요청은 종용하는 느낌이라 이 화면에서 빼고 노출(콘텐츠 코치) 탭에만 둔다.

type Tx = { customer_id: string | null; date: string; time: string | null; service: string | null; amount_won: number; memo: string | null; kind: string | null };
type Cust = { id: string; ext_id: string | null; pii_enc: string | null; visit_count: number };
type Bk = { id: string; customer_id: string | null; date: string | null; time: string | null; service: string | null; status: string | null; pii_enc: string | null };

const DAY = 86400000;
const KST = 9 * 3600000;

export default async function VisitsPage() {
  const { supabase, tenantId } = await requireTenant();

  const today = kstNow().date;
  const since = new Date(Date.now() + KST - 13 * DAY).toISOString().slice(0, 10); // 최근 14일

  const [{ data: tenant }, txs, synced, { data: bookings }] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped,designer_name,settings').eq('id', tenantId).maybeSingle(),
    fetchAllRows<Tx>((from, to) =>
      supabase
        .from('transactions')
        .select('customer_id,date,time,service,amount_won,memo,kind')
        .eq('tenant_id', tenantId)
        .gte('date', since)
        .order('id')
        .range(from, to)),
    lastSynced(supabase, tenantId),
    // 마지막 수집 뒤 다녀가셨을 분 — 방문 기록은 다음 수집에 들어오니 그 사이는 지난 예약으로 보여 준다(lib/visits)
    supabase.from('bookings').select('id,customer_id,date,time,service,status,pii_enc')
      .eq('tenant_id', tenantId).gte('date', since).lte('date', today).limit(500),
  ]);

  // 같은 날 여러 시술은 한 번의 방문으로 묶는다.
  const byVisit = new Map<
    string,
    { customer_id: string; date: string; time: string | null; services: string[]; amount: number; memo: string | null }
  >();
  for (const t of txs) {
    if (!t.customer_id || !t.date) continue;
    if (txKind(t.kind, t.service) !== 'service') continue; // 충전·제품만 있는 날은 방문이 아니다
    const k = `${t.customer_id}|${t.date}`;
    const e = byVisit.get(k) ?? { customer_id: t.customer_id, date: t.date, time: null, services: [], amount: 0, memo: null };
    if (t.service) e.services.push(t.service);
    e.amount += t.amount_won || 0;
    if (t.time && (!e.time || t.time < e.time)) e.time = t.time; // 같은 날 여러 건이면 가장 이른 시각 = 방문 시각
    if (t.memo && !e.memo) e.memo = t.memo; // 그날 매장에 적어둔 메모
    byVisit.set(k, e);
  }
  const collected = [...byVisit.values()];
  // 수집 뒤 지난 예약 — 이미 수집된 같은 날 방문과 겹치면 뺀다
  const bks = (bookings as Bk[] | null) ?? [];
  const pending = synced
    ? visitsSinceSync(bks, synced).filter((b) => !(b.customer_id && byVisit.has(`${b.customer_id}|${b.date}`)))
    : [];
  // 디자이너가 노쇼로 표시한 예약 — 세지 않고 줄을 그어 남긴다(되돌리기 자리, components/noshow-button)
  const marked = synced ? noShowsSinceSync(bks, synced) : [];

  const ids = [...new Set([...collected.map((v) => v.customer_id),
    ...[...pending, ...marked].map((b) => b.customer_id).filter(Boolean) as string[]])];
  const custs: Cust[] = ids.length
    ? (((await supabase.from('customers').select('id,ext_id,pii_enc,visit_count').eq('tenant_id', tenantId).in('id', ids)).data as Cust[]) ?? [])
    : [];
  const cmap = new Map(custs.map((c) => [c.id, c]));
  const nth = visitOrdinals(collected, (id) => cmap.get(id)?.visit_count ?? 1);

  const tRow = tenant as { dek_wrapped: string | null; designer_name: string | null; settings: unknown } | null;
  const dek = await openDek(tRow?.dek_wrapped ?? null);
  const readContact = contactReader(dek);
  const designer = tRow?.designer_name?.trim() || null;
  const button = mergeSettings(tRow?.settings).contact_button; // 문자 · 카톡 등(설정, v11 P1)
  // 방문 뒤 안내(v9 P1) — 그날 시술의 홈케어 안내 문구. 팁이 있는 시술만. 예약 권유는 없다(lib/drafts 'after').
  // 챙길 고객 연락이 아니라 연락 기록 · 효과엔 남기지 않는다. 문자 앱 링크는 번호가 있을 때만 — 없으면 카톡 등으로.
  const afterOf = (name: string, phone: string | null, raw: string | null, date: string) => {
    const care = careFor(raw);
    if (!care?.tip) return { after: null, sms: null };
    const after = draftFor({
      kind: 'after', name, designer, svc: friendlyService(raw) || null, care,
      days: daysBetween(date, today), when: whenWord(date, today),
    });
    const digits = phoneDigits(phone);
    return { after, sms: digits ? smsHref(digits, after) : null };
  };

  const visitItems = collected
    .filter((v) => isRealCustomer(cmap.get(v.customer_id)?.ext_id ?? null))
    .map(async (v): Promise<Item> => {
      const c = cmap.get(v.customer_id)!;
      const rawMain = v.services[0] ?? null;
      const { name, phone } = await readContact(c.pii_enc);
      return {
        id: v.customer_id,
        name,
        date: v.date,
        time: v.time,
        service: [...new Set(v.services.map((s) => friendlyService(s)).filter(Boolean))].join('+'), // 홈 브리핑과 같은 표기
        amount: v.amount,
        nth: nth.get(`${v.customer_id}|${v.date}`) ?? c.visit_count, // 그 방문이 몇 번째였나(지금 총 횟수가 아니라)
        pending: false,
        noshow: false,
        bookingId: null,
        memo: v.memo ?? '', // 그날 매장에서 적어둔 메모
        tip: careFor(rawMain)?.tip ?? '', // 그날 받은 시술의 홈케어 안내
        ...afterOf(name, phone, rawMain, v.date),
      };
    });
  // 수집 전 — 예약에 적힌 시각 · 시술. 처음 오신 분(손님 기록이 아직 없음)은 예약의 이름으로, 상세보기 없이.
  // 지금 기준으로 이미 다녀가신 분이라 방문 횟수에도 센다 — 수집된 횟수 다음부터 차례로(같은 분이 두 번이면 +1, +2).
  const pendDays = new Map<string, string[]>();
  for (const b of pending) {
    if (b.customer_id && b.date) pendDays.set(b.customer_id, [...new Set([...(pendDays.get(b.customer_id) ?? []), b.date])].sort());
  }
  const pendingItems = pending
    .filter((b) => !b.customer_id || isRealCustomer(cmap.get(b.customer_id)?.ext_id ?? null))
    .map(async (b): Promise<Item> => {
      const c = b.customer_id ? cmap.get(b.customer_id) : undefined;
      const { name, phone } = await readContact(c?.pii_enc ?? b.pii_enc);
      return {
        id: c?.id ?? '',
        name,
        date: b.date as string,
        time: b.time,
        service: friendlyService(b.service) || '',
        amount: 0,
        nth: c ? c.visit_count + (pendDays.get(c.id) ?? []).indexOf(b.date as string) + 1 : 1,
        pending: true,
        noshow: false,
        bookingId: b.id,
        memo: '',
        tip: careFor(b.service)?.tip ?? '',
        ...afterOf(name, phone, b.service, b.date as string),
      };
    });
  const markedItems = marked
    .filter((b) => !b.customer_id || isRealCustomer(cmap.get(b.customer_id)?.ext_id ?? null))
    .map(async (b): Promise<Item> => {
      const c = b.customer_id ? cmap.get(b.customer_id) : undefined;
      return {
        id: c?.id ?? '',
        name: (await readContact(c?.pii_enc ?? b.pii_enc)).name,
        date: b.date as string,
        time: b.time,
        service: friendlyService(b.service) || '',
        amount: 0,
        nth: 0,
        pending: true,
        noshow: true,
        bookingId: b.id,
        memo: '',
        tip: '',
        after: null,
        sms: null,
      };
    });
  const items = (await Promise.all([...pendingItems, ...markedItems, ...visitItems]))
    .sort((a, b) => (a.date !== b.date ? (a.date < b.date ? 1 : -1) : (a.time ?? '') < (b.time ?? '') ? 1 : -1))
    .slice(0, 60);

  const yesterday = new Date(Date.now() + KST - DAY).toISOString().slice(0, 10);

  return (
    <main className="wrap">
      <div className="body">
        {/* 머리말은 한 줄 — 수집 기준은 작은 표식 하나로(UX 계획 v3). 그 뒤 방문은 예약으로 보여 주고 다음 수집에 확정된다. */}
        <div className="top">
          <b>방문</b>
          <span className="sect-n">2주</span>
          <SyncChip synced={synced} />
        </div>
        <VisitsList items={items} today={today} yesterday={yesterday} syncLabel={synced ? `${synced.label} ${synced.time}` : null} button={button} />
      </div>
      <ScreenReady />
    </main>
  );
}
