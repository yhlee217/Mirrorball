export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { cookies } from 'next/headers';
import { openDek, requireTenant } from '@/lib/tenant';
import { mergeSettings } from '@/lib/settings';
import { fetchAllRows, isRealCustomer } from '@/lib/customers';
import { decryptPII } from '@/lib/crypto';
import { dayLabel } from '@/lib/week';
import SettingsForm from './settings-form';
import ChurnedList from './churned-list';
import LogoutButton from '../logout-button';
import { Help } from '@/components/help';
import { BackButton } from '@/components/back-button';
import { ScreenReady } from '@/components/screen-timer';
import OpMark from '@/components/op-mark';

export default async function SettingsPage() {
  const { supabase, user, tenantId } = await requireTenant();

  // 판정 기준을 바꿀 때 '지금 몇 명이 되는지' 바로 보여주려면 판정에 쓰는 값만 클라이언트로 보내야 한다.
  // 키 없는 배열로 압축해서 보낸다(객체면 행마다 키가 반복돼 payload 가 두 배).
  type StatRow = {
    ext_id: string | null;
    total_won: number;
    visit_count: number;
    visits_90d: number | null;
    visits_180d: number | null;
    visits_365d: number | null;
    last_visit: string | null;
    churned_at: string | null;
  };

  const [{ data: tenant }, { count }, { data: latest }, { data: churned }, statRows] = await Promise.all([
    supabase.from('tenants').select('salon_name,designer_name,slug,settings,dek_wrapped').eq('id', tenantId).maybeSingle(),
    supabase.from('customers').select('id', { count: 'exact', head: true }).eq('tenant_id', tenantId),
    supabase.from('transactions').select('date').eq('tenant_id', tenantId).order('date', { ascending: false }).limit(1),
    supabase
      .from('customers')
      .select('id,pii_enc,visit_count,last_visit,churned_at')
      .eq('tenant_id', tenantId)
      .not('churned_at', 'is', null)
      .order('churned_at', { ascending: false })
      .limit(200),
    fetchAllRows<StatRow>((from, to) =>
      supabase
        .from('customers')
        .select('ext_id,total_won,visit_count,visits_90d,visits_180d,visits_365d,last_visit,churned_at')
        .eq('tenant_id', tenantId)
        .order('id')
        .range(from, to)),
  ]);

  // 홈 신호와 같은 모집단 — 미식별 워크인·이탈 표시 고객 제외.
  const stats: [number, number, number, number, number, string | null][] = statRows
    .filter((c) => isRealCustomer(c.ext_id) && !c.churned_at)
    .map((c) => [
      c.total_won || 0,
      c.visit_count || 0,
      c.visits_90d ?? 0,
      c.visits_180d ?? 0,
      c.visits_365d ?? 0,
      c.last_visit,
    ]);
  const t = tenant as {
    salon_name: string;
    designer_name: string | null;
    slug: string;
    settings: unknown;
    dek_wrapped: string | null;
  } | null;
  const settings = mergeSettings(t?.settings);
  const lastDate = (latest as { date: string }[] | null)?.[0]?.date ?? null;

  // 이탈 표시 고객 — 이름은 테넌트 키로 복호화(다른 화면과 동일).
  type ChurnRow = { id: string; pii_enc: string | null; visit_count: number; last_visit: string | null; churned_at: string };
  const dek = await openDek(t?.dek_wrapped);
  const churnedRows = await Promise.all(
    ((churned as ChurnRow[]) ?? []).map(async (c) => {
      let name = '고객';
      if (dek && c.pii_enc) {
        try {
          const p = await decryptPII(c.pii_enc, dek);
          if (typeof p.name === 'string' && p.name) name = p.name;
        } catch {
          /* noop */
        }
      }
      return { id: c.id, name, visit_count: c.visit_count, last_visit: c.last_visit, churned_at: c.churned_at };
    }),
  );

  return (
    <main className="wrap">
      <div className="bar">
        <BackButton />
        <div className="ttl" style={{ marginLeft: 10 }}>설정</div>
      </div>
      <div className="body">
        <SettingsForm
          initSettings={settings}
          designer={t?.designer_name ?? ''}
          salon={t?.salon_name ?? ''}
          slug={t?.slug ?? ''}
          stats={stats}
        />

        <div className="card">
          <div className="ch">이탈 고객{churnedRows.length > 0 ? <span className="ch-n"> {churnedRows.length}명</span> : null}</div>
          <Help inset>
            손님 상세보기나 챙길 고객에서 직접 이탈로 표시한 고객이에요. 챙길 고객·홈 신호에서 빠져 있고, 이력과 매출은 그대로 남아 있어요.
          </Help>
          <ChurnedList rows={churnedRows} />
        </div>

        <div className="card" style={{ padding: '14px 15px' }}>
          <div className="ch" style={{ padding: 0, marginBottom: 8 }}>데이터 수집</div>
          <Help>
            수집은 매장 PC(맥)에서 매주 일요일 1회 자동으로 돌아요. 그래서 화면은 마지막 수집 기준이고, 그 뒤에 생긴 방문·예약은
            다음 주에 들어와요. 재연결이 필요하면 관리자에게 문의하세요.
          </Help>
          <div className="set-row">고객 {(count ?? 0).toLocaleString()}명 · 최근 방문 {lastDate ? dayLabel(lastDate) : '-'}</div>
        </div>

        <div className="card" style={{ padding: '14px 15px' }}>
          <div className="ch" style={{ padding: 0, marginBottom: 8 }}>계정 · 데이터</div>
          <Help>데이터 삭제·탈퇴는 관리자에게 문의해 주세요(되돌릴 수 없어요).</Help>
          <div className="set-row" style={{ marginBottom: 10 }}>{user.email}</div>
          <a className="btn ghost" href="/api/export" style={{ display: 'block', textAlign: 'center', marginBottom: 10 }}>
            고객 CSV 내보내기
          </a>
          {/* 시작 안내(v11 P0) — 로그인 없이 열리는 페이지라 새로 오신 디자이너께 이 주소를 그대로 보내면 된다 */}
          <Link className="btn ghost" href="/start" style={{ marginBottom: 4 }}>사용 안내</Link>
          {/* 운영 숫자(v12 P2) — 운영자 폰(?op=1)에서만 보이는 입구. 디자이너 화면엔 없다 */}
          {cookies().get('mb-op')?.value === '1' ? (
            <Link className="btn ghost" href="/ops" style={{ marginBottom: 4 }}>운영 숫자</Link>
          ) : null}
          <div className="logout-row"><LogoutButton /></div>
        </div>
      </div>
      <OpMark />
      <ScreenReady />
    </main>
  );
}
