'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

// 이탈 표시/해제. 자동 판정('이탈 위험')은 추정이라, 확실히 아는 디자이너가 확정할 수 있어야 한다.
// 표시하면 챙길 고객·홈 신호에서 빠지고, 이력은 그대로 남는다(언제든 해제 가능).
export default function ChurnToggle({ id, churnedAt }: { id: string; churnedAt: string | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const apply = async (next: boolean) => {
    if (next && !window.confirm('이 고객을 이탈로 표시할까요?\n\n챙길 고객·이탈위험에서 빠집니다. 이력은 그대로 남고 언제든 되돌릴 수 있어요.')) return;
    setBusy(true);
    try {
      const r = await fetch('/api/customer-churn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: id, churned: next }),
      });
      if (r.ok) router.refresh();
    } catch {
      /* noop */
    }
    setBusy(false);
  };

  if (churnedAt) {
    return (
      <div className="signal-card c">
        <div className="sig-t">이탈 고객</div>
        <div className="sig-w">{churnedAt.slice(0, 10)}에 직접 표시하셨어요 · 챙길 고객에서 빠져 있어요</div>
        <button className="btn ghost" style={{ marginTop: 10 }} onClick={() => apply(false)} disabled={busy}>
          {busy ? '처리 중…' : '이탈 표시 해제'}
        </button>
      </div>
    );
  }
  return (
    <button className="churn-set" onClick={() => apply(true)} disabled={busy}>
      {busy ? '처리 중…' : '이탈 고객으로 표시'}
    </button>
  );
}
