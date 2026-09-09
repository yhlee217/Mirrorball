import rules from './tx-rules.json';
// 거래 종류 — 판정은 워커(worker/txkind.py)가 하고 transactions.kind 에 저장한다.
// 화면은 읽기만 하되, 마이그레이션 직후 아직 kind 가 비어 있는 행이 있을 수 있어 폴백만 둔다.
// 어휘는 worker/txkind.py · service-name.ts 와 같이 맞춘다.
export type TxKind = 'service' | 'charge' | 'product' | 'refund';

// 판정 어휘는 파이썬 워커(worker/txkind.py)와 같은 파일에서 읽는다 — 한쪽에만 메뉴를
// 추가하면 화면과 집계가 어긋나기 때문. 계산 방법만 각 언어가 따로 구현한다.
const RULES: RegExp[] = rules.order.map(
  (k) => new RegExp((rules.patterns as Record<string, string[]>)[k].join('|')),
);

export function txKind(kind: string | null | undefined, service: string | null | undefined): TxKind {
  if (kind === 'service' || kind === 'charge' || kind === 'product' || kind === 'refund') return kind;
  const s = service ?? '';
  for (let i = 0; i < RULES.length; i++) {
    if (RULES[i].test(s)) return rules.order[i] as TxKind;   // 순서가 의미를 갖는다
  }
  return 'service';
}


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
