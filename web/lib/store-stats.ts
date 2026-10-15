import type { ServerClient } from './supabase/server';
import { fetchAllRows } from './customers';
import { pairStats, visitsByCustomer, type PairStats } from './recommend';
import { addDays } from './week';

type Sb = ServerClient;
type StoreTx = { customer_id: string | null; date: string | null; service: string | null; kind: string | null };

/**
 * '추천 시술'의 매장 근거(이 매장 손님들이 함께 받는 시술, lib/recommend pairStats) — 하루에 한 번 계산해
 * store_stats(0024)에 두고 홈 · 상세보기가 읽는다(개선 계획 v12 P0). 전에는 두 화면이 열릴 때마다 매장 1년 거래
 * (1,300~2,100건, v2 측정)를 받아 다시 셌다 — 앱을 처음 열 때 느린 때 1.9초(2026-10-15 감시)의 큰 몫.
 * 기준일은 지금처럼 오늘(KST)이라 숫자는 그대로다(날이 바뀌면 처음 연 화면이 다시 센다). 저장이 안 돼도(0024 전 ·
 * 권한) 계산한 값으로 화면은 뜬다 — 다음에 또 셀 뿐.
 */
export async function storePairs(supabase: Sb, tenantId: string, today: string): Promise<PairStats> {
  const { data } = await supabase
    .from('store_stats')
    .select('as_of,data')
    .eq('tenant_id', tenantId)
    .eq('kind', 'pairs')
    .maybeSingle();
  const row = data as { as_of: string; data: unknown } | null;
  if (row && row.as_of === today && row.data && typeof row.data === 'object') return row.data as PairStats;

  const tx = await fetchAllRows<StoreTx>((from, to) =>
    supabase.from('transactions').select('customer_id,date,service,kind')
      .eq('tenant_id', tenantId).gte('date', addDays(today, -365)).order('id').range(from, to));
  const pairs = pairStats(visitsByCustomer(tx), today);
  try {
    await supabase
      .from('store_stats')
      .upsert({ tenant_id: tenantId, kind: 'pairs', as_of: today, data: pairs, updated_at: new Date().toISOString() },
        { onConflict: 'tenant_id,kind' });
  } catch {
    /* 저장 실패는 화면과 무관하다 */
  }
  return pairs;
}
