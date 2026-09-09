import Link from 'next/link';
import { won } from '@/lib/format';
import { Empty } from '@/components/empty';

// 방문 관리 — 리뷰 요청 '복사 버튼'은 강요처럼 보여서 뺐다. 홈케어 팁도 손님께 전할 말투라
// 모든 줄에 펼쳐두니 목록이 지저분했다 → 기본은 접고 누를 때만 편다(네이티브 details, JS 없음).
// 토글은 행 우측 상단의 작은 표식 하나로만 둔다('홈케어 팁' 글자까지 넣으니 줄이 길어 보였다).
// 팁 토글은 링크 밖에 둬야 눌렀을 때 카르테로 이동하지 않는다.
type Item = {
  id: string;
  name: string;
  date: string;
  time: string | null;
  service: string;
  amount: number;
  visit_count: number;
  memo: string;
  tip: string;
};


function Row({ it }: { it: Item }) {
  return (
    <div className={'visit' + (it.tip ? ' has-tip' : '')}>
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
          {/* 매장이 그날 남긴 메모는 디자이너 본인의 기록이라 그대로 보여준다 */}
          {it.memo ? <div className="memo-note">{it.memo}</div> : null}
        </div>
      </Link>
      {it.tip ? (
        <details className="tipd">
          <summary aria-label="홈케어 팁 펼치기" title="홈케어 팁" />
          <div className="tip">{it.tip}</div>
        </details>
      ) : null}
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
  if (!items.length)
    return (
      <Empty
        title="최근 2주 방문 기록이 없어요"
        hint="수집은 주 1회예요. 방금 다녀가신 분은 다음 수집 뒤에 여기 나타나요."
      />
    );

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
