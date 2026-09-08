'use client';
import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';

// '사비 결제' 표시 — 선불 잔액은 추정이라(POS 에 결제수단이 없다) 사람이 고칠 손잡이가 필요하다.
// 표시하면 그 시술은 잔액에서 차감하지 않고 매출로 잡는다.
//
// 저장만 하고 끝내면 안 된다: 추정 잔액은 서버 컴포넌트가 이 고객 거래 전체로 계산하므로,
// 저장 뒤 router.refresh() 로 다시 그려야 위 카드의 잔액이 실제로 움직인다.
export default function PocketToggle({ id, initial }: { id: string; initial: boolean }) {
  const [on, setOn] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  const toggle = async () => {
    if (saving || pending) return;
    const next = !on;
    setSaving(true);
    setOn(next); // 낙관적 반영 — 실패하면 되돌린다
    try {
      const r = await fetch('/api/tx-pocket', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transaction_id: id, pocket: next }),
      });
      if (!r.ok) throw new Error();
      startTransition(() => router.refresh()); // 잔액 다시 계산해 표시
    } catch {
      setOn(!next);
      alert('저장하지 못했어요. 잠시 후 다시 눌러주세요.');
    } finally {
      setSaving(false);
    }
  };

  const busy = saving || pending;

  // 되묻지 않고 '지금 이 건을 어떻게 보고 있는지'를 보여준다.
  // 기본은 잔액 차감이고, 눌러야 사비로 바뀐다.
  return (
    <button type="button" className={'pocket' + (on ? ' on' : '') + (busy ? ' busy' : '')}
      onClick={toggle} disabled={busy} aria-pressed={on}
      title={on
        ? '사비 결제로 표시됨 — 눌러서 잔액 차감으로 되돌리기'
        : '충전 잔액에서 결제된 것으로 보고 있어요 — 눌러서 사비 결제로 표시'}>
      {busy ? '…' : on ? '사비 결제' : '잔액 차감'}
    </button>
  );
}
