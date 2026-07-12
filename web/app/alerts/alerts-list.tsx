'use client';
import Link from 'next/link';
import { useState } from 'react';

type Item = { id: string; name: string; state: string; why: string; draft: string };

export default function AlertsList({ items }: { items: Item[] }) {
  const [toast, setToast] = useState('');

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
    setToast('문구 복사됨 · 카톡에 붙여넣기');
    setTimeout(() => setToast(''), 1800);
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
          </div>
        </div>
      ))}
      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
