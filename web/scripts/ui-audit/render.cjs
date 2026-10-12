/**
 * UI 측정용 화면 그리기 — 7개 화면을 견본 데이터로 정적 HTML 로 그린다(UX 계획 v3 §6).
 *
 * 서버 화면(page.tsx)은 DB 를 읽어 여기서 못 그린다 → 표시 부품(home-view · …-list · cards)만 그리고,
 * 머리말(.bar · .top · .chd)은 각 page.tsx 와 같은 마크업을 여기 둔다. 머리말을 바꾸면 여기도 맞춘다.
 * 견본은 지어낸 이름·숫자다 — 실제 손님 데이터는 쓰지 않는다.
 *
 * 사용: node render.cjs <out>   (<out>/js 에 컴파일된 부품 → <out>/html/<화면>.html)
 */
const path = require('path');
const fs = require('fs');
const Module = require('module');

const WEB = path.resolve(__dirname, '../..');
const OUT = path.resolve(process.argv[2] || path.join(__dirname, 'out'));
const JS = path.join(OUT, 'js');
const HTML = path.join(OUT, 'html');

process.env.NODE_PATH = path.join(WEB, 'node_modules');
Module._initPaths();
const resolve = Module._resolveFilename;
Module._resolveFilename = function (req, ...rest) {
  if (req === 'next/navigation') return path.join(__dirname, 'stub/navigation.js');
  if (req.startsWith('@/')) req = path.join(JS, req.slice(2));
  return resolve.call(this, req, ...rest);
};

const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const r = (C, p) => renderToStaticMarkup(React.createElement(C, p));
const load = (f) => require(path.join(JS, f));

const { DEFAULT_SETTINGS } = load('lib/settings.js');
const { SyncChip } = load('components/sync-chip.js');

const TODAY = '2026-10-12'; // 월요일
const SYNC = { label: '10월 11일', daysAgo: 1, date: '2026-10-11' }; // 일요일 수집
const chip = r(SyncChip, { synced: SYNC });
const names = ['김서연', '박지훈', '이하은', '최민수', '정유진', '한지민', '오세훈', '윤아름', '장도윤', '서하린'];

const css = fs.readFileSync(path.join(WEB, 'app/globals.css'), 'utf8');
const tabbar =
  '<nav class="tabbar">' +
  [['🏠', '홈'], ['👥', '고객'], ['⏳', '챙길 고객'], ['✅', '방문']]
    .map(([i, t], n) => `<a class="tab${n ? '' : ' on'}"><div class="i">${i}</div><div class="tl">${t}</div></a>`)
    .join('') +
  '</nav>';
const doc = (main) =>
  `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">` +
  `<style>${css}</style></head><body>${main}${tabbar}</body></html>`;
/** page.tsx 모양 — <main class="wrap"> 머리줄(.bar) + 본문(.body) */
const screen = (bar, body) => doc(`<main class="wrap">${bar}<div class="body">${body}</div></main>`);
const bar = (title, { back = true, sync = false } = {}) =>
  `<div class="bar">${back ? '<a class="back">‹ 홈</a>' : ''}<div class="ttl"${back ? ' style="margin-left:10px"' : ''}>${title}</div>${sync ? chip : ''}</div>`;

const out = {};

// 홈(app/page.tsx → home-view) — 오늘 셋, 이번 주 둘(하나는 취소), 그 뒤 둘
out.home = doc(
  r(load('app/home-view.js').default, {
    designer: '하예원',
    synced: SYNC,
    today: TODAY,
    signals: { overdue: 37, due: 52 },
    week: { label: '10.4(일)~10.10(토)', cur: { visits: 23, firsts: 4, revenue: 3120000 }, prev: { visits: 21, firsts: 3, revenue: 2900000 }, work: null },
    careCount: 84,
    careQuiet: 5,
    briefs: [
      { id: 'b1', date: TODAY, time: '11:00', service: '뿌리염색', customer_id: 'c1', status: '예약', name: names[0], off: false, tag: null,
        gap: { text: '6주 만', late: false }, last: '뿌리염색+커트', prefer: ['두피 예민 — 저자극 약제', '뿌리 볼륨 살려 드라이'],
        recent: '(2026-08) 딸 결혼식 준비 중', prepaid: 520000, rec: { label: '클리닉', short: '뿌리염색 손님 38%가 함께' } },
      { id: 'b2', date: TODAY, time: '15:00', service: '남자컷', customer_id: 'c2', status: '예약', name: names[1], off: false, tag: '두 번째 방문',
        gap: { text: '4주 만', late: false }, last: '커트', prefer: [], recent: null, prepaid: 0, rec: { label: '다운펌', short: '남자커트 손님 39%가 함께' } },
      { id: 'b3', date: TODAY, time: '17:30', service: '디지털펌', customer_id: 'c3', status: '예약', name: names[2], off: false, tag: null,
        gap: { text: '3개월 만 · 평소 6주', late: true }, last: '디지털펌', prefer: ['곱슬 심함, 뿌리 쪽 짧게'], recent: '(2026-06) 이직 준비', prepaid: 0, rec: null },
      { id: 'b4', date: '2026-10-13', time: '14:00', service: '여자컷', customer_id: 'c4', status: '취소', name: names[3], off: true, tag: null,
        gap: null, last: null, prefer: [], recent: null, prepaid: 0, rec: null },
      { id: 'b5', date: '2026-10-15', time: '13:00', service: '여자컷', customer_id: null, status: '예약', name: names[4], off: false, tag: '첫 방문',
        gap: null, last: null, prefer: [], recent: null, prepaid: 0, rec: null },
    ],
    later: [
      { id: 'l1', date: '2026-10-21', time: '14:00', service: '펌', customer_id: 'c5', status: '예약', name: names[5], off: false },
      { id: 'l2', date: '2026-10-28', time: '10:30', service: '남자컷', customer_id: null, status: '예약', name: names[6], off: false },
    ],
  }),
);

// 챙길 고객(app/alerts/page.tsx) — 실제 화면이 만드는 문장 모양 그대로
const items = names.slice(0, 8).map((n, i) => {
  const over = i % 2 === 0;
  return {
    id: 'a' + i, name: n, phone: '01012345678', state: over ? 'overdue' : 'due',
    why: over ? `${2 + (i % 3)}개월째 · 평소 5주 · 뿌리염색` : '5주째 · 평소 4주 · 남자커트',
    note: over ? '마지막 방문 7.1(수)' : '마지막 방문 9.2(수)', prepaid: i === 0 ? 520000 : i === 3 ? 180000 : 0,
    draft: over
      ? `${n}님, 오랜만이에요! 벌써 ${2 + (i % 3)}개월 됐네요. 늘 찾아주셔서 감사해요 🙏 지난 뿌리염색 뿌리 올라올 때쯤이라 한번 뵙고 싶어서 연락드려요. 편하신 때 편하게 연락 주세요!`
      : `${n}님, 지난 커트 머리 자라 정리하실 때쯤이라 연락드려요. 편하신 시간에 예약 도와드릴게요!`,
  };
});
// 첫 방문 손님(개선 계획 v4) — 맨 위 안부, 맨 아래 다시 오실 때. 견본은 그대로 8명(전후 비교가 되게)
items.splice(6);
items.unshift({ id: 'f1', name: names[8], phone: '01012345678', state: 'hello', why: '안부 · 6일 전 · 뿌리염색',
  note: '첫 방문 10.6(월) · 첫 방문 14일 안에만 떠요',
  draft: `${names[8]}님, 지난주 뿌리염색 해드린 하예원이에요 😊 지내보시니 괜찮으세요? 너무 뜨거운 물로 자주 감지 않으시면 색이 더 오래가요. 불편한 점 있으면 편하게 말씀 주세요!` });
items.push({ id: 'f2', name: names[9], phone: '01012345678', state: 'back', why: '다시 오실 때 · 5주째 · 뿌리염색',
  note: '첫 방문 9.4(금) · 뿌리염색 보통 5주 · 10주 지나면 목록에서 내려가요',
  draft: `${names[9]}님, 하예원이에요! 5주 전 처음 오셨을 때 뿌리염색 해드렸는데, 뿌리 올라올 때쯤이라 연락드려요. 편하신 시간에 예약 도와드릴게요!` });
out.alerts = screen(bar('챙길 고객 <span class="sect-n">84명</span>', { back: false, sync: true }),
  r(load('app/alerts/alerts-list.js').default, { items, quiet: 3, quietDays: 14, effect: { contacted: 32, came: 11, booked: 4 } }));

// 방문(app/visits/page.tsx) — 어제 셋 · 토 셋 · 목 넷, 셋 중 하나꼴로 매장 메모
const visits = names.map((n, i) => ({
  id: 'v' + i, name: n, date: i < 3 ? '2026-10-11' : i < 6 ? '2026-10-10' : '2026-10-08', time: `1${i % 8}:00`,
  service: i % 2 ? '커트+뿌리염색' : '디지털펌', amount: 80000 + i * 10000, visit_count: 1 + i,
  memo: i % 3 === 0 ? '뿌리 볼륨 원하심, 다음엔 클리닉 같이' : '', tip: '이틀은 감지 말고, 말릴 때 손으로 감아쥐듯 말리면 컬이 오래 살아요.',
}));
out.visits = screen('', `<div class="top"><b>방문</b><span class="sect-n">2주</span>${chip}</div>`
  + r(load('app/visits/visits-list.js').default, { items: visits, today: TODAY, yesterday: '2026-10-11' }));

// 고객 목록(app/customers/page.tsx)
const rows = Array.from({ length: 20 }, (_, i) => ({
  id: 'c' + i, name: names[i % 10], visit_count: 1 + i, total_won: 50000 * (i + 1), last_visit: `2026-0${1 + (i % 9)}-1${i % 9}`,
  first_visit: '2024-01-01', state: ['overdue', 'due', null, 'new'][i % 4], cycle: 35, hasBooking: i % 7 === 0, hasPhone: true,
  tail: '1234', churned: false, gender: 'F', visits_90d: 1, visits_180d: 2, visits_365d: 4, prepaid_balance: i % 6 === 2 ? 300000 : 0,
}));
out.customers = screen(bar('고객 <span class="sect-n">1,136명</span>'),
  r(load('app/customers/customers-list.js').default, { rows, settings: DEFAULT_SETTINGS, asOf: SYNC.date, today: TODAY, initialFilter: null }));

// 카르테(app/customer/[id]/page.tsx) — 화면 순서대로
const C = load('app/customer/[id]/cards.js');
const hist = Array.from({ length: 8 }, (_, i) => ({
  id: 'h' + i, date: `2026-0${9 - i}-0${1 + i}`, time: '14:00', service: i % 2 ? '여자컷(원장)' : '뿌리염색', amount_won: 60000,
  memo: i === 0 ? '뿌리 볼륨 원하심' : null, kind: 'service', paid_out_of_pocket: false,
}));
out.carte = screen('<div class="bar"><a class="back">‹ 홈</a></div>',
  '<div class="chd"><div class="cav">김</div><div><h2>김서연 님<span class="tag-vip">VIP</span><span class="ctag overdue">이탈 위험</span></h2>'
  + '<div class="s">14회 · 누적 182만</div></div></div>'
  + r(C.FactStrip, { lastVisit: '2026-08-01', sinceLast: 72, next: { kind: 'expected', date: '2026-09-05', basis: '평소 5주 주기', estimated: false, overdueDays: 37 },
    prepaid: true, balance: 520000, avg: 85000, top: 3, vacation: 10 })
  + r(C.MemoAiCard, { cust: { memo_ai: '- 두피 예민 — 저자극 약제\n- 뿌리 볼륨 살려 드라이\n- 앞머리 짧게 싫어함', memo_ai_recent: '- (2026-08) 딸 결혼식 준비 중\n- (2026-06) 제주 여행' }, today: TODAY })
  + r(C.RecommendCard, { items: [
    { kind: 'due', label: '뿌리염색', reason: '마지막 7주 전 · 보통 5주마다', short: '' },
    { kind: 'cross', label: '클리닉', reason: '뿌리염색 손님 38%가 클리닉도 받아요 · 주로 두피 클리닉', short: '' },
  ] })
  + r(C.NextBookingCard, { bk: null })
  + r(C.HistoryCard, { history: hist, pocketIds: hist.slice(0, 7).map((h) => h.id), top: [['뿌리염색', 7], ['여자컷', 5], ['클리닉', 2]] })
  + r(load('app/customer/[id]/customer-note.js').default, { id: 'x', initMemo: '', initTags: ['두피예민', '볼륨'] })
  + r(C.FamilyCard, { list: [{ id: 'f1', name: names[1], vip: false, visit_count: 6, last_visit: '2026-09-20' }], today: TODAY })
  + r(C.PrepaidCard, { charges: [{ id: 'p1', date: '2026-03-01', amount_won: 1000000 }], chargedTotal: 1000000, balance: 520000 })
  + '<div class="admin-sec"><div class="admin-h">관리</div>'
  + r(load('app/customer/[id]/gender-picker.js').default, { id: 'x', manual: null, inferred: 'F' })
  + r(load('app/customer/[id]/churn-toggle.js').default, { id: 'x', churnedAt: null })
  + '</div>');

// 통계(app/stats/page.tsx) — 요약 · 신규 재방문 · 바쁜 시간 · 월별 매출 · 더 보기(접힘)
const S = load('app/stats/cards.js');
const grid = [[6, 0, 9, 8, 7, 14, 10], [11, 0, 14, 12, 13, 26, 18], [12, 0, 15, 16, 17, 38, 21], [9, 0, 12, 13, 15, 29, 12], [7, 0, 10, 11, 14, 6, 2]];
const days = [26, 0, 26, 24, 24, 23, 27];
const avg = grid.map((row) => row.map((n, d) => (days[d] ? n / days[d] : 0)));
out.stats = screen(bar('통계', { sync: true }),
  r(S.SummaryCard, {
    span: '1–11일', work: { now: 9, prev: 10 }, rev: 9820000, revDelta: 12, visits: 380, prevVisits: 391,
    fc: { show: true, worked: 9, remaining: 17, soFar: 9820000, center: 22500000, low: 21800000, high: 23900000, months: 6, lastMonth: 20500000 },
    bkLeft: 18, active: [['5월', 410], ['6월', 425], ['7월', 418], ['8월', 402], ['9월', 398], ['10.11', 395]].map(([label, count]) => ({ label, count })),
    prepaid: { sum: 76040000, n: 129 }, careCount: 84, unknownGender: 212, prepaidGone: 18,
  })
  + r(S.CohortCard, {
    cohorts: [['2026-04', 25, 6, false], ['2026-05', 29, 7, false], ['2026-06', 23, 5, false], ['2026-07', 24, 6, true], ['2026-08', 23, 4, true], ['2026-09', 14, 2, true]]
      .map(([month, total, back, open]) => ({ month, label: `${Number(month.slice(5))}월`, total, back, open })),
    medianDays: 38, repeat: 512, total: 1136, vacation: true,
  })
  + r(S.HeatCard, { heat: { grid, avg, days, off: days.map((n, d) => n === 0 && d === 1), max: Math.max(...avg.flat()), total: 400, noTime: 12 }, hasOff: true })
  + r(S.MonthCard, {
    months: [['2026-05', '5월', 19800000], ['2026-06', '6월', 21200000], ['2026-07', '7월', 15400000], ['2026-08', '8월', 20100000], ['2026-09', '9월', 20500000], ['2026-10', '10월', 9820000]]
      .map(([key, label, rev], i) => ({ key, label, rev, partial: i === 5 })),
    work: [26, 25, 12, 26, 25, 9], syncLabel: '10.11',
  })
  + '<details class="more-sec"><summary>더 보기 <span class="sect-n">시술별 · 성별 · 연락 효과 · 적중률 · 누적</span></summary>'
  + r(S.ServiceCard, {
    rows: [['여자컷(원장)', 410, 33000, 186, 300], ['뿌리염색', 220, 65000, 114, 160], ['남자컷(원장)', 180, 18000, 72, 130], ['디지털펌', 60, 180000, 18, 45], ['클리닉', 40, 40000, 4, 9], ['앞머리컷', 35, 5000, 20, 25]]
      .map(([service, count, avg, back, base]) => ({ service, count, avg, back, base })),
    vacation: true,
  })
  + r(S.GenderCard, { g: { M: { n: 420, perVisit: 21000, cycle: 32, share: 24 }, F: { n: 760, perVisit: 64000, cycle: 49, share: 76 }, unknown: 212, noClue: 190, proxy: 22, manual: 14, rate: 85, kids: 38, total: 1392 } })
  + r(S.ContactEffectCard, { groups: { first: { contacted: 12, came: 3, booked: 1 }, repeat: { contacted: 40, came: 14, booked: 4 } },
    hello: { sent: { n: 12, back: 3 }, unsent: { n: 9, back: 1 } }, since: '2026-10-12' })
  + r(S.RecommendHitCard, { hits: { due: { n: 1240, hit: 719, base: 0.31 }, cross: { n: 310, hit: 28, base: 0.04 } } })
  + r(S.TotalsCard, { customers: 1393, revenue: 410000000, tx: 9307 })
  + '</details>');

// 설정(app/settings/page.tsx) — 입력 카드들(아래 이탈 고객·수집·계정 카드는 빠짐)
out.settings = screen(bar('설정'),
  r(load('app/settings/settings-form.js').default, {
    initSettings: { ...DEFAULT_SETTINGS, off_weekdays: [1], off_dates: [{ from: '2026-07-01', to: '2026-07-14' }] },
    designer: '하예원', salon: '살롱톤', slug: 'demo', stats: [],
  }));

fs.mkdirSync(HTML, { recursive: true });
for (const [k, v] of Object.entries(out)) fs.writeFileSync(path.join(HTML, `${k}.html`), v);
console.log(`${Object.keys(out).length}개 화면 → ${HTML}`);
