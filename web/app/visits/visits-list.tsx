import Link from 'next/link';
import { man } from '@/lib/format';
import { dayLabel } from '@/lib/week';
import { Empty } from '@/components/empty';
import { Help } from '@/components/help';

// 방문 관리 — 리뷰 요청 '복사 버튼'은 강요처럼 보여서 뺐다. 홈케어 팁도 손님께 전할 말투라
// 모든 줄에 펼쳐두니 목록이 지저분했다 → 기본은 접고 누를 때만 편다(네이티브 details, JS 없음).
// 토글은 행 우측 상단의 작은 표식 하나로만 둔다('홈케어 팁' 글자까지 넣으니 줄이 길어 보였다).
// 팁 토글은 링크 밖에 둬야 눌렀을 때 카르테로 이동하지 않는다.
export type Item = {
  id: string; // 손님 기록이 없으면(수집 전에 처음 오신 분) 빈 값 — 상세보기 없이 한 줄만
  name: string;
  date: string;
  time: string | null;
  service: string;
  amount: number;
  nth: number; // 그 방문이 몇 번째였나(lib/visits visitOrdinals) — 수집 전이면 다음 번째
  pending: boolean; // 마지막 수집 뒤 지난 예약으로 보여 주는 줄(방문 기록은 다음 수집에 들어온다)
  memo: string;
  tip: string;
};

function Row({ it }: { it: Item }) {
  const tag = it.pending ? (
    <span className="tag-pend">예약 기준</span>
  ) : it.nth <= 1 ? (
    <span className="tag-new">첫 방문</span>
  ) : (
    <span className="nm-n">{it.nth}회째</span>
  );
  const body = (
    <>
      <div className="av">{it.name.charAt(0)}</div>
      <div className="bd">
        <div className="nm">
          {it.name}
          {tag}
        </div>
        <div className="sub">
          {it.time ? it.time + ' · ' : ''}
          {it.service || '시술'}
          {it.amount ? ' · ' + man(it.amount) : ''}
        </div>
        {/* 매장이 그날 남긴 메모는 디자이너 본인의 기록이라 그대로 보여준다 */}
        {it.memo ? <div className="memo-note">{it.memo}</div> : null}
      </div>
    </>
  );
  return (
    <div className={'visit' + (it.tip ? ' has-tip' : '')}>
      {it.id ? (
        <Link href={`/customer/${it.id}`} className="li li-link" style={{ alignItems: 'flex-start' }}>
          {body}
        </Link>
      ) : (
        <div className="li" style={{ alignItems: 'flex-start' }}>
          {body}
        </div>
      )}
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
  syncLabel = null,
}: {
  items: Item[];
  today: string;
  yesterday: string;
  syncLabel?: string | null; // '10월 12일 14:05' — 그 뒤 방문은 예약으로 보여 준다
}) {
  if (!items.length)
    return (
      <Empty title="최근 2주 방문 없음" hint="방금 다녀가신 분은 다음 수집 뒤에 나와요." />
    );

  const label = (d: string) => (d === today ? '오늘' : d === yesterday ? '어제' : dayLabel(d));
  const groups: { key: string; rows: Item[] }[] = [];
  for (const it of items) {
    const k = label(it.date);
    const g = groups.find((x) => x.key === k);
    if (g) g.rows.push(it);
    else groups.push({ key: k, rows: [it] });
  }

  // 날짜마다 카드를 따로 두지 않고 한 카드 안에 날짜 머리줄로 — 홈 '이번 주' 예약과 같은 모양
  return (
    <div className="card">
      {items.some((it) => it.pending) ? (
        <Help>
          마지막 수집({syncLabel ?? '일요일'}) 뒤에 다녀가신 분은 아직 방문 기록이 없어서, 지난 예약으로 보여 드려요(&lsquo;예약
          기준&rsquo;). 시술 · 금액 · 메모와 예약 없이 오신 분은 다음 수집(일요일) 때 들어오고, 그때 &lsquo;N회째&rsquo;로 바뀌어요.
        </Help>
      ) : null}
      {groups.map((g) => (
        <div key={g.key}>
          <div className="bf-day">{g.key} · {g.rows.length}명</div>
          {g.rows.map((it, i) => (
            <Row key={(it.id || it.name) + it.date + (it.time ?? '') + i} it={it} />
          ))}
        </div>
      ))}
    </div>
  );
}
