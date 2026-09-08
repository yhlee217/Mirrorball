// 거래 종류 — 판정은 워커(worker/txkind.py)가 하고 transactions.kind 에 저장한다.
// 화면은 읽기만 하되, 마이그레이션 직후 아직 kind 가 비어 있는 행이 있을 수 있어 폴백만 둔다.
// 어휘는 worker/txkind.py · service-name.ts 와 같이 맞춘다.
export type TxKind = 'service' | 'charge' | 'product' | 'refund';

export function txKind(kind: string | null | undefined, service: string | null | undefined): TxKind {
  if (kind === 'service' || kind === 'charge' || kind === 'product' || kind === 'refund') return kind;
  const s = service ?? '';
  if (/환불/.test(s)) return 'refund';
  if (/충전|선불|정액|상품권/.test(s)) return 'charge';
  if (/제품|판매|펌제|약제|기장추가/.test(s)) return 'product';
  return 'service';
}

export const won = (n: number) => (n >= 10000 ? Math.round(n / 10000) + '만' : n.toLocaleString()) + '원';
