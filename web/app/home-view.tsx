import Link from 'next/link';

type Booking = { id: string; date: string; time: string | null; service: string | null; customer_id: string | null; status: string | null; name?: string };
type Care = { id: string; name: string; state: string; visit_count: number; last_visit: string | null };
type Signals = { overdue: number; due: number; new: number; vip: number };

const STATE_LABEL: Record<string, string> = { overdue: '이탈 위험', due: '재방문 도래' };

export default function HomeView({
  designer,
  totalCustomers,
  recentVisits,
  signals,
  care,
  bookings,
}: {
  designer: string;
  totalCustomers: number;
  recentVisits: number; // 방문 관리 화면과 같은 최근 14일 기준
  signals: Signals;
  care: Care[];
  bookings: Booking[];
}) {
  const careCount = signals.overdue + signals.due;
  const nameOf = (b: Booking) => b.name || '고객';
  // 취소·노쇼도 '그 시간이 비었다'는 정보라 목록엔 보여주되, 개수에는 넣지 않는다.
  const isOff = (b: Booking) => !!b.status && /취소|노쇼/.test(b.status);
  const activeBk = bookings.filter((b) => !isOff(b)).length;
  const monthsAgo = (d: string | null) => (d ? Math.max(1, Math.round((Date.now() - new Date(d).getTime()) / 2592000000)) : null);

  return (
    <main className="wrap">
      <div className="body">
        <div className="hello">
          <div className="e">
            <span>For the Designer</span>
            <Link href="/settings" className="gear" aria-label="설정" title="설정">⚙</Link>
          </div>
          <h2>{designer}님, 안녕하세요 👋</h2>
          <div className="s">
            챙길 고객 {careCount} · 다가오는 예약 {activeBk} · 전체 {totalCustomers}명
          </div>
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

        <div className="chips">
          <Link href="/alerts" className="chip" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="nnum">{careCount}</div>
            <div className="l">챙길 고객 ›</div>
          </Link>
          <a href="#bookings" className="chip" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="nnum">{activeBk}</div>
            <div className="l">다가오는 예약 ›</div>
          </a>
          <Link href="/visits" className="chip" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="nnum">{recentVisits}</div>
            <div className="l">방문 관리 ›</div>
          </Link>
          <Link href="/stats" className="chip chip-flat" style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="l">기록 · 통계 ›</div>
          </Link>
        </div>

        <div className="card" id="bookings" style={{ scrollMarginTop: 12 }}>
          <div className="ch">다가오는 예약</div>
          {bookings.length ? (
            bookings.map((b) => {
              const label = nameOf(b);
              const off = isOff(b);
              const inner = (
                <>
                  <div className="av">{label.charAt(0)}</div>
                  <div className="bd">
                    <div className="nm" style={off ? { textDecoration: 'line-through' } : undefined}>
                      {label} 님
                      {off ? (
                        <span className="tag-off">{b.status?.includes('노쇼') ? '노쇼' : '취소'}</span>
                      ) : !b.customer_id ? (
                        <span className="tag-new">신규</span>
                      ) : null}
                    </div>
                    <div className="sub">
                      {b.service ?? ''}
                      {b.time ? ' · ' + b.time : ''}
                    </div>
                  </div>
                  <div className="rt">{b.date}</div>
                </>
              );
              const cls = `li${b.customer_id ? ' li-link' : ''}${off ? ' li-off' : ''}`;
              return b.customer_id ? (
                <Link key={b.id} href={`/customer/${b.customer_id}`} className={cls}>
                  {inner}
                </Link>
              ) : (
                <div className={cls} key={b.id}>
                  {inner}
                </div>
              );
            })
          ) : (
            <div className="empty">다가오는 예약이 없어요</div>
          )}
        </div>

        <div className="card">
          <div className="ch">오늘 챙길 고객</div>
          {care.length ? (
            care.map((c) => (
              <Link key={c.id} href={`/customer/${c.id}`} className="li li-link">
                <div className="av">{c.name.charAt(0)}</div>
                <div className="bd">
                  <div className="nm">{c.name} 님</div>
                  <div className="sub">
                    {c.visit_count}회{c.last_visit ? ' · 마지막 ' + c.last_visit : ''}
                  </div>
                </div>
                <div className="rt">
                  {STATE_LABEL[c.state] ?? ''}
                  {c.state === 'overdue' && c.last_visit ? ` (${monthsAgo(c.last_visit)}개월 미방문)` : ''}
                </div>
              </Link>
            ))
          ) : (
            <div className="empty">지금 챙길 고객이 없어요</div>
          )}
        </div>

        <p className="note">
          이름을 누르면 고객 카르테로 이동해요. 이름은 테넌트별 키로 암호화 저장되고 이 화면에서만 복호화됩니다.
        </p>
      </div>
    </main>
  );
}
