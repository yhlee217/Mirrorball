// 하이브리드 암호화(엣지 호환 · Web Crypto). node:crypto 대신 crypto.subtle 사용 → Cloudflare Workers/엣지 동작.
// 봉투 형식: base64( iv(12) || ciphertext || GCM태그(16) ) — Node/Python 버전과 동일(상호운용).

function b64encode(bytes: Uint8Array): string {
  let s = '';
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}

function b64decode(b64: string): Uint8Array {
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

function kekBytes(): Uint8Array {
  const b64 = process.env.MIRRORBALL_KEK;
  if (!b64) throw new Error('MIRRORBALL_KEK 미설정');
  const k = b64decode(b64);
  if (k.length !== 32) throw new Error('MIRRORBALL_KEK 는 base64(32 bytes) 여야 함');
  return k;
}

async function importKey(raw: Uint8Array): Promise<CryptoKey> {
  return crypto.subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);
}

async function seal(rawKey: Uint8Array, plaintext: Uint8Array): Promise<string> {
  const key = await importKey(rawKey);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, plaintext));
  const out = new Uint8Array(iv.length + ct.length);
  out.set(iv, 0);
  out.set(ct, iv.length);
  return b64encode(out);
}

async function open(rawKey: Uint8Array, blobB64: string): Promise<Uint8Array> {
  const raw = b64decode(blobB64);
  const iv = raw.subarray(0, 12);
  const ct = raw.subarray(12);
  const key = await importKey(rawKey);
  const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ct);
  return new Uint8Array(pt);
}

export async function generateDek(): Promise<Uint8Array> {
  return crypto.getRandomValues(new Uint8Array(32));
}
export async function wrapDek(dek: Uint8Array): Promise<string> {
  return seal(kekBytes(), dek);
}
export async function unwrapDek(wrappedB64: string): Promise<Uint8Array> {
  return open(kekBytes(), wrappedB64);
}
export async function encryptPII(obj: unknown, dek: Uint8Array): Promise<string> {
  return seal(dek, new TextEncoder().encode(JSON.stringify(obj)));
}
export async function decryptPII(blobB64: string, dek: Uint8Array): Promise<Record<string, unknown>> {
  const pt = await open(dek, blobB64);
  return JSON.parse(new TextDecoder().decode(pt));
}
