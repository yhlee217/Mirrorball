// HandSOS 자격증명을 KEK로 암호화해 pos_credentials 에 저장(평문 미보관).
// 실행: cd web && HANDSOS_ID=<id> HANDSOS_PW=<pw> node --env-file=.env.local scripts/set-handsos-creds.mjs <slug>
//   자격증명은 인자 대신 env 로 받아 shell 히스토리 노출을 줄임(그래도 취급 주의).
import { createClient } from '@supabase/supabase-js';
import crypto from 'node:crypto';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const svc = process.env.SUPABASE_SERVICE_ROLE_KEY;
const kekB64 = process.env.MIRRORBALL_KEK;
const slug = process.argv[2];
const hid = process.env.HANDSOS_ID;
const hpw = process.env.HANDSOS_PW;

if (!url || !svc || !kekB64 || !slug || !hid || !hpw) {
  console.error('사용법: HANDSOS_ID=<id> HANDSOS_PW=<pw> node --env-file=.env.local scripts/set-handsos-creds.mjs <slug>');
  process.exit(1);
}
const KEK = Buffer.from(kekB64, 'base64');
if (KEK.length !== 32) {
  console.error('MIRRORBALL_KEK 는 base64(32 bytes)');
  process.exit(1);
}
const seal = (key, buf) => {
  const iv = crypto.randomBytes(12);
  const c = crypto.createCipheriv('aes-256-gcm', key, iv);
  const ct = Buffer.concat([c.update(buf), c.final()]);
  return Buffer.concat([iv, ct, c.getAuthTag()]).toString('base64');
};

const admin = createClient(url, svc, { auth: { persistSession: false } });
const { data: tenant } = await admin.from('tenants').select('id').eq('slug', slug).maybeSingle();
if (!tenant) {
  console.error('tenant 없음:', slug);
  process.exit(1);
}
const enc = seal(KEK, Buffer.from(JSON.stringify({ id: hid, pw: hpw }), 'utf8'));
const { error } = await admin
  .from('pos_credentials')
  .upsert({ tenant_id: tenant.id, provider: 'handsos', enc_blob: enc, status: 'ok' }, { onConflict: 'tenant_id' });
if (error) {
  console.error('저장 실패:', error.message);
  process.exit(1);
}
console.log('자격증명 저장 완료(암호화):', slug);
