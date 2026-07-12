export const dynamic = 'force-dynamic';

import { redirect } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import ProfileEdit from './profile-edit';

export default async function ProfilePage() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) redirect('/');
  const tenantId = (mem as { tenant_id: string }).tenant_id;

  const { data: prof } = await supabase
    .from('profiles')
    .select('tagline,bio,location,services,faq')
    .eq('tenant_id', tenantId)
    .maybeSingle();

  const p = (prof as {
    tagline: string | null;
    bio: string | null;
    location: string | null;
    services: unknown;
    faq: unknown;
  } | null) || null;

  const initial = {
    tagline: p?.tagline ?? '',
    bio: p?.bio ?? '',
    location: p?.location ?? '',
    services: Array.isArray(p?.services) ? (p!.services as { name: string; desc: string }[]) : [],
    faq: Array.isArray(p?.faq) ? (p!.faq as { q: string; a: string }[]) : [],
  };

  return (
    <main className="wrap">
      <div className="bar">
        <div className="ttl">소개 페이지 편집</div>
      </div>
      <div className="body">
        <div className="sec-h">손님에게 보이는 공개 소개 · 저장하면 반영</div>
        <ProfileEdit initial={initial} />
      </div>
    </main>
  );
}
