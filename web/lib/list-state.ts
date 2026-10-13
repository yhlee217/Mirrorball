/**
 * 목록 화면의 상태를 주소(URL)에 담는다 — 카르테를 보고 돌아와도 검색·조건·펼친 수가 그대로(모바일 개선 M2).
 *
 * 홈 화면에 설치한 앱에는 브라우저 뒤로 버튼이 없고, 화면 상태(useState)는 다른 화면에 다녀오면 사라진다.
 * 그래서 검색어를 다시 치고 조건을 다시 켜야 했다. 주소에 담아 두면 뒤로 가기가 그 주소로 돌아오고,
 * 화면은 주소를 읽어 같은 상태로 열린다(목록 길이가 같아 스크롤 자리도 돌아온다).
 * 주소 바꾸기는 window.history.replaceState — 서버를 다시 부르지 않는다(Next 14.1+ 가 주소를 따라간다).
 */

/** 고객 목록 조건 칩 — 홈·통계 링크의 ?filter= 도 이 안에서만 받는다. */
export const CHIPS = ['overdue', 'due', 'new', 'vip', 'booking', 'nophone', 'churned', 'nogender', 'prepaid'] as const;
/** '필터' 안에 접어 두는 칩 — 이게 켜져 있으면 접힌 판을 펼친 채로 연다(켜진 조건이 안 보이면 헷갈린다). */
export const FOLDED = ['booking', 'nophone', 'churned', 'nogender', 'prepaid'];

export type ListState = {
  q: string;
  chips: string[];
  more: boolean;
  visit: string;
  rev: string;
  rec: string;
  svc: string;
  sort: string;
};

export const LIST_DEFAULT: ListState = { q: '', chips: [], more: false, visit: '', rev: '', rec: '', svc: '', sort: 'recent' };

const SELECTS = {
  visit: ['reg', 'rep', 'new'],
  rev: ['100', '50', 'lo'],
  rec: ['1m', '3m', '6m', '1y'],
  svc: ['펌', '염색', '클리닉', '컷'],
  sort: ['recent', 'revenue', 'visits', 'avg', 'new', 'name'],
} as const;
const pick = (v: string | null, ok: readonly string[], dflt = '') => (v && ok.includes(v) ? v : dflt);

/** 주소 → 상태. 모르는 값은 버린다(손으로 고친 주소·옛 링크). 옛 ?filter= 하나도 칩으로 받는다. */
export function decodeList(get: (k: string) => string | null): ListState {
  const chips = [...new Set([...(get('f') ?? '').split(','), get('filter') ?? ''])].filter((c) =>
    (CHIPS as readonly string[]).includes(c));
  const s: ListState = {
    q: (get('q') ?? '').slice(0, 40),
    chips,
    more: get('m') === '1',
    visit: pick(get('v'), SELECTS.visit),
    rev: pick(get('r'), SELECTS.rev),
    rec: pick(get('rc'), SELECTS.rec),
    svc: pick(get('s'), SELECTS.svc),
    sort: pick(get('o'), SELECTS.sort, 'recent'),
  };
  if (chips.some((c) => FOLDED.includes(c)) || s.visit || s.rev || s.rec || s.svc) s.more = true;
  return s;
}

/** 상태 → 주소 쿼리('?' 없이). 기본값은 적지 않는다 — 아무것도 안 걸면 빈 문자열. */
export function encodeList(s: ListState): string {
  const p = new URLSearchParams();
  if (s.q.trim()) p.set('q', s.q.trim().slice(0, 40));
  if (s.chips.length) p.set('f', [...s.chips].sort().join(','));
  if (s.more) p.set('m', '1');
  if (s.visit) p.set('v', s.visit);
  if (s.rev) p.set('r', s.rev);
  if (s.rec) p.set('rc', s.rec);
  if (s.svc) p.set('s', s.svc);
  if (s.sort !== 'recent') p.set('o', s.sort);
  return p.toString();
}

/** 챙길 고객 — 펼친 수(50명씩)와 열린 줄. */
export function decodeAlerts(get: (k: string) => string | null, step: number): { shown: number; open: string | null } {
  const n = Number(get('n'));
  const open = get('open');
  return {
    shown: Number.isFinite(n) && n > step ? Math.min(Math.ceil(n / step) * step, 2000) : step,
    open: open && /^[0-9a-f-]{8,40}$/i.test(open) ? open : null,
  };
}

export function encodeAlerts(shown: number, open: string | null, step: number): string {
  const p = new URLSearchParams();
  if (shown > step) p.set('n', String(shown));
  if (open) p.set('open', open);
  return p.toString();
}

/** 주소만 바꾼다(기록을 늘리지 않고, 서버도 다시 부르지 않는다). 같으면 손대지 않는다. */
export function replaceQuery(query: string): void {
  if (typeof window === 'undefined') return;
  const url = window.location.pathname + (query ? `?${query}` : '');
  if (url !== window.location.pathname + window.location.search) window.history.replaceState(null, '', url);
}
