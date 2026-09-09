import { notFound } from 'next/navigation';
import { requireUser, openDek, nameReader } from '@/lib/tenant';
import { mergeSettings, isVip } from '@/lib/settings';
import { kstNow } from '@/lib/kst';
import { isActiveBooking } from '@/lib/bookings';
import { txKind, ledger } from '@/lib/tx';

/**
 * 카르테가 화면에 뿌릴 것들을 한 번에 모은다.
 *
 * 조회·복호화·선불원장·가족·집계가 렌더 코드와 한 파일에 섞여 있어 350줄이었다.
 * 화면(page.tsx)은 이 결과만 받아 배치하고, 무엇을 어떻게 계산하는지는 여기서만 본다.
 */

type Cust = {
  id: string;
  tenant_id: string;
  pii_enc: string | null;
  visit_count: number;
  first_visit: string | null;
  last_visit: string | null;
  total_won: number;
  revisit_state: string | null;
  revisit_cycle_days: number | null;
  prefer_tags: string[] | null;
  memo: string | null;
  family_ext_id: string | null;
  churned_at: string | null;
  visits_90d: number | null;
  visits_180d: number | null;
  visits_365d: number | null;
  memo_ai: string | null;
  memo_ai_recent: string | null;
  prepaid_balance: number | null;
  gender: string | null;
  gender_manual: string | null;
  memo_ai_at: string | null;
};
type Tx = { id: string; date: string; time: string | null; service: string | null; amount_won: number; memo: string | null; kind: string | null; paid_out_of_pocket: boolean | null };
type Bk = { date: string; time: string | null; service: string | null; note: string | null; status: string | null };

function monthsAgo(d: string | null): number | null {
  if (!d) return null;
  return Math.max(1, Math.round((Date.now() - new Date(d).getTime()) / 2592000000));
}

export type Carte = Awaited<ReturnType<typeof loadCarte>>;

export async function loadCarte(id: string) {
  // 테넌트는 RLS 가 걸린 고객 행에서 따라오므로 소속 조회가 따로 필요 없다.
  const { supabase } = await requireUser();

  const { data: c } = await supabase
    .from('customers')
    .select(
      'id,tenant_id,pii_enc,visit_count,first_visit,last_visit,total_won,revisit_state,revisit_cycle_days,prefer_tags,memo,family_ext_id,churned_at,visits_90d,visits_180d,visits_365d,memo_ai,memo_ai_recent,memo_ai_at,prepaid_balance,gender,gender_manual',
    )
    .eq('id', id)
    .maybeSingle();
  if (!c) notFound();
  const cust = c as Cust;

  const today = kstNow().date; // KST 기준(엣지는 UTC라 새벽에 하루 밀림)
  const [{ data: tenant }, { data: tx }, { data: bk }] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped,settings').eq('id', cust.tenant_id).maybeSingle(),
    supabase
      .from('transactions')
      .select('id,date,time,service,amount_won,memo,kind,paid_out_of_pocket')
      .eq('customer_id', cust.id)
      .order('date', { ascending: false })
      .limit(500), // 잔액 계산이 과거 충전까지 봐야 해서 넉넉히
    supabase
      .from('bookings')
      .select('date,time,service,note,status')
      .eq('customer_id', cust.id)
      .gte('date', today)
      .order('date', { ascending: true })
      .order('time', { ascending: true, nullsFirst: false })
      .limit(5),
  ]);

  const settings = mergeSettings((tenant as { settings: unknown } | null)?.settings);
  const dw = (tenant as { dek_wrapped: string | null } | null)?.dek_wrapped ?? null;

  const dek = await openDek(dw);
  const nameFrom = nameReader(dek);
  const name = await nameFrom(cust.pii_enc);

  // 가족: 같은 tenant 내 동일 family_ext_id. 담당(디자이너)이 다른 가족원은 다른 tenant 라
  // 여기 안 보인다(멀티테넌트 격리 유지) — 각 디자이너는 '자기 고객인 가족원'만 본다.
  type FamRow = {
    id: string;
    pii_enc: string | null;
    visit_count: number;
    last_visit: string | null;
    total_won: number;
    visits_90d: number | null;
    visits_180d: number | null;
    visits_365d: number | null;
  };
  let familyList: { id: string; name: string; visit_count: number; last_visit: string | null; vip: boolean }[] = [];
  if (cust.family_ext_id) {
    const { data: fam } = await supabase
      .from('customers')
      .select('id,pii_enc,visit_count,last_visit,total_won,visits_90d,visits_180d,visits_365d')
      .eq('tenant_id', cust.tenant_id)
      .eq('family_ext_id', cust.family_ext_id)
      .neq('id', cust.id)
      .order('last_visit', { ascending: false })
      .limit(12);
    familyList = await Promise.all(
      ((fam as FamRow[]) ?? []).map(async (m) => ({
        id: m.id,
        name: await nameFrom(m.pii_enc),
        visit_count: m.visit_count,
        last_visit: m.last_visit,
        vip: isVip(m, settings),
      })),
    );
  }

  const all = (tx as Tx[]) ?? [];
  // 충전·상품권은 시술이 아니다. 같이 늘어놓으면 시술 이력이 읽히지 않고,
  // 매출·방문수도 이 구분 위에서 계산된다(worker/txkind.py).
  const history = all.filter((h) => txKind(h.kind, h.service) === 'service');
  const charges = all.filter((h) => txKind(h.kind, h.service) === 'charge');
  const others = all.filter((h) => {
    const k = txKind(h.kind, h.service);
    return k === 'product' || k === 'refund';
  });
  // 잔액을 DB 값에만 기대면 워커 재계산 전까지 0으로 보인다. 이 고객 거래는 이미 들고
  // 있으니 같은 규칙(lib/tx ledger)으로 여기서 바로 계산한다.
  const book = ledger(
    all.map((h) => ({
      date: h.date, time: h.time, id: h.id,
      amount: h.amount_won || 0,
      kind: txKind(h.kind, h.service),
      pocket: !!h.paid_out_of_pocket,
    })),
  );
  const chargedTotal = book.charged;
  const balance = book.balance;

  // 매장 메모를 따로 모아 보여주던 카드는 없앴다 — 아래 '시술 이력'이 같은 메모를 방문마다
  // 이미 달고 있어 화면에 두 번 나왔다. 메모는 어느 시술 때 적힌 것인지가 중요하므로
  // 이력 쪽에 붙은 것을 남기고, 전체를 훑는 용도는 상단 'AI 정리'가 대신한다.
  const nextBk = ((bk as Bk[]) ?? []).find((b) => isActiveBooking(b)) ?? null; // 지난 시간·취소·노쇼 제외
  const vip = isVip(cust, settings);
  const avg = cust.visit_count ? Math.round(cust.total_won / cust.visit_count) : 0;

  const svcCount = new Map<string, number>();
  for (const h of history) {
    const s = (h.service || '').trim();
    if (s) svcCount.set(s, (svcCount.get(s) || 0) + 1);
  }
  const topSvc = [...svcCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);

  const overdue = cust.revisit_state === 'overdue';
  const due = cust.revisit_state === 'due';
  const reason = overdue && cust.last_visit ? `${monthsAgo(cust.last_visit)}개월 미방문` : due ? '재방문 시기예요' : '';

  return {
    cust, name, settings, vip, avg,
    history, charges, others,
    chargedTotal, balance,
    familyList, nextBk, topSvc,
    overdue, due, reason,
  };
}
