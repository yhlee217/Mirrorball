import Link from 'next/link';
import { man, price, won } from '@/lib/format';
import { recentWords } from '@/lib/briefing';
import { agoWords, dayLabel, daysBetween, shortDate, spanWords } from '@/lib/week';
import PocketToggle from './pocket-toggle';
import { Empty } from '@/components/empty';
import { Help } from '@/components/help';
import type { Carte } from './data';

/**
 * 카르테를 이루는 카드들.
 *
 * page.tsx 가 화면 개요로 읽히도록 표시 덩어리를 여기로 옮겼다.
 * 보일지 말지(빈 목록이면 숨김)는 각 카드가 스스로 정한다 — 호출부에 조건이 흩어지면
 * 화면 순서를 바꿀 때 조건까지 따라다녀야 한다.
 * 글은 조각으로, 설명은 ? 안에(UX 계획 v3).
 */

/** 줄 앞의 '- ' 를 뗀 줄들. */
const lines = (text: string | null) => (text ?? '').split('\n').map((l) => l.replace(/^-\s*/, '').trim()).filter(Boolean);

/**
 * 흩어진 매장 메모를 맥 배치가 정리해 둔 것(customers.memo_ai). 화면에서는 AI 를 부르지 않고
 * 저장분만 읽는다. 근황은 시술 지침이 아니라 '다음에 먼저 꺼낼 이야기'라 따로 묶는다.
 */
export function MemoAiCard({ cust, today }: { cust: Carte['cust']; today: string }) {
  if (!cust.memo_ai && !cust.memo_ai_recent) return null;
  return (
    <div className="card memo-ai">
      <div className="ch" style={{ padding: 0, marginBottom: 6 }}>메모</div>
      {lines(cust.memo_ai).map((line, i) => (
        <div className="ai-line" key={i}>{line}</div>
      ))}
      {cust.memo_ai_recent ? (
        <div className="ai-recent">
          <div className="ai-rh">근황</div>
          {lines(cust.memo_ai_recent).map((line, i) => (
            <div className="ai-line" key={i}>{recentWords(line, today)}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/**
 * 한 줄 띠 — 마지막 · 다음 · 선불(또는 객단가) · 매출 순위. 머리말('N회 · 누적 X')과 겹치지 않는,
 * 손님 앞에서 바로 묻게 되는 넷. 큰 타일 넷(약 200px)이던 것을 한 줄로 줄여 메모·추천 시술이 첫 화면에
 * 들어오게 했다. 다음 방문의 근거·휴가·추정은 ? 안에. 계산은 lib/carte-stats.ts.
 */
export function FactStrip({
  lastVisit,
  sinceLast,
  next,
  prepaid,
  balance,
  avg,
  top,
  vacation,
}: {
  lastVisit: string | null;
  sinceLast: Carte['sinceLast'];
  next: Carte['next'];
  prepaid: boolean;
  balance: number;
  avg: number;
  top: Carte['top'];
  vacation: number; // 마지막 방문 뒤 디자이너 휴가 일수 — 재방문 판정에서 뺀 날
}) {
  return (
    <div className="card facts">
      <div className="fact">
        <b>{sinceLast === null ? '-' : agoWords(sinceLast)}</b>
        <span>마지막{lastVisit ? ' ' + shortDate(lastVisit) : ''}</span>
      </div>
      <NextFact next={next} />
      {prepaid ? (
        <div className="fact">
          <b>약 {man(balance)}</b>
          <span>선불 잔액</span>
        </div>
      ) : (
        <div className="fact">
          <b>{price(avg)}</b>
          <span>객단가</span>
        </div>
      )}
      <div className="fact">
        <b>{top ? `상위 ${top}%` : '-'}</b>
        <span>매출 순위</span>
      </div>
      <Help>
        {next && next.kind === 'expected' ? <>다음 방문 = {next.basis}로 본 예상일이에요. </> : null}
        {next && next.kind === 'passed' ? (
          <>지난 예약 = 마지막 수집 뒤 예약 시각이 지났어요. 다녀가셨으면 다음 수집 때 방문으로 잡히고, 그때까지는
            챙길 고객에서 빼 둬요. </>
        ) : null}
        {vacation > 0 ? <>마지막 방문 뒤 휴가 {vacation}일은 빼고 셌어요. </> : null}
        {prepaid ? <>선불 잔액은 결제수단이 기록되지 않아 충전 뒤 시술을 잔액에서 쓴 것으로 본 추정이에요. </> : null}
        매출 순위는 이 매장 손님 중 누적 매출 순서예요.
      </Help>
    </div>
  );
}

/** 다음 방문 — 잡힌 예약 > 수집 뒤 지난 예약 > 평소 주기 > 시술 기준 추정. 예상일이 지났으면 지난 만큼을 빨갛게. */
function NextFact({ next }: { next: Carte['next'] }) {
  if (!next) return <div className="fact"><b>-</b><span>다음</span></div>;
  if (next.kind === 'booked') return <div className="fact"><b>{shortDate(next.date)}</b><span>예약</span></div>;
  if (next.kind === 'passed') return <div className="fact"><b>{shortDate(next.date)}</b><span>지난 예약</span></div>;
  if (next.overdueDays > 0) {
    return (
      <div className="fact">
        <b className="late">{spanWords(next.overdueDays)} 지남</b>
        <span>예상 {shortDate(next.date)}</span>
      </div>
    );
  }
  return <div className="fact"><b>{shortDate(next.date)}쯤</b><span>다음 예상</span></div>;
}

/**
 * 추천 시술(lib/recommend) — 때가 된 시술과, 이 매장 손님들이 함께 많이 받는 것. 추정이라 판단은
 * 디자이너 몫 — 이름과 근거 한 줄만, 옅게(해야 할 일이 아니라 참고로 읽히게).
 */
export function RecommendCard({ items }: { items: Carte['recs'] }) {
  if (!items.length) return null;
  return (
    <div className="card" style={{ padding: '13px 15px' }}>
      <div className="ch" style={{ padding: 0, marginBottom: 4 }}>추천 시술</div>
      {items.map((r) => (
        <div className="rec" key={r.kind + r.label}>
          <b>{r.label}</b>
          <span className="rec-w">{r.reason}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * 같은 tenant 안의 가족만 보인다 — 담당 디자이너가 다른 가족원은 다른 tenant 라
 * 여기 안 나온다(멀티테넌트 격리 유지).
 */
export function FamilyCard({ list, today }: { list: Carte['familyList']; today: string }) {
  if (!list.length) return null;
  return (
    <div className="card">
      <div className="ch">가족 {list.length}명</div>
      {list.map((m) => (
        <Link key={m.id} href={`/customer/${m.id}`} className="li li-link">
          <div className="av">{m.name.charAt(0)}</div>
          <div className="bd">
            <div className="nm">
              {m.name}
              {m.vip ? <span className="tag-vip">VIP</span> : null}
            </div>
            <div className="sub">
              {m.visit_count}회{m.last_visit ? ' · ' + agoWords(daysBetween(m.last_visit, today)) : ''}
            </div>
          </div>
          <span className="rt" style={{ fontSize: 18 }} aria-hidden>
            ›
          </span>
        </Link>
      ))}
    </div>
  );
}

export function NextBookingCard({ bk }: { bk: Carte['nextBk'] }) {
  if (!bk) return null;
  return (
    <div className="card" style={{ padding: '13px 15px' }}>
      <div className="ch" style={{ padding: 0, marginBottom: 6 }}>다음 예약</div>
      <div className="set-row">
        {dayLabel(bk.date)}
        {bk.time ? ' ' + bk.time : ''}
        {bk.service ? ' · ' + bk.service : ''}
      </div>
      {bk.note ? (
        <div style={{ fontSize: 13, color: 'var(--accent)', marginTop: 5 }}>“{bk.note}”</div>
      ) : null}
    </div>
  );
}

/** 선불 — 충전 합계와 남은 잔액(추정), 충전 내역. 왜 추정인지·고치는 법은 ? 안에. */
export function PrepaidCard({
  charges,
  chargedTotal,
  balance,
}: {
  charges: Carte['charges'];
  chargedTotal: number;
  balance: number;
}) {
  if (!charges.length) return null;
  return (
    <div className="card" style={{ padding: '13px 15px' }}>
      <div className="ch" style={{ padding: 0, marginBottom: 6 }}>선불</div>
      <Help>
        결제수단이 기록되지 않아 충전 뒤 시술은 잔액에서 쓴 것으로 봐요(추정). 따로 결제한 시술은 시술 이력에서
        &lsquo;잔액 차감&rsquo;을 눌러 &lsquo;사비 결제&rsquo;로 바꿔 주세요.
        {balance === 0 && chargedTotal > 0 ? ' 잔액이 0이면 그 뒤 시술은 사비로 계산돼요.' : ''}
      </Help>
      <div className="prepaid">
        <div><span className="pl">충전</span><b>{man(chargedTotal)}</b></div>
        <div><span className="pl">남은 잔액</span><b className={balance > 0 ? 'pos' : ''}>약 {man(balance)}</b></div>
      </div>
      {charges.map((h) => (
        <div className="memo-row" key={h.id}>
          <span className="memo-date">{shortDate(h.date)}</span>
          <span>{man(h.amount_won)} 충전</span>
        </div>
      ))}
    </div>
  );
}

/**
 * 시술 이력 — 손님 앞에서 필요한 건 '지난번에 뭘 했나'지 전체 이력이 아니다.
 * 최근 몇 건만 펼치고 나머지는 접는다(단골은 100건이 넘어 화면이 통째로 이력이 된다).
 * 자주 받는 시술은 따로 카드로 두지 않고 머리줄 한 줄로(UX 계획 v3).
 */
const RECENT_N = 5;

function HistoryRow({ h, pocket }: { h: Carte['history'][number]; pocket: boolean }) {
  return (
    <div className="li" style={{ alignItems: 'flex-start' }}>
      <div className="bd">
        <div className="nm" style={{ fontWeight: 600 }}>{h.service ?? '시술'}</div>
        <div className="sub">{dayLabel(h.date)}</div>
        {h.memo ? <div className="tip">{h.memo}</div> : null}
      </div>
      <div className="rt">
        {man(h.amount_won)}
        {/* 잔액에서 뺀 줄(또는 사비로 고친 줄)만 — 나머지는 어차피 사비로 셈한다(data.ts pocketIds) */}
        {pocket ? (
          <div style={{ marginTop: 4 }}>
            <PocketToggle id={h.id} initial={!!h.paid_out_of_pocket} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function HistoryCard({
  history,
  pocketIds,
  top,
}: {
  history: Carte['history'];
  pocketIds: string[];
  top: Carte['topSvc'];
}) {
  const pocket = new Set(pocketIds);
  const recent = history.slice(0, RECENT_N);
  const rest = history.slice(RECENT_N);
  return (
    <div className="card">
      <div className="ch">
        시술 이력{history.length ? ` ${history.length}건` : ''}
        {top.length ? <span className="ch-n"> · {top.slice(0, 3).map(([s, n]) => `${s} ${n}`).join(' · ')}</span> : null}
      </div>
      {history.length ? (
        <>
          {recent.map((h) => (
            <HistoryRow key={h.id} h={h} pocket={pocket.has(h.id)} />
          ))}
          {rest.length > 0 && (
            <details className="moreh">
              <summary>이전 {rest.length}건</summary>
              {rest.map((h) => (
                <HistoryRow key={h.id} h={h} pocket={pocket.has(h.id)} />
              ))}
            </details>
          )}
        </>
      ) : (
        <Empty title="시술 이력이 없어요" hint="첫 방문 전이거나 아직 수집되지 않았어요." />
      )}
    </div>
  );
}

/** 제품·환불 — 시술이 아니라 이력과 섞지 않는다. */
export function OtherItemsCard({ items }: { items: Carte['others'] }) {
  if (!items.length) return null;
  return (
    <div className="card" style={{ padding: '13px 15px' }}>
      <div className="ch" style={{ padding: 0, marginBottom: 6 }}>제품 · 기타</div>
      {items.map((h) => (
        <div className="memo-row" key={h.id}>
          <span className="memo-date">{shortDate(h.date)}</span>
          <span>{h.service ?? '기타'} · {won(h.amount_won)}</span>
        </div>
      ))}
    </div>
  );
}
