'use client';
import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';

/**
 * 방문 탭 · 상세보기 이력의 '예약 기준' 줄 [노쇼] · 줄 그은 줄의 [되돌리기](api/booking-noshow). 주중에 취소 · 노쇼가 나도
 * 앱은 일요일 수집까지 몰라 시간이 지나면 방문으로 셌다 — 디자이너가 바로잡는 손잡이. 표시는 확인을 한 번 받는다.
 */
export default function NoShowButton({ id, undo = false }: { id: string; undo?: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [, startTransition] = useTransition();

  async function act() {
    if (!undo && !window.confirm('이 예약을 노쇼로 표시할까요?\n\n방문 · 방문 횟수에서 빠져요. 되돌리기로 언제든 돌릴 수 있어요.')) return;
    setBusy(true);
    try {
      const r = await fetch('/api/booking-noshow', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ id, undo }),
      });
      if (r.ok) startTransition(() => router.refresh()); // 횟수 · 줄을 서버에서 다시 그린다
      else window.alert('표시하지 못했어요. 잠시 뒤 다시 해 주세요.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <button type="button" className={'vns' + (undo ? ' undo' : '')} onClick={act} disabled={busy}
      aria-label={undo ? '노쇼 표시 되돌리기' : '노쇼로 표시'}>
      {undo ? '되돌리기' : '노쇼'}
    </button>
  );
}
