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

export type Timing = { path: string; ms: number; cached: boolean; first: boolean; op: boolean; app: boolean };

/**
 * 화면 속도 기록(개선 계획 v7 P0) — 화면을 누른 순간 → 내용이 뜬 순간. 남기는 건 경로(id 는 ':id') ·
 * 밀리초 · 받아 둔 화면을 바로 보여줬나(cached) · 앱을 처음 열었나(first)뿐이다. 1분이 넘는 값은
 * 폰이 잠겼다 깨어난 것 같은 잡음이라 버린다.
 * v10 P0 — 운영자 폰이었나(op, 설정 ?op=1) · 홈 화면 앱으로 열었나(app)도 참/거짓으로. 두 칸은 늘 남긴다 —
 * 감시(0025 ops_usage)가 '두 칸이 있는 기록'부터 디자이너 사용으로 센다.
 */
export function cleanTiming(body: unknown): Timing | null {
  const b = (body && typeof body === 'object' ? body : {}) as Record<string, unknown>;
  const ms = typeof b.ms === 'number' && Number.isFinite(b.ms) ? Math.round(b.ms) : -1;
  if (ms < 0 || ms > 60_000) return null;
  return {
    path: cleanPath(b.path), ms, cached: b.cached === true, first: b.first === true,
    op: b.op === true, app: b.app === true,
  };
}
