import Link from 'next/link';
import { man } from '@/lib/format';
import { dayHead, recentWords } from '@/lib/briefing';
import { dayLabel, type WeekNums } from '@/lib/week';
import { Empty } from '@/components/empty';
import { Help } from '@/components/help';
import { SyncChip } from '@/components/sync-chip';
import NoShowButton from '@/components/noshow-button';

type Signals = { overdue: number; due: number };
type Synced = { label: string; daysAgo: number; date: string } | null;

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
  gap: { text: string; late: boolean } | null; // '6주 만' · 늦으면 '11주 만 · 평소 6주'
  last: string | null; // 지난번 시술
  prefer: string[]; // 매장 메모 정리 — 선호(최대 2줄)
  recent: string | null; // 매장 메모 정리 — 근황 중 가장 최근 한 줄
  prepaid: number; // 선불 잔액(추정)
  rec: { label: string; short: string } | null; // 추천 시술(lib/recommend) — 추정, 하나만. 판단은 디자이너 몫이라 옅게
  phone: string | null; // 예약 손님 번호(숫자만) — 펼친 곳의 📞(늦으시거나 시간을 바꿀 때)
};
type Later = { id: string; date: string; time: string | null; service: string | null; customer_id: string | null; status: string | null; name: string; off: boolean };
/** 오늘 시간이 지난 예약 — 오늘 카드 맨 아래에 접어 둔다(v9 P0). appNoShow = 앱에서 노쇼로 표시(되돌리기 가능) */
type Past = { id: string; time: string | null; service: string | null; customer_id: string | null; status: string | null; name: string; off: boolean; appNoShow: boolean };

const offWord = (status: string | null) => (status?.includes('노쇼') ? '노쇼' : '취소');
const TAG = { '첫 방문': '첫 방문', '두 번째 방문': '두 번째' } as const;

/**
 * 홈 — 열자마자 '오늘 누가 오나'가 보이게(UX 계획 v3 §4). 머리말은 한 줄, 그 아래 오늘 예약,
 * 숫자 띠(지난주 + 연락할 분), 이번 주 나머지. 설명은 ? 안에.
 */
export default function HomeView({
  designer,
  synced,
  today,
  signals,
  week,
  careCount,
  careQuiet,
  careNew = 0,
  briefs,
  later,
  past = [],
}: {
  designer: string;
  synced: Synced;
  today: string; // KST — 오늘·내일 머리말
  signals: Signals;
  // 지난 한 주와 그 전주(lib/week.ts). work = 두 주에 영업한 날 — 휴무를 정했을 때만(lib/offdays.ts)
  week: { label: string; cur: WeekNums; prev: WeekNums; work: { cur: number; prev: number } | null };
  careCount: number; // '할 일' 수 — 챙길 고객 탭과 같은 기준(최근 연락한 분 제외)
  careQuiet: number; // 최근 연락해서 잠시 빠진 수
  careNew?: number; // 그중 이번 주 새로 오른 분(lib/fresh) — 챙길 고객 화면 맨 위
  briefs: Brief[]; // 앞으로 7일 예약(날짜·시각 순)
  later: Later[]; // 그 뒤 예약 — 접어 둔다
  past?: Past[]; // 오늘 시간이 지난 예약 — 오늘 카드 맨 아래에 접어 둔다
}) {
  const todays = briefs.filter((b) => b.date === today);
  const rest = briefs.filter((b) => b.date !== today);
  const count = (xs: { off: boolean }[]) => xs.filter((b) => !b.off).length;

  // 이번 주 나머지는 날짜별로 묶는다(이미 날짜·시각 순)
  const days: { date: string; items: Brief[] }[] = [];
  for (const b of rest) {
    const cur = days[days.length - 1];
    if (cur && cur.date === b.date) cur.items.push(b);
    else days.push({ date: b.date, items: [b] });
  }

  return (
    <main className="wrap">
      <div className="body">
        <div className="top">
          <b>{designer}</b>
          <SyncChip synced={synced} />
          <Link href="/settings" className="gear" aria-label="설정" title="설정">⚙</Link>
        </div>

        <div className="sect-h">
          오늘 <span className="sect-n">{dayLabel(today)} · {count(todays) + count(past)}명</span>
        </div>
        <div className="card bf">
          {todays.length ? (
            todays.map((b) => <BookRow key={b.id} b={b} today={today} />)
          ) : (
            <Empty title={past.length ? '남은 예약 없음' : '오늘 예약 없음'} />
          )}
          {past.length ? <PastToday rows={past} /> : null}
        </div>

        {/* 통계 입구는 '지난주' 제목 오른쪽 — 숫자를 보다가 더 보고 싶을 때 닿는 자리. 할 일 알약 끝에 붙여 두면
            폰 폭에서 혼자 다음 줄로 떨어져 작은 버튼처럼 보였다 */}
        <div className="sect-h">
          지난주 <span className="sect-n">{week.label}{week.work ? ` · 영업 ${week.work.cur}일` : ''}</span>
          <Link href="/stats" className="sect-a">통계 ›</Link>
        </div>
        <div className="card strip">
          <Help>
            지난주 = 마지막 수집일 전날까지 7일이에요(수집 안 된 날이 섞이지 않게). 방문은 시술을 받은 횟수,
            매출은 선불 잔액으로 낸 금액을 뺀 실매출이고, ▲▼는 그 전주와 견준 값이에요.
            {week.work ? ` 영업한 날은 지난주 ${week.work.cur}일 · 그 전주 ${week.work.prev}일이에요.` : ''}
            {' '}챙길 고객은 재방문 시기가 됐거나 오래 안 오신 분, 그리고 첫 방문 뒤 안부·다시 오실 때인 분이에요
            {careQuiet ? ` — 최근 연락한 ${careQuiet}명은 2주 동안 빠져 있어요` : ''}.
            {careNew ? ' 새로는 지난주 수집 땐 없었는데 이번에 오른 분이에요 — 챙길 고객 맨 위에 모여 있어요.' : ''}
          </Help>
          <div className="strip-r">
            <Num label="방문" v={week.cur.visits} prev={week.prev.visits} />
            <Num label="첫 방문" v={week.cur.firsts} prev={week.prev.firsts} />
            <Num label="매출" v={week.cur.revenue} prev={week.prev.revenue} money />
          </div>
          <div className="strip-l fill">
            <Link href="/alerts" className="pill main">
              챙길 고객 <b>{careCount.toLocaleString()}</b>
              {careNew ? <span className="pill-new">새로 <b>{careNew.toLocaleString()}</b></span> : null}
            </Link>
            <div className="pill-2">
              <Link href="/customers?filter=overdue" className="pill">이탈 위험 <b>{signals.overdue.toLocaleString()}</b></Link>
              <Link href="/customers?filter=due" className="pill">재방문 도래 <b>{signals.due.toLocaleString()}</b></Link>
            </div>
          </div>
        </div>

        {days.length ? (
          <>
            <div className="sect-h">
              이번 주 <span className="sect-n">{count(rest)}명</span>
            </div>
            <div className="card bf" id="bookings">
              {days.map((d) => (
                <div key={d.date}>
                  <div className="bf-day">{dayHead(d.date, today)}</div>
                  {d.items.map((b) => (
                    <BookRow key={b.id} b={b} today={today} />
                  ))}
                </div>
              ))}
            </div>
          </>
        ) : null}

        {later.length ? (
          <details className="card moreh later">
            <summary>그 뒤 예약 {count(later)}건</summary>
            {later.map((b) => (
              <LaterRow key={b.id} b={b} />
            ))}
          </details>
        ) : null}
      </div>
    </main>
  );
}

/** 지난주 숫자 하나 — 숫자가 먼저, ▲▼는 전주와의 차이. */
function Num({ label, v, prev, money = false }: { label: string; v: number; prev: number; money?: boolean }) {
  const d = v - prev;
  const fmt = (n: number) => (money ? man(n) : n.toLocaleString());
  return (
    <div className="num">
      <span>{label}</span>
      <b>{fmt(v)}</b>
      <span className={d > 0 ? 'up' : d < 0 ? 'down' : undefined}>{d ? `${d > 0 ? '▲' : '▼'}${fmt(Math.abs(d))}` : '전주와 같음'}</span>
    </div>
  );
}

/**
 * 예약 한 줄 — 시각 · 이름 · 시술, 아래 한 줄에 몇 주 만 · 지난번 · 선불. 메모·근황·추천 시술은 눌러야
 * 펼친다(첫 화면에 오늘 예약이 다 들어오게). 펼친 곳에 카르테로 가는 길.
 */
function BookRow({ b, today }: { b: Brief; today: string }) {
  const facts = [
    b.gap ? <span key="g" className={b.gap.late ? 'late' : undefined}>{b.gap.text}</span> : null,
    b.last ? `지난번 ${b.last}` : null,
    b.prepaid > 0 ? `선불 약 ${man(b.prepaid)}` : null,
  ].filter(Boolean);
  const head = (
    <div className="bk">
      <span className="bk-t">{b.time ?? ''}</span>
      <div className="bk-m">
        <div className="bk-n">
          <b style={b.off ? { textDecoration: 'line-through' } : undefined}>{b.name}</b>
          <span className="bk-s">{b.service ?? ''}</span>
          {b.off ? <span className="tag-off">{offWord(b.status)}</span> : b.tag ? <span className="tag-new">{TAG[b.tag]}</span> : null}
        </div>
        {facts.length && !b.off ? (
          <div className="bk-f">
            {facts.map((f, i) => (
              <span key={i}>
                {i ? ' · ' : ''}
                {f}
              </span>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
  const more = !b.off && (b.prefer.length > 0 || !!b.recent || !!b.rec || !!b.customer_id || !!b.phone);
  if (!more) return <div className={'li' + (b.off ? ' li-off' : '')}>{head}</div>;
  return (
    <details className="bkd">
      <summary className="li">{head}</summary>
      <div className="bk-x">
        {b.prefer.length ? <div>{b.prefer.join(' · ')}</div> : null}
        {b.recent ? <div>💬 {recentWords(b.recent, today)}</div> : null}
        {b.rec ? (
          <div className="bk-rec">
            추천 시술 <b>{b.rec.label}</b> <span className="bk-s">{b.rec.short}</span>
          </div>
        ) : null}
        <div className="bk-a">
          {b.phone ? <a href={`tel:${b.phone}`}>📞 전화</a> : null}
          {b.customer_id ? <Link href={`/customer/${b.customer_id}`}>상세보기 ›</Link> : null}
        </div>
      </div>
    </details>
  );
}

/** 이번 주 뒤 예약 — 아직 준비할 때가 아니라 날짜 · 시각 · 이름 · 시술만. */
function LaterRow({ b }: { b: Later }) {
  const inner = (
    <div className="bk">
      <span className="bk-t">{dayLabel(b.date)}</span>
      <div className="bk-m">
        <div className="bk-n">
          <b style={b.off ? { textDecoration: 'line-through' } : undefined}>{b.name}</b>
          <span className="bk-s">
            {b.service ?? ''}
            {b.time ? ' · ' + b.time : ''}
          </span>
          {b.off ? <span className="tag-off">{offWord(b.status)}</span> : !b.customer_id ? <span className="tag-new">첫 방문</span> : null}
        </div>
      </div>
    </div>
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

/**
 * 오늘 시간이 지난 예약 — 오늘 카드 맨 아래에 접어 둔다(개선 계획 v9 P0). 위는 늘 다음 손님. 펼치면 다녀가셨을 분은
 * '예약 기준'(방문 탭과 같은 뜻), 안 오셨으면 그 자리에서 [노쇼] · 잘못 눌렀으면 [되돌리기]. HandSOS 의 취소 · 노쇼는 표시만.
 */
function PastToday({ rows }: { rows: Past[] }) {
  return (
    <details className="past-d">
      <summary>지난 예약 {rows.filter((r) => !r.off).length}명</summary>
      {rows.map((b) => {
        const struck = b.off;
        const label = b.appNoShow ? '노쇼로 표시함' : b.off ? offWord(b.status) : '예약 기준';
        return (
          <div className="li past-r" key={b.id}>
            <div className="bk">
              <span className="bk-t">{b.time ?? ''}</span>
              <div className="bk-m">
                <div className="bk-n">
                  <b style={struck ? { textDecoration: 'line-through' } : undefined}>{b.name}</b>
                  <span className="bk-s">{b.service ?? ''}</span>
                </div>
                <div className="bk-f">{label}</div>
              </div>
            </div>
            {!b.off || b.appNoShow ? <NoShowButton id={b.id} undo={b.appNoShow} /> : null}
          </div>
        );
      })}
    </details>
  );
}
