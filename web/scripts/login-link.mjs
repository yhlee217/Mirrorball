// 이메일 발송 없이 로그인 링크 생성(dev 전용). 이메일 레이트리밋 우회.
// 실행: cd web && node --env-file=.env.local scripts/login-link.mjs <email>
//   출력 URL 을 브라우저에 붙여넣으면 그 계정으로 로그인됨(dev 서버 실행 중이어야 함).
import { createClient } from '@supabase/supabase-js';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const svc = process.env.SUPABASE_SERVICE_ROLE_KEY;
const email = process.argv[2];
const site = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';
if (!url || !svc || !email) {
  console.error('사용법: node --env-file=.env.local scripts/login-link.mjs <email>');
  process.exit(1);
}
const admin = createClient(url, svc, { auth: { persistSession: false } });
const { data, error } = await admin.auth.admin.generateLink({ type: 'magiclink', email });
if (error) {
  console.error('실패:', error.message);
  process.exit(1);
}
const tokenHash = data.properties.hashed_token;
const type = data.properties.verification_type || 'magiclink';
console.log('\n아래 URL 을 브라우저에 붙여넣으면 로그인됩니다(이메일 없음 · dev 서버 실행 중이어야 함):\n');
console.log(`${site}/auth/confirm?token_hash=${tokenHash}&type=${type}`);
console.log('');
