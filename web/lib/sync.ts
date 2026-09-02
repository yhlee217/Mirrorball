import type { supabaseServer } from './supabase/server';
import { kstStamp } from './kst';

/**
 * 마지막 성공 수집 시각(KST 표기) — 화면이 '언제 기준'인지 밝히는 데 쓴다.
 *
 * 수집이 30분마다에서 주 1회로 바뀐 뒤로, 화면에 보이는 것은 항상 며칠 전 상태다.
 * 그걸 밝히지 않으면 '예약이 없다'·'아무도 안 왔다'를 지금의 사실로 오해한다.
 * 기록(sync_jobs)이 아직 없으면 null — 호출부에서 표시를 생략한다.
 */
export async function lastSynced(
  supabase: ReturnType<typeof supabaseServer>,
): Promise<{ label: string; daysAgo: number } | null> {
  const { data } = await supabase
    .from('sync_jobs')
    .select('finished_at')
    .eq('status', 'ok')
    .order('finished_at', { ascending: false })
    .limit(1)
    .maybeSingle();
  return kstStamp((data as { finished_at: string | null } | null)?.finished_at);
}

/** 수집 주기(7일)를 한 번 놓친 수준 — 조용히 멈춘 걸 몇 주씩 모르는 게 주 1회의 진짜 위험. */
export function isSyncStale(s: { daysAgo: number } | null): boolean {
  return !!s && s.daysAgo >= 10;
}

/** '8월 30일 수집 기준 · 3일 전' — 화면 상단에 한 줄로 붙이는 표기. */
export function syncLine(s: { label: string; daysAgo: number } | null): string | null {
  if (!s) return null;
  const when = s.daysAgo === 0 ? '오늘 갱신' : `${s.daysAgo}일 전`;
  return `${s.label} 수집 기준 · ${when}${isSyncStale(s) ? ' · 수집이 밀렸어요' : ''}`;
}
