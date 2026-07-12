// hayewoni 실데이터를 v2 스키마로 1회 임포트(이름 암호화).
// 실행: cd web && node --env-file=.env.local scripts/import-hayewoni.mjs <owner-email>
//   - <owner-email>: 앱에서 매직링크로 최소 1회 로그인한 계정(이 테넌트의 owner 로 연결)
//   - 소스: ../dist_app/hayewoni.json (v1 `python build_app.py` 산출물, 평문)
//   - MIRRORBALL_KEK: 앱(.env.local)과 반드시 동일해야 홈에서 복호화됨.

import { createClient } from '@supabase/supabase-js';
import crypto from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const svc = process.env.SUPABASE_SERVICE_ROLE_KEY;
const kekB64 = process.env.MIRRORBALL_KEK;
const ownerEmail = process.argv[2];

if (!url || !svc || !kekB64) {
  console.error('env 필요: NEXT_PUBLIC_SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, MIRRORBALL_KEK');
  process.exit(1);
}
if (!ownerEmail) {
  console.error('사용법: node --env-file=.env.local scripts/import-hayewoni.mjs <owner-email>');
  process.exit(1);
}
const KEK = Buffer.from(kekB64, 'base64');
if (KEK.length !== 32) {
  console.error('MIRRORBALL_KEK 는 base64(32 bytes). 생성: openssl rand -base64 32');
  process.exit(1);
}

const seal = (key, buf) => {
  const iv = crypto.randomBytes(12);
  const c = crypto.createCipheriv('aes-256-gcm', key, iv);
  const ct = Buffer.concat([c.update(buf), c.final()]);
  return Buffer.concat([iv, ct, c.getAuthTag()]).toString('base64');
};
const unseal = (key, b64) => {
  const raw = Buffer.from(b64, 'base64');
  const d = crypto.createDecipheriv('aes-256-gcm', key, raw.subarray(0, 12));
  d.setAuthTag(raw.subarray(raw.length - 16));
  return Buffer.concat([d.update(raw.subarray(12, raw.length - 16)), d.final()]);
};

const admin = createClient(url, svc, { auth: { persistSession: false } });

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(here, '..', '..', 'dist_app', 'hayewoni.json'), 'utf8'));
const seed = data.seed || [];
console.log(`소스: 고객 ${seed.length}명 · 예약 ${(data.bookings || []).length}건`);

// 1) owner 유저
const { data: usersList, error: ue } = await admin.auth.admin.listUsers();
if (ue) { console.error('listUsers:', ue.message); process.exit(1); }
const owner = usersList.users.find((u) => u.email === ownerEmail);
if (!owner) { console.error(`유저 없음: ${ownerEmail} — 앱에서 매직링크로 1회 로그인 후 재실행`); process.exit(1); }

// 2) 테넌트 + DEK
let tenantId, dek;
const { data: t } = await admin.from('tenants').select('id,dek_wrapped').eq('slug', 'hayewoni').maybeSingle();
if (t) {
  tenantId = t.id;
  dek = unseal(KEK, t.dek_wrapped);
} else {
  dek = crypto.randomBytes(32);
  const { data: nt, error: ne } = await admin
    .from('tenants')
    .insert({ slug: 'hayewoni', salon_name: data.salon || '살롱', designer_name: data.designer || null, dek_wrapped: seal(KEK, dek) })
    .select('id')
    .single();
  if (ne) { console.error('tenant:', ne.message); process.exit(1); }
  tenantId = nt.id;
}
await admin.from('memberships').upsert({ tenant_id: tenantId, user_id: owner.id, role: 'owner' });
console.log('테넌트:', tenantId, '· owner:', ownerEmail);

// 3) 고객(이름 암호화 + 재방문 신호 1차 파생)
const today = data.today || new Date().toISOString().slice(0, 10);
function deriveRevisit(c) {
  const dates = (c.history || []).map((h) => h.date).filter(Boolean).sort().reverse();
  const last = dates[0] || c.first_visit || null;
  const visits = c.loyalty_visits || 0;
  let cycle = null;
  if (dates.length >= 2) {
    const gaps = [];
    for (let i = 0; i < dates.length - 1; i++) gaps.push((new Date(dates[i]) - new Date(dates[i + 1])) / 86400000);
    gaps.sort((a, b) => a - b);
    const m = gaps[Math.floor(gaps.length / 2)];
    if (m > 0) cycle = Math.round(m);
  }
  let state = null;
  if (visits <= 1) state = 'new';
  else if (last) {
    const days = Math.round((new Date(today) - new Date(last)) / 86400000);
    const cyc = cycle || 42;
    if (days > cyc * 1.6) state = 'overdue';
    else if (days >= cyc) state = 'due';
  }
  return { last, cycle, state };
}
const rows = seed.map((c) => {
  const d = deriveRevisit(c);
  return {
    tenant_id: tenantId,
    ext_id: String(c.custno || c.id),
    pii_enc: seal(dek, Buffer.from(JSON.stringify({ name: c.name }), 'utf8')),
    pii_kid: 'v1',
    visit_count: c.loyalty_visits || 0,
    first_visit: c.first_visit || null,
    last_visit: d.last,
    total_won: c.total_won || 0,
    revisit_cycle_days: d.cycle,
    revisit_state: d.state,
  };
});
for (let i = 0; i < rows.length; i += 200) {
  const { error } = await admin.from('customers').upsert(rows.slice(i, i + 200), { onConflict: 'tenant_id,ext_id' });
  if (error) { console.error('customers:', error.message); process.exit(1); }
}
console.log(`고객 ${rows.length}명 임포트(이름 암호화)`);

// 4) 예약(고객 연결)
const { data: idrows } = await admin.from('customers').select('id,ext_id').eq('tenant_id', tenantId);
const extToId = new Map((idrows || []).map((r) => [r.ext_id, r.id]));
const seedIdToExt = new Map(seed.map((c) => [String(c.id), String(c.custno || c.id)]));
const bks = (data.bookings || []).map((b, i) => {
  const ext = seedIdToExt.get(String(b.id));
  return {
    tenant_id: tenantId,
    customer_id: ext ? extToId.get(ext) || null : null,
    date: b.date,
    time: b.time || null,
    service: b.service || null,
    source: 'handsos',
    ext_id: 'B' + i, // 인덱스 기반 유니크 키(같은 고객 예약 2건 충돌 방지)
  };
});
// 다가오는 예약은 매번 전량 새로고침(중복·스테일 방지)
await admin.from('bookings').delete().eq('tenant_id', tenantId);
if (bks.length) {
  const { error } = await admin.from('bookings').insert(bks);
  if (error) console.error('bookings:', error.message);
  else console.log(`예약 ${bks.length}건 임포트`);
}

// 5) 시술 이력(거래)
const txRows = [];
for (const c of seed) {
  const cid = extToId.get(String(c.custno || c.id));
  if (!cid) continue;
  (c.history || []).forEach((h, j) => {
    if (h && h.date) {
      txRows.push({
        tenant_id: tenantId,
        customer_id: cid,
        date: h.date,
        service: h.service || null,
        ext_id: String(c.custno || c.id) + '-' + j,
      });
    }
  });
}
for (let i = 0; i < txRows.length; i += 500) {
  const { error } = await admin.from('transactions').upsert(txRows.slice(i, i + 500), { onConflict: 'tenant_id,ext_id' });
  if (error) { console.error('transactions:', error.message); break; }
}
console.log(`시술 이력 ${txRows.length}건 임포트`);

// 6) 공개 소개 프로필
const prof = data.profile || {};
{
  const { error } = await admin.from('profiles').upsert(
    {
      tenant_id: tenantId,
      tagline: prof.tagline || null,
      bio: Array.isArray(prof.about) ? prof.about.join('\n\n') : prof.about || null,
      services: prof.specialties || [],
      faq: prof.faq || [],
      location: (prof.location && prof.location.address) || null,
      published: true,
    },
    { onConflict: 'tenant_id' },
  );
  if (error) console.error('profile:', error.message);
  else console.log('소개 프로필 임포트');
}

console.log('완료. 앱에서', ownerEmail, '로 로그인하면 실데이터가 보입니다.');
