/**
 * 운영 기록(ops_events)에 남길 화면 경로 — 손님·예약을 가리키는 id 는 ':id' 로 지운다(개선 계획 v5 P2).
 * 오류가 '어느 화면'에서 났는지면 충분하다. 쿼리(?filter=…)·해시도 버린다.
 */
const ID = /^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\d{3,})$/i;

export function cleanPath(raw: unknown): string {
  if (typeof raw !== 'string' || !raw.startsWith('/')) return '/';
  const path = raw.split(/[?#]/)[0];
  return path
    .split('/')
    .map((seg) => (ID.test(seg) ? ':id' : seg.slice(0, 40)))
    .join('/')
    .slice(0, 120);
}

export type Timing = {
  path: string; ms: number; cached: boolean; first: boolean; op: boolean; app: boolean; server?: number;
};

/**
 * 화면 속도 기록(개선 계획 v7 P0) — 화면을 누른 순간 → 내용이 뜬 순간. 남기는 건 경로(id 는 ':id') ·
 * 밀리초 · 받아 둔 화면을 바로 보여줬나(cached) · 앱을 처음 열었나(first)뿐이다. 1분이 넘는 값은
 * 폰이 잠겼다 깨어난 것 같은 잡음이라 버린다.
 * v10 P0 — 운영자 폰이었나(op, 설정 ?op=1) · 홈 화면 앱으로 열었나(app)도 참/거짓으로. 두 칸은 늘 남긴다 —
 * 감시(0025 ops_usage)가 '두 칸이 있는 기록'부터 디자이너 사용으로 센다.
 * v16 P2 — 앱 첫 열기 때만 서버가 첫 바이트를 보낸 때(server, ms)도. 전체 시간보다 길면 버린다(0029 ops_speed).
 */
export function cleanTiming(body: unknown): Timing | null {
  const b = (body && typeof body === 'object' ? body : {}) as Record<string, unknown>;
  const ms = typeof b.ms === 'number' && Number.isFinite(b.ms) ? Math.round(b.ms) : -1;
  if (ms < 0 || ms > 60_000) return null;
  const first = b.first === true;
  const server = first && typeof b.server === 'number' && Number.isFinite(b.server) ? Math.round(b.server) : -1;
  return {
    path: cleanPath(b.path), ms, cached: b.cached === true, first,
    op: b.op === true, app: b.app === true,
    ...(server >= 0 && server <= ms ? { server } : {}),
  };
}

export type CareOpen = { step: 'open'; op: boolean; app: boolean };

/**
 * 챙길 고객 줄을 펼쳤다(개선 계획 v16 P1) — 연락이 0인 까닭을 가르는 숫자. 펼쳤다는 것과 운영자 폰 · 홈 화면 앱
 * 여부뿐, 어느 손님인지는 남기지 않는다(보내 와도 버린다). 감시 · /ops 가 매장별 '챙길 고객 펼침 N번'으로 센다(0029).
 */
export function cleanCare(body: unknown): CareOpen | null {
  const b = (body && typeof body === 'object' ? body : {}) as Record<string, unknown>;
  if (b.step !== 'open') return null;
  return { step: 'open', op: b.op === true, app: b.app === true };
}

export type CspHit = { directive: string; blocked: string; path: string };

/** 막힐 뻔한 것 — 바깥 주소는 출처(https://host)만, 그 밖엔 이름(inline · eval · data · blob …)만. 주소의 경로 · 쿼리는 버린다. */
export function blockedOf(raw: unknown): string {
  const s = typeof raw === 'string' ? raw.trim() : '';
  if (!s) return 'unknown';
  if (/^[a-z-]+$/i.test(s)) return s.toLowerCase().slice(0, 20); // inline · eval · self · data · blob · wasm-eval
  try {
    const u = new URL(s);
    if (u.protocol === 'http:' || u.protocol === 'https:' || u.protocol === 'wss:') return u.origin.slice(0, 80);
    return u.protocol.replace(':', '').slice(0, 20); // data: · blob: · chrome-extension: …
  } catch {
    return 'unknown';
  }
}

/**
 * CSP 어긋남 기록(개선 계획 v14 P0 — v16 P3 부터는 막힌 것). 남기는 건 어긋난 규칙 · 막힌(막힐 뻔한) 것의 출처 ·
 * 화면 경로(id 는 지움)뿐 — 손님 정보는 없다. 브라우저 보고(report-uri, {"csp-report": {...}})와 화면의 어긋남 소식
 * (components/csp-watch) 두 모양을 다 받는다.
 */
export function cleanCsp(body: unknown): CspHit | null {
  const b = (body && typeof body === 'object' ? body : {}) as Record<string, unknown>;
  const r = (b['csp-report'] && typeof b['csp-report'] === 'object' ? b['csp-report'] : b) as Record<string, unknown>;
  const dir = r['effective-directive'] ?? r['violated-directive'] ?? r.directive;
  const directive = typeof dir === 'string' ? dir.trim().split(/\s+/)[0].toLowerCase() : '';
  if (!/^[a-z-]{2,40}$/.test(directive)) return null;
  const page = r['document-uri'] ?? r.path;
  let path = typeof page === 'string' ? page : '/';
  try {
    if (/^https?:/i.test(path)) path = new URL(path).pathname;
  } catch {
    path = '/';
  }
  return { directive, blocked: blockedOf(r['blocked-uri'] ?? r.blocked), path: cleanPath(path) };
}
