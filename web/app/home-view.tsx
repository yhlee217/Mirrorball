import Link from 'next/link';
import { syncLine } from '@/lib/sync';
import { won } from '@/lib/format';
import { dayHead } from '@/lib/briefing';
import { dayLabel, type WeekNums } from '@/lib/week';
import { Empty } from '@/components/empty';

type Signals = { overdue: number; due: number; new: number; vip: number };
type Synced = { label: string; daysAgo: number } | null;

/** 예약 한 건과 그 손님 브리핑. 모으는 쪽은 app/page.tsx, 말 만들기는 lib/briefing.ts. */
export type Brief = {
  id: string;
  date: string;
  time: string | null;
  service: string | null;
  customer_id: string | null;
  status: string | null;
  name: string;
  off: boolean; // 취소·노쇼 — '그 시간이 비었다'는 정보라 보여주되 세지 않는다
  tag: '첫 방문' | '두 번째 방문' | null;
  gap: { text: string; late: boolean } | null; // '6주 만 · 평소 5주'
  last: string | null; // 지난번 시술
  prefer: string[]; // 매장 메모 정리 — 선호(최대 2줄)
  recent: string | null; // 매장 메모 정리 — 근황 중 가장 최근 한 줄
  prepaid: number; // 선불 잔액(추정)
};
type Later = { id: string; date: string; time: string | null; service: string | null; customer_id: string | null; status: string | null; name: string; off: boolean };

const offWord = (status: string | null) => (status?.includes('노쇼') ? '노쇼' : '취소');
const arrow = <span className="rt" style={{ fontSize: 18, color: '#B4B2A9' }} aria-hidden>›</span>;

export default function HomeView({
  designer,
  synced,
  today,
  signals,
  week,
  careCount,
  careQuiet,
  briefs,
  later,
}: {
  designer: string;
  synced: Synced; // 마지막 수집 시각. 주 1회라 '언제 기준 화면인지'를 밝힌다
  today: string; // KST — 날짜 머리말의 '오늘·내일'
  signals: Signals;
  week: { label: string; cur: WeekNums; prev: WeekNums }; // 지난 한 주와 그 전주(lib/week.ts)
  careCount: number; // '할 일' 수 — 챙길 고객 탭과 같은 기준(최근 연락한 분 제외)
  careQuiet: number; // 최근 연락해서 잠시 빠진 수
  briefs: Brief[]; // 앞으로 7일 예약(날짜·시각 순)
  later: Later[]; // 그 뒤 예약 — 접어 둔다
}) {
  // 수집은 주 1회다. 며칠 전 자료인지 모르고 보면 '예약이 없다'를 사실로 오해한다.
  const freshness = syncLine(synced);
  const active = briefs.filter((b) => !b.off).length;
  const laterActive = later.filter((b) => !b.off).length;
  const bookingBasis = `${synced ? `${synced.label} 수집 기준` : '수집 시점 기준'} · ${active}건 — 그 뒤로 잡힌 예약은 HandSOS에서 확인하세요`;

  // 날짜별로 묶는다(이미 날짜·시각 순). 하루에 몇 분인지가 한눈에 보여야 준비가 된다.
  const days: { date: string; items: Brief[] }[] = [];
  for (const b of briefs) {
    const cur = days[days.length - 1];
    if (cur && cur.date === b.date) cur.items.push(b);
    else days.push({ date: b.date, items: [b] });
  }

  return (
    <main className="wrap">
      <div className="body">
        <div className="hello">
          <div className="e">
            <span>For the Designer</span>
            <Link href="/settings" className="gear" aria-label="설정" title="설정">⚙</Link>
          </div>
          <h2>{designer}님, 안녕하세요 👋</h2>
          {freshness ? <div className="s">{freshness}</div> : null}
        </div>

        <div className="hsig">
          <Link href="/customers?filter=overdue" className="hs x" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="hn">{signals.overdue}</div><div className="hl">이탈위험 ›</div>
          </Link>
          <Link href="/customers?filter=due" className="hs d" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="hn">{signals.due}</div><div className="hl">재방문도래 ›</div>
          </Link>
          <Link href="/customers?filter=new" className="hs g" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="hn">{signals.new}</div><div className="hl">신규 ›</div>
          </Link>
          <Link href="/customers?filter=vip" className="hs v" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="hn">{signals.vip}</div><div className="hl">VIP ›</div>
          </Link>
        </div>

        {/* 이번 주 요약 — 주 1회 수집 리듬에 맞춘 첫 카드. 챙길 고객·통계로 가는 길도 여기 하나로 모았다
            (전에는 칩 줄과 카드가 같은 곳을 가리켰다). */}
        <div className="card">
          <div className="ch">이번 주 요약</div>
          <div className="csub">지난 한 주 · {week.label} · 수집된 거래 기준</div>
          <div className="wk-nums">
            <div>
              <span className="wl">방문</span>
              <b>{week.cur.visits.toLocaleString()}명</b>
              <span className="wp">전주 {week.prev.visits.toLocaleString()}명</span>
            </div>
            <div>
              <span className="wl">첫 방문</span>
              <b>{week.cur.firsts.toLocaleString()}명</b>
              <span className="wp">전주 {week.prev.firsts.toLocaleString()}명</span>
            </div>
            <div>
              <span className="wl">매출</span>
              <b>{won(week.cur.revenue)}</b>
              <span className="wp">전주 {won(week.prev.revenue)}</span>
            </div>
          </div>
          <a href="#bookings" className="li li-link">
            <div className="bd">
              <div className="nm">앞으로 7일 예약 {active}건</div>
              <div className="sub">손님별 지난 시술·메모를 아래에 모았어요</div>
            </div>
            {arrow}
          </a>
          <Link href="/alerts" className="li li-link">
            <div className="bd">
              <div className="nm">챙길 고객 {careCount.toLocaleString()}명</div>
              <div className="sub">
                {careQuiet ? `최근 연락한 ${careQuiet}명은 잠시 빠져 있어요` : '재방문 시기가 됐거나 오래 안 오신 분이에요'}
              </div>
            </div>
            {arrow}
          </Link>
          <Link href="/stats" className="li li-link">
            <div className="bd">
              <div className="nm">기록 · 통계</div>
              <div className="sub">이번 달 매출 · 재방문율 · 요일별 방문</div>
            </div>
            {arrow}
          </Link>
        </div>

        {/* 예약 브리핑 — 손님이 오기 전에 카르테를 하나씩 열지 않아도 되게. 예약은 수집 시점에 묶인
            자료라 기준을 밝힌다. */}
        <div className="card bf" id="bookings" style={{ scrollMarginTop: 12 }}>
          <div className="ch">예약 브리핑 · 앞으로 7일</div>
          <div className="csub">{bookingBasis}</div>
          {days.length ? (
            days.map((d) => (
              <div key={d.date}>
                <div className="bf-day">{dayHead(d.date, today)}</div>
                {d.items.map((b) => (
                  <BriefRow key={b.id} b={b} />
                ))}
              </div>
            ))
          ) : (
            <Empty
              title="앞으로 7일 잡힌 예약이 없어요"
              hint="수집 시점 이후에 들어온 예약은 다음 수집 때 반영돼요."
            />
          )}
          {later.length ? (
            <details className="moreh">
              <summary>그 뒤 예약 {laterActive}건 더 보기</summary>
              {later.map((b) => (
                <LaterRow key={b.id} b={b} />
              ))}
            </details>
          ) : null}
        </div>

        <p className="note">
          고객 데이터는 매주 한 번 갱신돼요. 이름을 누르면 고객 카르테로 이동하고,
          이름은 테넌트별 키로 암호화 저장되어 이 화면에서만 복호화됩니다.
        </p>
      </div>
    </main>
  );
}

/** 예약 한 건 + 브리핑. 연결된 손님 기록이 있으면 누르면 카르테로 간다. */
function BriefRow({ b }: { b: Brief }) {
  const inner = (
    <>
      <div className="av">{b.name.charAt(0)}</div>
      <div className="bd">
        <div className="nm" style={b.off ? { textDecoration: 'line-through' } : undefined}>
          {b.name} 님
          {b.off ? <span className="tag-off">{offWord(b.status)}</span> : b.tag ? <span className="tag-new">{b.tag}</span> : null}
        </div>
        <div className="sub">{b.service ?? ''}</div>
        {b.gap || b.last ? (
          <div className="bf-f">
            {b.gap ? <span className={b.gap.late ? 'late' : undefined}>{b.gap.text}</span> : null}
            {b.gap && b.last ? ' · ' : null}
            {b.last ? `지난번 ${b.last}` : null}
          </div>
        ) : null}
        {b.prefer.length || b.recent ? (
          <div className="bf-m">
            {b.prefer.length ? <div>{b.prefer.join(' · ')}</div> : null}
            {b.recent ? (
              <div className="r">
                <span className="k">최근 이야기</span>
                {b.recent}
              </div>
            ) : null}
          </div>
        ) : null}
        {b.prepaid > 0 ? (
          <div className="bf-f">
            선불 잔액 {won(b.prepaid)} <span className="dim">· 추정</span>
          </div>
        ) : null}
      </div>
      <div className="rt">{b.time ?? ''}</div>
    </>
  );
  const cls = `li${b.customer_id ? ' li-link' : ''}${b.off ? ' li-off' : ''}`;
  return b.customer_id ? (
    <Link href={`/customer/${b.customer_id}`} className={cls}>
      {inner}
    </Link>
  ) : (
    <div className={cls}>{inner}</div>
  );
}

/** 7일 뒤 예약 — 아직 준비할 때가 아니라 이름·시술·날짜만. */
function LaterRow({ b }: { b: Later }) {
  const inner = (
    <>
      <div className="av">{b.name.charAt(0)}</div>
      <div className="bd">
        <div className="nm" style={b.off ? { textDecoration: 'line-through' } : undefined}>
          {b.name} 님
          {b.off ? <span className="tag-off">{offWord(b.status)}</span> : !b.customer_id ? <span className="tag-new">첫 방문</span> : null}
        </div>
        <div className="sub">
          {b.service ?? ''}
          {b.time ? ' · ' + b.time : ''}
        </div>
      </div>
      <div className="rt">{dayLabel(b.date)}</div>
    </>
  );
  const cls = `li${b.customer_id ? ' li-link' : ''}${b.off ? ' li-off' : ''}`;
  return b.customer_id ? (
    <Link href={`/customer/${b.customer_id}`} className={cls}>
      {inner}
    </Link>
  ) : (
    <div className={cls}>{inner}</div>
  );
}
