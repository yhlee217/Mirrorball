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
