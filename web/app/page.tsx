export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import HomeView from './home-view';
import OnboardButton from './onboard-button';

export default async function Page() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  // 로그인 사용자의 테넌트(멤버십). RLS 로 자기 것만 보인다.
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
    supabase.from('tenants').select('salon_name,slug').eq('id', tenantId).maybeSingle(),
    supabase.from('bookings').select('id,date,time,service,customer_id').order('date').limit(20),
    supabase.from('customers').select('id,revisit_state,tier,visit_count'),
  ]);

  return (
    <HomeView
      salon={(tenant as { salon_name: string } | null)?.salon_name ?? '디자이너'}
      bookings={(bookings as never[]) ?? []}
      customers={(customers as never[]) ?? []}
    />
  );
}
