export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import HomeView from './home-view';
import OnboardButton from './onboard-button';

export default async function Page() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: mem } = await supabase
    .from('memberships')
    .select('tenant_id')
    .limit(1)
    .maybeSingle();

  if (!mem) {
    return (
      <main className="wrap">
        <div className="entry">
          <div className="brand">살롱 컨시어지</div>
          <p className="muted">아직 연결된 살롱이 없어요. 데모 데이터로 홈을 확인해보세요.</p>
          <OnboardButton />
        </div>
      </main>
    );
  }

  const tenantId = (mem as { tenant_id: string }).tenant_id;
  const [{ data: tenant }, { data: bookings }, { data: customers }] = await Promise.all([
    supabase.from('tenants').select('salon_name,slug,dek_wrapped,designer_name').eq('id', tenantId).maybeSingle(),
    supabase.from('bookings').select('id,date,time,service,customer_id').order('date').limit(20),
    supabase.from('customers').select('id,revisit_state,tier,visit_count'),
  ]);

  const t = tenant as { salon_name: string; dek_wrapped: string | null; designer_name: string | null } | null;
  const bk =
    (bookings as { id: string; date: string; time: string | null; service: string | null; customer_id: string | null }[]) ?? [];

  // 예약 고객 이름 복호화(DEK 있고 연결된 고객이 있을 때만)
  const nameById: Record<string, string> = {};
  const ids = bk.map((b) => b.customer_id).filter((x): x is string => !!x);
  if (t?.dek_wrapped && ids.length) {
    try {
      const dek = unwrapDek(t.dek_wrapped);
      const { data: pii } = await supabase.from('customers').select('id,pii_enc').in('id', ids);
      for (const row of (pii as { id: string; pii_enc: string | null }[]) ?? []) {
        if (row.pii_enc) {
          try {
            const p = decryptPII(row.pii_enc, dek);
            if (typeof p.name === 'string') nameById[row.id] = p.name;
          } catch {
            // 복호화 실패는 무시(이름만 '고객'으로 폴백)
          }
        }
      }
    } catch {
      // KEK 미설정 등 → 이름 없이 진행
    }
  }

  return (
    <HomeView
      designer={t?.designer_name ?? t?.salon_name ?? '디자이너'}
      bookings={bk}
      customers={(customers as never[]) ?? []}
      nameById={nameById}
    />
  );
}
