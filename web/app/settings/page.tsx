export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { mergeSettings } from '@/lib/settings';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import SettingsForm from './settings-form';
import ChurnedList from './churned-list';
import LogoutButton from '../logout-button';

export default async function SettingsPage() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) redirect('/');
  const tenantId = (mem as { tenant_id: string }).tenant_id;

  const [{ data: tenant }, { count }, { data: latest }, { data: churned }] = await Promise.all([
    supabase.from('tenants').select('salon_name,designer_name,slug,settings,dek_wrapped').eq('id', tenantId).maybeSingle(),
    supabase.from('customers').select('id', { count: 'exact', head: true }),
    supabase.from('transactions').select('date').order('date', { ascending: false }).limit(1),
    supabase
      .from('customers')
      .select('id,pii_enc,visit_count,last_visit,churned_at')
      .not('churned_at', 'is', null)
      .order('churned_at', { ascending: false })
      .limit(200),
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
  let dek: Uint8Array | null = null;
  if (t?.dek_wrapped) {
    try {
      dek = await unwrapDek(t.dek_wrapped);
    } catch {
      dek = null;
    }
  }
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
        <Link href="/" className="back">‹ 홈</Link>
        <div className="ttl" style={{ marginLeft: 10 }}>설정</div>
      </div>
      <div className="body">
        <SettingsForm
          initSettings={settings}
          designer={t?.designer_name ?? ''}
          salon={t?.salon_name ?? ''}
          slug={t?.slug ?? ''}
        />

        <div className="card">
          <div className="ch">이탈 고객 {churnedRows.length > 0 ? `· ${churnedRows.length}명` : ''}</div>
          <ChurnedList rows={churnedRows} />
          <p className="note" style={{ padding: '0 15px 13px' }}>
            직접 이탈로 표시한 고객이에요. 챙길 고객·홈 신호에서 빠져 있고, 이력과 매출은 그대로 남아 있어요.
          </p>
        </div>

        <div className="card" style={{ padding: '14px 15px' }}>
          <div className="ch" style={{ padding: 0, marginBottom: 8 }}>데이터 수집</div>
          <div className="set-row">고객 {count ?? 0}명 수집됨 · 최근 방문기록 {lastDate ?? '-'}</div>
          <p className="note">
            수집은 매장 PC(맥)에서 영업시간 중 30분마다 자동 실행됩니다. 재연결이 필요하면 관리자에게 문의하세요.
          </p>
        </div>

        <div className="card" style={{ padding: '14px 15px' }}>
          <div className="ch" style={{ padding: 0, marginBottom: 8 }}>계정 · 데이터</div>
          <div className="set-row" style={{ marginBottom: 10 }}>{user.email}</div>
          <a className="btn ghost" href="/api/export" style={{ display: 'block', textAlign: 'center', marginBottom: 10 }}>
            고객 CSV 내보내기
          </a>
          <LogoutButton />
          <p className="note">데이터 삭제·탈퇴는 관리자에게 문의해 주세요(되돌릴 수 없습니다).</p>
        </div>
      </div>
    </main>
  );
}
