export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { BackButton } from '@/components/back-button';
import { requireTenant } from '@/lib/tenant';
import ProfileEdit from './profile-edit';

export default async function ProfilePage() {
  const { supabase, tenantId } = await requireTenant();

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
      {/* 탭이 아니라 설정 안의 화면이다 — 한 번 만들고 거의 안 고치는 공개 페이지라 탭 한 칸을
          차지할 이유가 없었다(UX 계획 v2 2-3). '콘텐츠 제안' 칸은 없는 화면(404)을 가리켜 뺐다. */}
      <div className="bar">
        <BackButton fallback="/settings" />
        <div className="ttl" style={{ marginLeft: 10 }}>소개</div>
      </div>
      <div className="body">
        <p className="note" style={{ marginTop: 0 }}>손님에게 보이는 공개 소개예요. 저장하면 바로 반영됩니다.</p>
        {slug && (
          <a href={`/p/${slug}`} target="_blank" rel="noopener" className="pub-link">공개 페이지 미리보기 ↗</a>
        )}
        <ProfileEdit initial={initial} />
      </div>
    </main>
  );
}
