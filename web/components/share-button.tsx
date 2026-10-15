'use client';
import { useState } from 'react';
import { MSG } from '@/lib/copy';
import { shareOrCopy } from '@/lib/share';

/** 연락 기록에 안 남는 곳(방문 탭 '방문 뒤 안내')의 보내기 버튼. 챙길 고객은 alerts-list 가 shareOrCopy 로 직접 기록한다. */
export default function ShareButton({ text, className, children }: { text: string; className?: string; children: React.ReactNode }) {
  const [msg, setMsg] = useState('');
  const flash = (m: string) => {
    setMsg(m);
    setTimeout(() => setMsg(''), 1800);
  };
  return (
    <>
      <button
        type="button"
        className={className}
        onClick={async () => {
          const r = await shareOrCopy(text);
          if (r === 'copied') flash('문구 복사됨 · 카톡에 붙여넣기');
          else if (r === 'fail') flash(MSG.copyFail);
        }}
      >
        {children}
      </button>
      {msg ? <div className="toast" role="status">{msg}</div> : null}
    </>
  );
}
