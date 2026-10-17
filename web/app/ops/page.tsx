export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { cookies } from 'next/headers';
import { notFound } from 'next/navigation';
import { requireUser } from '@/lib/tenant';
import { canSeeOps } from '@/lib/ops-gate';
import {
  cspLine, dbLines, DB_LIMIT_MB, DB_WARN_MB, sinceLine, speedLine, usageLine,
  type CspRow, type DbRow, type SpeedRow, type UsageRow,
} from '@/lib/ops-view';
import { BackButton } from '@/components/back-button';

/**
 * 운영자 화면(개선 계획 v12 P2) — 매장별 사용 · 연락 · 화면 속도. 매일 감시(GitHub)와 같은 함수(0024 · 0025 ops_usage ·
 * ops_speed)의 숫자를 폰에서 바로 — 전에는 제가 감시 기록을 읽어 드려야 했다. 운영자 계정(0027 ops_add_reader — v15 P2)만
 * 열리고(0027 전엔 운영자 폰 쿠키 ?op=1), 디자이너 화면엔 입구가 없다. 매장 단위 숫자뿐 — 손님 정보는 없다.
 */
export default async function OpsPage() {
  const opCookie = (await cookies()).get('mb-op')?.value === '1';
  const { supabase } = await requireUser();
  if (!(await canSeeOps(supabase, opCookie))) notFound();
  const [usage, speed, csp, db] = await Promise.all([
    supabase.rpc('ops_usage'), supabase.rpc('ops_speed'), supabase.rpc('ops_csp'), supabase.rpc('ops_db_size'),
  ]);
  const urows = (usage.data as UsageRow[] | null) ?? [];
  const srows = (speed.data as SpeedRow[] | null) ?? [];
  const crows = (csp.data as CspRow[] | null) ?? [];
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
        <div className="sect-h">보안 정책 <span className="sect-n">보고만 · 지난 7일 어긋남</span></div>
        <div className="card">
          {csp.error ? (
            <div className="li ops-err">아직 못 읽어요 — 0026 SQL 을 실행하면 보여요</div>
          ) : crows.length ? (
            crows.map((r) => (
              <div className="li ops-r" key={`${r.directive}|${r.blocked}`}>
                <b>{r.directive ?? '?'}</b>
                <span>{cspLine(r)}</span>
              </div>
            ))
          ) : (
            <div className="li ops-err">어긋남 없음</div>
          )}
        </div>
        <div className="sect-h">DB 용량 <span className="sect-n">무료 {DB_LIMIT_MB}MB · {DB_WARN_MB}MB 넘으면 알림</span></div>
        <div className="card">
          {db.error ? (
            <div className="li ops-err">아직 못 읽어요 — 0028 SQL 을 실행하면 보여요</div>
          ) : (
            dbLines((db.data as DbRow[] | null) ?? []).map((l) => (
              <div className="li ops-r" key={l}>
                <span>{l}</span>
              </div>
            ))
          )}
        </div>
        <p className="ops-note">매일 감시와 같은 숫자예요. 매장 단위 숫자뿐 — 손님 정보는 없어요. 이 화면은 운영자만 열 수 있어요.</p>
      </div>
    </main>
  );
}
