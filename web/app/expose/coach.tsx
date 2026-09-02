'use client';
import { useState } from 'react';
import { captionFor, reviewRequestFor } from '@/lib/coach';
import { friendlyService } from '@/lib/service-name';

// 'AI로 다듬기'는 지금 같은 템플릿을 되돌려줘 눌러도 변화가 없었다(가짜 버튼) → 제거.
// 실제 Workers AI 를 붙일 때 다시 살린다(/api/ai 라우트와 buildPrompt 는 그대로 둠).
// 카드의 시술명은 고객에게 그대로 나가는 문구라 friendlyService 로 표시한다.

type Svc = { service: string; count: number };
type Target = { id: string; name: string; last_visit: string | null; service: string | null };

function DraftCard({ title, sub, initial }: { title: string; sub?: string; initial: string }) {
  const [text, setText] = useState(initial);
  const [msg, setMsg] = useState('');

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setMsg('복사됐어요 ✓');
    } catch {
      setMsg('복사 실패');
    }
    setTimeout(() => setMsg(''), 1800);
  };

  return (
    <div className="card" style={{ padding: '13px 15px', marginBottom: 10 }}>
      <div className="ch" style={{ padding: 0, marginBottom: 2 }}>{title}</div>
      {sub ? <div className="sub" style={{ marginBottom: 8 }}>{sub}</div> : null}
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} />
      <button type="button" className="btn" style={{ width: '100%', marginTop: 8 }} onClick={copy}>
        {msg || '복사'}
      </button>
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
            title={friendlyService(s.service) || s.service}
            sub={`최근 30일 ${s.count}건 — 전후 사진과 함께 올리기 좋아요`}
            initial={captionFor(s.service, salon)}
          />
        ))
      ) : (
        <div className="empty">최근 시술 데이터가 없어요</div>
      )}

      <div className="sec-h" style={{ marginTop: 18 }}>리뷰 요청</div>
      {reviewTargets.length ? (
        reviewTargets.map((t) => (
          <DraftCard
            key={t.id}
            title={`${t.name} 님`}
            sub={[t.last_visit, friendlyService(t.service)].filter(Boolean).join(' · ')}
            initial={reviewRequestFor(t.name, t.service ?? undefined, t.last_visit)}
          />
        ))
      ) : (
        <div className="empty">최근 방문 고객이 없어요</div>
      )}
    </>
  );
}
