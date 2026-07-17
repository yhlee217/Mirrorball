'use client';
import { useState } from 'react';
import { captionFor, reviewRequestFor } from '@/lib/coach';

type Svc = { service: string; count: number };
type Target = { id: string; name: string; last_visit: string | null; service: string | null };

function DraftCard({
  title,
  sub,
  initial,
  kind,
  ctx,
}: {
  title: string;
  sub?: string;
  initial: string;
  kind: string;
  ctx: Record<string, string>;
}) {
  const [text, setText] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setMsg('복사됐어요 ✓');
    } catch {
      setMsg('복사 실패');
    }
  };
  const refine = async () => {
    setBusy(true);
    setMsg('');
    try {
      const r = await fetch('/api/ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, context: { ...ctx, text } }),
      });
      const d = await r.json();
      if (d.text) {
        setText(d.text);
        setMsg(d.source === 'ai' ? 'AI로 다듬었어요 ✓' : '문구를 새로 뽑았어요');
      } else setMsg('실패');
    } catch {
      setMsg('실패');
    }
    setBusy(false);
  };

  return (
    <div className="card" style={{ padding: '13px 15px' }}>
      <div className="ch" style={{ padding: 0, marginBottom: 2 }}>{title}</div>
      {sub ? <div className="sub" style={{ marginBottom: 8 }}>{sub}</div> : null}
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} />
      <div className="row2" style={{ marginTop: 8 }}>
        <button type="button" className="btn ghost" onClick={copy}>복사</button>
        <button type="button" className="btn" onClick={refine} disabled={busy}>
          {busy ? '다듬는 중…' : 'AI로 다듬기'}
        </button>
      </div>
      {msg ? <div className="set-msg">{msg}</div> : null}
    </div>
  );
}

export default function Coach({
  salon,
  topServices,
  reviewTargets,
}: {
  salon: string;
  topServices: Svc[];
  reviewTargets: Target[];
}) {
  return (
    <>
      <div className="sec-h">이번 주 콘텐츠 제안</div>
      {topServices.length ? (
        topServices.map((s) => (
          <DraftCard
            key={s.service}
            title={s.service}
            sub={`최근 30일 ${s.count}건 — 전후 사진·후기 올리기 좋아요`}
            initial={captionFor(s.service, salon)}
            kind="caption"
            ctx={{ service: s.service, salon }}
          />
        ))
      ) : (
        <div className="empty">최근 시술 데이터가 없어요</div>
      )}

      <div className="sec-h" style={{ marginTop: 16 }}>리뷰 요청</div>
      {reviewTargets.length ? (
        reviewTargets.map((t) => (
          <DraftCard
            key={t.id}
            title={`${t.name} 님`}
            sub={`${t.last_visit ?? ''}${t.service ? ' · ' + t.service : ''}`}
            initial={reviewRequestFor(t.name, t.service ?? undefined)}
            kind="review"
            ctx={{ name: t.name, service: t.service ?? '' }}
          />
        ))
      ) : (
        <div className="empty">최근 방문 고객이 없어요</div>
      )}
    </>
  );
}
