'use client';
import { useState } from 'react';

// '사비 결제' 표시 — 선불 잔액은 추정이라(POS 에 결제수단이 없다) 사람이 고칠 손잡이가 필요하다.
// 표시하면 그 시술은 잔액에서 차감하지 않고 매출로 잡는다. 반영은 다음 재계산 때.
export default function PocketToggle({ id, initial }: { id: string; initial: boolean }) {
  const [on, setOn] = useState(initial);
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    if (busy) return;
    const next = !on;
    setBusy(true);
    setOn(next); // 낙관적 반영 — 실패하면 되돌린다
    try {
      const r = await fetch('/api/tx-pocket', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transaction_id: id, pocket: next }),
      });
      if (!r.ok) throw new Error();
    } catch {
      setOn(!next);
      alert('저장하지 못했어요. 잠시 후 다시 눌러주세요.');
    } finally {
      setBusy(false);
    }
  };

  // 되묻지 않고 '지금 이 건을 어떻게 보고 있는지'를 보여준다.
  // 기본은 잔액 차감이고, 눌러야 사비로 바뀐다.
  return (
    <button type="button" className={'pocket' + (on ? ' on' : '')} onClick={toggle} disabled={busy}
      aria-pressed={on}
      title={on
        ? '사비 결제로 표시됨 — 눌러서 잔액 차감으로 되돌리기'
        : '충전 잔액에서 결제된 것으로 보고 있어요 — 눌러서 사비 결제로 표시'}>
      {on ? '사비 결제' : '잔액 차감'}
    </button>
  );
}
