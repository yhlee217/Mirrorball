'use client';
import { useState } from 'react';
import Link from 'next/link';

type Item = {
  id: string;
  name: string;
  date: string;
  service: string;
  amount: number;
  visit_count: number;
  draft: string;
};

const won = (n: number) => (n >= 10000 ? Math.round(n / 10000) + '만' : n.toLocaleString()) + '원';

function Row({ it }: { it: Item }) {
  const [msg, setMsg] = useState('');
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(it.draft);
      setMsg('복사됨 ✓');
    } catch {
      setMsg('복사 실패');
    }
    setTimeout(() => setMsg(''), 1600);
  };
  return (
    <div className="li" style={{ alignItems: 'flex-start' }}>
      <div className="av">{it.name.charAt(0)}</div>
      <div className="bd">
        <div className="nm">
          {it.name} 님 <span style={{ fontWeight: 400, fontSize: 12, color: 'var(--muted)' }}>· {it.visit_count}회</span>
        </div>
        <div className="sub">
          {it.service || '시술'}
          {it.amount ? ' · ' + won(it.amount) : ''}
        </div>
        <div className="row2" style={{ marginTop: 8 }}>
          <button type="button" className="btn ghost" onClick={copy}>
            {msg || '리뷰 요청 복사'}
          </button>
          <Link href={`/customer/${it.id}`} className="btn" style={{ textAlign: 'center', textDecoration: 'none' }}>
            카르테
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function VisitsList({
  items,
  today,
  yesterday,
}: {
  items: Item[];
  today: string;
  yesterday: string;
}) {
  if (!items.length) return <div className="empty">최근 2주 방문 기록이 없어요</div>;

  const label = (d: string) => (d === today ? '오늘' : d === yesterday ? '어제' : d);
  const groups: { key: string; rows: Item[] }[] = [];
  for (const it of items) {
    const k = label(it.date);
    const g = groups.find((x) => x.key === k);
    if (g) g.rows.push(it);
    else groups.push({ key: k, rows: [it] });
  }

  return (
    <>
      {groups.map((g) => (
        <div key={g.key}>
          <div className="sec-h" style={{ marginTop: 14 }}>
            {g.key} · {g.rows.length}명
          </div>
          <div className="card">
            {g.rows.map((it) => (
              <Row key={it.id + it.date} it={it} />
            ))}
          </div>
        </div>
      ))}
    </>
  );
}
