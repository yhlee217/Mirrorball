'use client';
import { useState } from 'react';
import Link from 'next/link';

type Row = { id: string; name: string; visit_count: number; state: string | null; last_visit: string | null };

export default function CustomersList({ rows }: { rows: Row[] }) {
  const [q, setQ] = useState('');
  const term = q.trim();
  const filtered = term ? rows.filter((r) => r.name.includes(term)) : rows;

  return (
    <>
      <input
        className="search"
        placeholder="이름 검색"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      <div className="sec-h">{filtered.length}명</div>
      <div className="card">
        {filtered.length ? (
          filtered.map((r) => (
            <Link key={r.id} href={`/customer/${r.id}`} className="li li-link">
              <div className="av">{r.name.charAt(0)}</div>
              <div className="bd">
                <div className="nm">{r.name} 님</div>
                <div className="sub">
                  {r.visit_count}회{r.last_visit ? ' · 마지막 ' + r.last_visit : ''}
                </div>
              </div>
              <div className="rt">
                {r.state === 'overdue' ? '이탈 위험' : r.state === 'due' ? '재방문 도래' : ''}
              </div>
            </Link>
          ))
        ) : (
          <div className="empty">검색 결과가 없어요</div>
        )}
      </div>
    </>
  );
}
