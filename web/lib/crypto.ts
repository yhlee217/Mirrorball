import crypto from 'node:crypto';

// 하이브리드 암호화(서버 전용). 봉투 형식: base64( iv(12) || ciphertext || tag(16) ).
// KEK(마스터, env) → 테넌트별 DEK(랜덤 32B, KEK로 래핑해 tenants.dek_wrapped 저장) → PII 필드 암호화.
// app_crypto.py(AES-256-GCM) 와 동일 원리라 파이썬/노드 상호운용.

function kek(): Buffer {
  const b64 = process.env.MIRRORBALL_KEK;
  if (!b64) throw new Error('MIRRORBALL_KEK 미설정');
  const k = Buffer.from(b64, 'base64');
  if (k.length !== 32) throw new Error('MIRRORBALL_KEK 는 base64(32 bytes) 여야 함');
  return k;
}

function seal(key: Buffer, plaintext: Buffer): string {
  const iv = crypto.randomBytes(12);
  const c = crypto.createCipheriv('aes-256-gcm', key, iv);
  const ct = Buffer.concat([c.update(plaintext), c.final()]);
  return Buffer.concat([iv, ct, c.getAuthTag()]).toString('base64');
}

function open(key: Buffer, blobB64: string): Buffer {
  const raw = Buffer.from(blobB64, 'base64');
  const iv = raw.subarray(0, 12);
  const tag = raw.subarray(raw.length - 16);
  const ct = raw.subarray(12, raw.length - 16);
  const d = crypto.createDecipheriv('aes-256-gcm', key, iv);
  d.setAuthTag(tag);
  return Buffer.concat([d.update(ct), d.final()]);
}

export function generateDek(): Buffer {
  return crypto.randomBytes(32);
}
export function wrapDek(dek: Buffer): string {
  return seal(kek(), dek);
}
export function unwrapDek(wrappedB64: string): Buffer {
  return open(kek(), wrappedB64);
}
export function encryptPII(obj: unknown, dek: Buffer): string {
  return seal(dek, Buffer.from(JSON.stringify(obj), 'utf8'));
}
export function decryptPII(blobB64: string, dek: Buffer): Record<string, unknown> {
  return JSON.parse(open(dek, blobB64).toString('utf8'));
}
