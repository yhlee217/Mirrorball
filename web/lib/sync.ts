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

/**
 * 예정된 수집을 한 번 걸렀는가 — 조용히 멈춘 걸 몇 주씩 모르는 게 주 1회의 진짜 위험.
 *
 * 수집은 일요일 14:00 에 한 번이다. 정상이라면 '며칠 전'은 일요일 0 에서 토요일 6 까지만
 * 오간다. 일요일 새벽(그날 수집 전)에 7 이 잠깐 나올 수 있으니, **8 이상이면 예정된
 * 일요일이 통째로 비었다는 뜻**이다 — 예외 없이.
 *
 * 전에는 10 이었다. 그래서 실제로 한 주를 거른 상태(8~9일)가 아무 경고 없이 지나갔다.
 */
export function isSyncStale(s: { daysAgo: number } | null): boolean {
  return !!s && s.daysAgo >= 8;
}

/** '8월 30일 수집 기준 · 3일 전' — 화면 상단에 한 줄로 붙이는 표기. */
export function syncLine(s: { label: string; daysAgo: number } | null): string | null {
  if (!s) return null;
  const when = s.daysAgo === 0 ? '오늘 갱신' : `${s.daysAgo}일 전`;
  return `${s.label} 수집 기준 · ${when}${isSyncStale(s) ? ' · 수집이 밀렸어요' : ''}`;
}
