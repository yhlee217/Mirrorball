export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { cookies } from 'next/headers';
import { notFound } from 'next/navigation';
import { requireUser } from '@/lib/tenant';
import { sinceLine, speedLine, usageLine, type SpeedRow, type UsageRow } from '@/lib/ops-view';
import { BackButton } from '@/components/back-button';

/**
 * 운영자 화면(개선 계획 v12 P2) — 매장별 사용 · 연락 · 화면 속도. 매일 감시(GitHub)와 같은 함수(0024 · 0025 ops_usage ·
 * ops_speed)의 숫자를 폰에서 바로 — 전에는 제가 감시 기록을 읽어 드려야 했다. 운영자 폰(설정 ?op=1 → 쿠키)에서만 열리고,
 * 디자이너 화면엔 입구가 없다. 매장 단위 숫자뿐 — 손님 정보는 없다.
 */
export default async function OpsPage() {
  if (cookies().get('mb-op')?.value !== '1') notFound();
  const { supabase } = await requireUser();
  const [usage, speed] = await Promise.all([supabase.rpc('ops_usage'), supabase.rpc('ops_speed')]);
  const urows = (usage.data as UsageRow[] | null) ?? [];
  const srows = (speed.data as SpeedRow[] | null) ?? [];
  const now = Date.now();
  const since = sinceLine(urows);
  return (
    <main className="wrap">
      <div className="bar">
        <BackButton />
        <div className="ttl" style={{ marginLeft: 6 }}>운영 숫자 <span className="sect-n">지난 7일</span></div>
      </div>
      <div className="body">
        {since ? <p className="ops-since">{since}</p> : null}
        <div className="sect-h">매장별 사용</div>
        <div className="card">
          {usage.error ? (
            <div className="li ops-err">못 읽었어요 — 0024 · 0025 SQL 을 실행했는지 확인해 주세요</div>
          ) : urows.length ? (
            urows.map((r) => (
              <div className="li ops-r" key={r.slug ?? '?'}>
                <b>{r.slug ?? '?'}</b>
                <span>{usageLine(r, now)}</span>
              </div>
            ))
          ) : (
            <div className="li ops-err">아직 기록 없음</div>
          )}
        </div>
        <div className="sect-h">화면 속도 <span className="sect-n">누른 순간 → 내용이 뜬 순간</span></div>
        <div className="card">
          {speed.error ? (
            <div className="li ops-err">못 읽었어요 — 0024 SQL 을 실행했는지 확인해 주세요</div>
          ) : srows.length ? (
            srows.map((r) => (
              <div className="li ops-r" key={r.screen ?? '?'}>
                <b>{r.screen ?? '?'}</b>
                <span>{speedLine(r)}</span>
              </div>
            ))
          ) : (
            <div className="li ops-err">아직 기록 없음</div>
          )}
        </div>
        <p className="ops-note">매일 감시와 같은 숫자예요. 매장 단위 숫자뿐 — 손님 정보는 없어요. 이 화면은 운영자 폰에서만 열려요.</p>
      </div>
    </main>
  );
}
