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

/**
 * 선불 원장 — worker/txkind.py 의 ledger 와 같은 규칙을 화면에서도 쓴다.
 *
 * 잔액을 DB(customers.prepaid_balance)에만 의존하면 워커 재계산 전까지 0으로 보인다.
 * 카르테는 그 고객의 거래를 이미 들고 있으므로 여기서 바로 계산해 보여준다.
 * 규칙: 충전은 잔액을 늘리고, 시술은 잔액이 남아 있는 동안만 차감한다.
 * 잔액이 바닥나면 그 뒤는 사비로 보고(추정이 스스로 교정됨), '사비 결제'로 표시된 건은 건드리지 않는다.
 */
export type LedgerItem = {
  date: string;
  time?: string | null;
  id?: string;
  amount: number;
  kind: TxKind;
  pocket?: boolean;
};

export function ledger(items: LedgerItem[]): {
  balance: number;
  revenue: number;
  charged: number;
  covered: number;
} {
  const key = (t: LedgerItem) => `${t.date ?? ''} ${t.time ?? ''} ${t.id ?? ''}`;
  const rows = [...items].sort((a, b) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : 0));

  let balance = 0;
  let revenue = 0;
  let charged = 0;
  let covered = 0;

  for (const it of rows) {
    const amt = it.amount || 0;
    if (it.kind === 'charge') {
      balance += amt;
      charged += amt;
      revenue += amt;
      continue;
    }
    if (it.kind === 'refund') {
      revenue += amt; // 환불은 보통 음수
      continue;
    }
    if (it.pocket) {
      revenue += amt; // 사비로 표시 — 잔액 건드리지 않음
      continue;
    }
    if (balance <= 0) {
      revenue += amt;
      continue;
    }
    const use = Math.min(balance, amt);
    balance -= use;
    covered += use;
    revenue += amt - use;
  }
  return { balance, revenue, charged, covered };
}
