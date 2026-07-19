import Link from 'next/link';

// 방문 관리 — 리뷰 요청 '복사 버튼'은 강요처럼 보여서 뺐다. 대신 그날 받은 시술의 홈케어 팁을
// 본문에 그대로 노출한다(손님께 전할 말 겸, 디자이너 기억용). 행 전체가 카르테로 연결된다.
type Item = {
  id: string;
  name: string;
  date: string;
  time: string | null;
  service: string;
  amount: number;
  visit_count: number;
  tip: string;
};

const won = (n: number) => (n >= 10000 ? Math.round(n / 10000) + '만' : n.toLocaleString()) + '원';

function Row({ it }: { it: Item }) {
  return (
    <Link href={`/customer/${it.id}`} className="li li-link" style={{ alignItems: 'flex-start' }}>
      <div className="av">{it.name.charAt(0)}</div>
      <div className="bd">
        <div className="nm">
          {it.name} 님
          <span style={{ fontWeight: 400, fontSize: 12, color: 'var(--muted)' }}> · {it.visit_count}회째</span>
        </div>
        <div className="sub">
          {it.time ? it.time + ' · ' : ''}
          {it.service || '시술'}
          {it.amount ? ' · ' + won(it.amount) : ''}
        </div>
        {it.tip ? <div className="tip">{it.tip}</div> : null}
      </div>
    </Link>
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
