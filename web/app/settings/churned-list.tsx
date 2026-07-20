'use client';
import Link from 'next/link';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

// 이탈로 표시한 고객 모아보기 + 해제. 표시는 여러 화면에서 하지만 '되돌리기'는 여기 모아둔다
// (실수로 표시했을 때 어디서 찾아야 할지 헤매지 않도록).
type Row = { id: string; name: string; visit_count: number; last_visit: string | null; churned_at: string };

export default function ChurnedList({ rows }: { rows: Row[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState('');

  const restore = async (id: string) => {
    setBusy(id);
    try {
      const r = await fetch('/api/customer-churn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: id, churned: false }),
      });
      if (r.ok) router.refresh();
    } catch {
      /* noop */
    }
    setBusy('');
  };

  if (!rows.length) return <div className="empty">이탈로 표시한 고객이 없어요</div>;

  return (
    <>
      {rows.map((r) => (
        <div className="li" key={r.id}>
          <div className="av">{r.name.charAt(0)}</div>
          <div className="bd">
            <Link href={`/customer/${r.id}`} className="nm" style={{ color: 'inherit', textDecoration: 'none' }}>
              {r.name} 님
            </Link>
            <div className="sub">
              {r.visit_count}회{r.last_visit ? ' · 마지막 ' + r.last_visit : ''} · {r.churned_at.slice(0, 10)} 표시
            </div>
          </div>
          <button className="churn-undo" onClick={() => restore(r.id)} disabled={busy === r.id}>
            {busy === r.id ? '…' : '해제'}
          </button>
        </div>
      ))}
    </>
  );
}
