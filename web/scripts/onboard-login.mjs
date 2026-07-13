// 디자이너 로그인 온보딩: 이메일 → 디자이너 테넌트 멤버십 + 매직링크(이메일 없이 dev 로그인).
// 실행: cd web && node --env-file=.env.local scripts/onboard-login.mjs <email> <slug>
//   각 디자이너는 자기 이메일로 로그인 → 자기 테넌트 데이터만 보임(멀티테넌트).
import { createClient } from '@supabase/supabase-js';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const svc = process.env.SUPABASE_SERVICE_ROLE_KEY;
const site = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
const email = process.argv[2];
const slug = process.argv[3];
if (!url || !svc || !email || !slug) {
  console.error('사용법: node --env-file=.env.local scripts/onboard-login.mjs <email> <slug>');
  process.exit(1);
}
const admin = createClient(url, svc, { auth: { persistSession: false } });

const { data: t } = await admin.from('tenants').select('id,designer_name,slug').eq('slug', slug).maybeSingle();
if (!t) {
  console.error(`tenant 없음: ${slug} — worker/onboard_designers.py 로 먼저 생성하세요`);
  process.exit(1);
}

// 유저 조회(페이지네이션) 없으면 생성
let user = null;
for (let page = 1; page <= 20 && !user; page++) {
  const { data: list, error } = await admin.auth.admin.listUsers({ page, perPage: 200 });
  if (error) {
    console.error('listUsers:', error.message);
    process.exit(1);
  }
  const users = list.users || [];
  user = users.find((u) => u.email === email) || null;
  if (users.length < 200) break;
}
if (!user) {
  const { data: created, error } = await admin.auth.admin.createUser({ email, email_confirm: true });
  if (error) {
    console.error('user 생성 실패:', error.message);
    process.exit(1);
  }
  user = created.user;
  console.log('유저 생성:', email);
}

const { error: me } = await admin.from('memberships').upsert({ tenant_id: t.id, user_id: user.id, role: 'owner' });
if (me) {
  console.error('멤버십 실패:', me.message);
  process.exit(1);
}

const { data, error } = await admin.auth.admin.generateLink({ type: 'magiclink', email });
if (error) {
  console.error('링크 실패:', error.message);
  process.exit(1);
}
const tokenHash = data.properties.hashed_token;
const type = data.properties.verification_type || 'magiclink';
console.log(`\n${t.designer_name || slug} (${email}) → 아래 URL 을 브라우저에 붙여넣으면 로그인:\n`);
console.log(`${site}/auth/confirm?token_hash=${tokenHash}&type=${type}\n`);
