import LogoutButton from './logout-button';

type Booking = { id: string; date: string; time: string | null; service: string | null; customer_id: string | null };
type Customer = { id: string; revisit_state: string | null; tier: string | null; visit_count: number };

export default function HomeView({
  salon,
  bookings,
  customers,
}: {
  salon: string;
  bookings: Booking[];
  customers: Customer[];
}) {
  const n = { overdue: 0, due: 0, new: 0, vip: 0 };
  for (const c of customers) {
    if (c.revisit_state && c.revisit_state in n) (n as Record<string, number>)[c.revisit_state]++;
    if (c.tier === 'vip') n.vip++;
  }
  const care = n.overdue + n.due;

  return (
    <main className="wrap">
      <div className="bar">
        <div className="ttl">컨시어지</div>
        <LogoutButton />
      </div>
      <div className="body">
        <div className="hello">
          <div className="e">For the Designer</div>
          <h2>{salon}님, 안녕하세요 👋</h2>
          <div className="s">다가오는 예약 {bookings.length} · 챙길 고객 {care}</div>
        </div>

        <div className="chips">
          <div className="chip"><div className="nnum">{bookings.length}</div><div className="l">다가오는 예약</div></div>
          <div className="chip"><div className="nnum">{care}</div><div className="l">챙길 고객</div></div>
          <div className="chip"><div className="nnum">–</div><div className="l">AI 노출</div></div>
        </div>

        <div className="hsig">
          <div className="hs x"><div className="hn">{n.overdue}</div><div className="hl">이탈위험</div></div>
          <div className="hs d"><div className="hn">{n.due}</div><div className="hl">재방문도래</div></div>
          <div className="hs g"><div className="hn">{n.new}</div><div className="hl">신규</div></div>
          <div className="hs v"><div className="hn">{n.vip}</div><div className="hl">VIP</div></div>
        </div>

        <div className="card">
          <div className="ch">다가오는 예약</div>
          {bookings.length ? (
            bookings.map((b) => (
              <div className="li" key={b.id}>
                <div className="av">·</div>
                <div className="bd">
                  <div className="nm">고객</div>
                  <div className="sub">
                    {b.service ?? ''}
                    {b.time ? ' · ' + b.time : ''}
                  </div>
                </div>
                <div className="rt">{b.date}</div>
              </div>
            ))
          ) : (
            <div className="empty">다가오는 예약이 없어요</div>
          )}
        </div>

        <p className="note">
          ※ 고객 이름은 PII 라 암호화 저장(P3 복호화 연결 예정) — 현재 화면은 운영 데이터(예약·신호)만 표시합니다.
        </p>
      </div>
    </main>
  );
}
