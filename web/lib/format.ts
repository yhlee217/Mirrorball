/**
 * 표시용 포맷 한 곳.
 *
 * 금액 표기가 화면 5곳에 각자 있었고 서로 달랐다:
 *   · 고객목록은 String() 이라 5,000 이 '5000'(콤마 없음)으로 나왔다
 *   · '억' 단위는 통계에만 있어, 같은 금액이 다른 화면에선 '12000만원'으로 보였다
 *   · 0 처리도 제각각
 * 같은 숫자가 화면마다 다르게 보이는 건 신뢰를 깎으므로 하나로 모은다.
 */

/** 1,234,567 → '123만원' · 123,456,789 → '1.2억원' · 5,000 → '5,000원' */
export function won(n: number): string {
  if (!n) return '0원';
  const a = Math.abs(n);
  if (a < 10000) return n.toLocaleString() + '원';
  // 만 단위로 반올림한 뒤에 '억'으로 올릴지 정한다. 먼저 억부터 재면 99,999,999 가
  // '10,000만원'으로 나온다(1억에 가까운데 만 단위로 남는다).
  const man = Math.round(n / 10000);
  if (Math.abs(man) >= 10000) return (man / 10000).toFixed(1) + '억원';
  return man.toLocaleString() + '만원';
}

/** won() 표기의 단위 — '만원'·'억원'도 '원'으로 끝나니 긴 것부터 본다. */
const unitOf = (s: string) => (s.endsWith('억원') ? '억원' : s.endsWith('만원') ? '만원' : '원');

/** 범위 — 단위가 같으면 한 번만: '2,180~2,390만원'. 다르면 '9,800만원~1.1억원'. */
export function wonRange(a: number, b: number): string {
  const x = won(a);
  const y = won(b);
  const u = unitOf(x);
  return u === unitOf(y) ? `${x.slice(0, -u.length)}~${y}` : `${x}~${y}`;
}

/**
 * 객단가(방문 1회·시술 1건 가격) — 10만원 아래는 만원 아래 한 자리까지.
 * 합계는 만원 단위면 충분하지만 가격은 아니다: 65,000 이 won() 으로는 '7만원'이 된다.
 * 33,000 → '3.3만원' · 30,000 → '3만원' · 5,000 → '5,000원' · 180,000 → '18만원'
 */
export function price(n: number): string {
  const a = Math.abs(n);
  if (a < 10000 || a >= 100000) return won(n);
  return (Math.round(n / 1000) / 10).toString() + '만원';
}
