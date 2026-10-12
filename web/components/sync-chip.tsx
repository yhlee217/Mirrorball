import { isSyncStale } from '@/lib/sync';
import { shortDate } from '@/lib/week';

/**
 * 기준 표시 — 화면 위 작은 '10.11 기준'. 주 1회 수집이라 화면이 언제 기준인지는 정보의 일부지만,
 * 화면마다 문장으로 되풀이하면 피로하다(UX 계획 v3). 평소엔 조용히, 8일 넘게 밀리면 눈에 띄게.
 */
export function SyncChip({ synced }: { synced: { date: string; daysAgo: number } | null }) {
  if (!synced) return null;
  const stale = isSyncStale(synced);
  return (
    <span className={'sync' + (stale ? ' stale' : '')} title={`마지막 수집 ${synced.daysAgo}일 전`}>
      {shortDate(synced.date)} 기준{stale ? ' · 수집 밀림' : ''}
    </span>
  );
}
