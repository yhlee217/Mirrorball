'use client';
import Link from 'next/link';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

type Item = { id: string; name: string; state: string; why: string; draft: string };

export default function AlertsList({ items }: { items: Item[] }) {
  const router = useRouter();
  const [toast, setToast] = useState('');
  const [busy, setBusy] = useState('');

  const flash = (m: string) => {
    setToast(m);
    setTimeout(() => setToast(''), 1800);
  };

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.cssText = 'position:fixed;left:-9999px';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
      } catch {
        /* noop */
      }
      document.body.removeChild(ta);
    }
    flash('문구 복사됨 · 카톡에 붙여넣기');
  }

  // '이 분은 확실히 안 오신다'는 판단이 드는 자리가 바로 여기라, 목록에서 곧장 처리하게 뒀다.
  // 표시하면 이 목록·홈 신호에서 빠지고, 고객 카르테에서 되돌릴 수 있다.
  async function markChurned(id: string, name: string) {
    if (!window.confirm(`${name} 님을 이탈로 표시할까요?\n\n챙길 고객에서 빠집니다. 이력은 그대로 남고, 고객 카르테에서 언제든 되돌릴 수 있어요.`)) return;
    setBusy(id);
    try {
      const r = await fetch('/api/customer-churn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: id, churned: true }),
      });
      if (r.ok) {
        flash(`${name} 님을 이탈로 표시했어요`);
        router.refresh();
      } else flash('처리 실패');
    } catch {
      flash('처리 실패');
    }
    setBusy('');
  }

  if (!items.length) return <div className="empty">지금 챙길 고객이 없어요</div>;

  return (
    <>
      {items.map((it) => (
        <div className="care" key={it.id}>
          <div className="hd">
            <span className={'tag ' + (it.state === 'overdue' ? 'rose' : 'gold')}>
              {it.state === 'overdue' ? '이탈 위험' : '재방문 도래'}
            </span>
            <span className="cnm">{it.name} 님</span>
          </div>
          <div className="why">{it.why}</div>
          <div className="draft">
            <div className="lab">추천 문구</div>
            {it.draft}
          </div>
          <div className="row2">
            <button className="btn" onClick={() => copy(it.draft)}>📋 문구 복사</button>
            <Link className="btn ghost" href={`/customer/${it.id}`}>고객 보기</Link>
            <button className="btn ghost" onClick={() => markChurned(it.id, it.name)} disabled={busy === it.id}>
              {busy === it.id ? '처리 중…' : '이탈 처리'}
            </button>
          </div>
        </div>
      ))}
      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
