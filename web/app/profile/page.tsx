export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
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

  const [{ data: tenant }, { data: prof }] = await Promise.all([
    supabase.from('tenants').select('slug').eq('id', tenantId).maybeSingle(),
    supabase.from('profiles').select('tagline,bio,location,services,faq').eq('tenant_id', tenantId).maybeSingle(),
  ]);
  const slug = (tenant as { slug: string } | null)?.slug ?? null;

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
      <div className="body">
        <div className="hello">
          <div className="e">
            <span>Profile</span>
          </div>
          <h2>소개</h2>
          <div className="s">손님에게 보이는 공개 소개예요. 저장하면 바로 반영됩니다.</div>
        </div>
        <div className="seg">
          <span className="seg-b on">소개 편집</span>
          <Link href="/profile/content" className="seg-b">콘텐츠 제안</Link>
        </div>
        {slug && (
          <a href={`/p/${slug}`} target="_blank" rel="noopener" className="pub-link">공개 페이지 미리보기 ↗</a>
        )}
        <ProfileEdit initial={initial} />
      </div>
    </main>
  );
}
