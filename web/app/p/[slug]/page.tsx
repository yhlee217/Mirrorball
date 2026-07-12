export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { notFound } from 'next/navigation';
import { createClient } from '@supabase/supabase-js';

type Spec = { name: string; desc: string };
type Faq = { q: string; a: string };

// 공개 소개 페이지 — 손님용. published 프로필만, 고객 PII 없음.
export default async function PublicProfile({ params }: { params: { slug: string } }) {
  const admin = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.SUPABASE_SERVICE_ROLE_KEY!, {
    auth: { persistSession: false },
  });

  const { data: tenant } = await admin
    .from('tenants')
    .select('id,salon_name,designer_name')
    .eq('slug', params.slug)
    .maybeSingle();
  if (!tenant) notFound();
  const t = tenant as { id: string; salon_name: string | null; designer_name: string | null };

  const { data: profile } = await admin
    .from('profiles')
    .select('tagline,bio,location,services,faq,published')
    .eq('tenant_id', t.id)
    .maybeSingle();
  const p = profile as {
    tagline: string | null;
    bio: string | null;
    location: string | null;
    services: unknown;
    faq: unknown;
    published: boolean;
  } | null;
  if (!p || !p.published) notFound();

  const services = Array.isArray(p.services) ? (p.services as Spec[]) : [];
  const faq = Array.isArray(p.faq) ? (p.faq as Faq[]) : [];
  const name = t.designer_name || t.salon_name || '';

  return (
    <main className="pub">
      <div className="pub-hd">
        <div className="pub-name">{name}</div>
        {p.tagline && <div className="pub-tag">{p.tagline}</div>}
      </div>

      {p.bio && (
        <div className="pub-sec">
          <p className="pub-bio">{p.bio}</p>
        </div>
      )}

      {services.length > 0 && (
        <div className="pub-sec">
          <h3>시술</h3>
          {services.map((s, i) => (
            <div className="pub-svc" key={i}>
              <div className="pub-svc-n">{s.name}</div>
              {s.desc && <div className="pub-svc-d">{s.desc}</div>}
            </div>
          ))}
        </div>
      )}

      {faq.length > 0 && (
        <div className="pub-sec">
          <h3>자주 묻는 질문</h3>
          {faq.map((f, i) => (
            <div className="pub-faq" key={i}>
              <div className="pub-q">Q. {f.q}</div>
              <div className="pub-a">{f.a}</div>
            </div>
          ))}
        </div>
      )}

      {p.location && (
        <div className="pub-sec">
          <h3>위치</h3>
          <div className="pub-loc">{p.location}</div>
        </div>
      )}

      <div className="pub-foot">Mirrorball</div>
    </main>
  );
}
