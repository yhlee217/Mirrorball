import Link from 'next/link';
import { won } from '@/lib/format';
import PocketToggle from './pocket-toggle';
import type { Carte } from './data';

/**
 * 카르테를 이루는 카드들.
 *
 * page.tsx 가 화면 개요로 읽히도록 표시 덩어리를 여기로 옮겼다.
 * 보일지 말지(빈 목록이면 숨김)는 각 카드가 스스로 정한다 — 호출부에 조건이 흩어지면
 * 화면 순서를 바꿀 때 조건까지 따라다녀야 한다.
 */

/**
 * 흩어진 매장 메모를 맥 배치가 정리해 둔 것(customers.memo_ai).
 * 화면에서는 AI 를 부르지 않고 저장분만 읽는다. 방문마다 흩어진 메모를
 * '이 고객이 누구인지'로 바꿔 맨 위에 둔다.
 */
export function MemoAiCard({ cust }: { cust: Carte['cust'] }) {
  if (!cust.memo_ai && !cust.memo_ai_recent) return null;
  return (
    <div className="card memo-ai">
      <div className="ch" style={{ padding: 0, marginBottom: 6 }}>
        한눈에 <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: 10 }}>· 매장 메모 정리</span>
      </div>
      {(cust.memo_ai ?? '').split('\n').filter(Boolean).map((line, i) => (
        <div className="ai-line" key={i}>{line.replace(/^-\s*/, '')}</div>
      ))}
      {/* 근황은 시술 지침이 아니라 '다음에 먼저 꺼낼 이야기'라 따로 묶는다. */}
      {cust.memo_ai_recent ? (
        <div className="ai-recent">
          <div className="ai-rh">최근 이야기</div>
          {cust.memo_ai_recent.split('\n').filter(Boolean).map((line, i) => (
            <div className="ai-line" key={i}>{line.replace(/^-\s*/, '')}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/**
 * 같은 tenant 안의 가족만 보인다 — 담당 디자이너가 다른 가족원은 다른 tenant 라
 * 여기 안 나온다(멀티테넌트 격리 유지).
 */
export function FamilyCard({ list }: { list: Carte['familyList'] }) {
  if (!list.length) return null;
  return (
    <div className="card">
      <div className="ch">가족 · {list.length}명</div>
      {list.map((m) => (
        <Link key={m.id} href={`/customer/${m.id}`} className="li li-link">
          <div className="av">{m.name.charAt(0)}</div>
          <div className="bd">
            <div className="nm">
              {m.name} 님{m.vip ? <span className="tag-vip">VIP</span> : null}
            </div>
            <div className="sub">
              {m.visit_count}회{m.last_visit ? ' · 최근 ' + m.last_visit : ''}
            </div>
          </div>
          <span className="rt" style={{ fontSize: 18, color: '#B4B2A9' }} aria-hidden>
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
        {bk.date}
        {bk.time ? ' ' + bk.time : ''}
        {bk.service ? ' · ' + bk.service : ''}
      </div>
      {bk.note ? (
        <div style={{ fontSize: 13, color: 'var(--accent)', marginTop: 5 }}>“{bk.note}”</div>
      ) : null}
    </div>
  );
}

export function TopServicesCard({ top }: { top: Carte['topSvc'] }) {
  if (!top.length) return null;
  return (
    <div className="card" style={{ padding: '13px 15px' }}>
      <div className="ch" style={{ padding: 0, marginBottom: 8 }}>자주 받는 시술</div>
      <div className="tags">
        {top.map(([s, n]) => (
          <span key={s} className="tagr">
            {s} <b>{n}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

/** 선불 충전 — 잔액은 추정이라 근거를 함께 밝힌다. */
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
      <div className="ch" style={{ padding: 0, marginBottom: 6 }}>
        선불 충전 <span style={{ fontWeight: 400, color: 'var(--muted)', fontSize: 10 }}>· 잔액은 추정</span>
      </div>
      <div className="prepaid">
        <div><span className="pl">충전 합계</span><b>{won(chargedTotal)}</b></div>
        <div><span className="pl">추정 잔액</span><b className={balance > 0 ? 'pos' : ''}>{won(balance)}</b></div>
      </div>
      {charges.map((h) => (
        <div className="memo-row" key={h.id}>
          <span className="memo-date">{h.date.replace(/-/g, '.')}</span>
          <span>{won(h.amount_won)} 충전</span>
        </div>
      ))}
      <p className="note">
        결제수단이 기록되지 않아 <b>충전 이후 시술은 잔액에서 쓴 것으로 추정</b>합니다(기본값).
        따로 결제한 시술은 아래 이력에서 <b>&lsquo;잔액 차감&rsquo;</b>을 눌러 <b>&lsquo;사비 결제&rsquo;</b>로 바꿔주세요.
        {balance === 0 && chargedTotal > 0 ? ' 잔액이 0이면 그 뒤 시술은 사비로 계산됩니다.' : ''}
      </p>
    </div>
  );
}

/** 시술 이력 — 충전 이력이 있는 고객에게만 '사비 결제' 토글을 붙인다. */
export function HistoryCard({
  history,
  hasCharges,
}: {
  history: Carte['history'];
  hasCharges: boolean;
}) {
  return (
    <div className="card">
      <div className="ch">시술 이력{history.length ? ' · ' + history.length + '건' : ''}</div>
      {history.length ? (
        history.map((h) => (
          <div className="li" key={h.id} style={{ alignItems: 'flex-start' }}>
            <div className="bd">
              <div className="nm" style={{ fontWeight: 600 }}>{h.service ?? '시술'}</div>
              <div className="sub">
                {h.date}
                {h.time ? ' ' + h.time : ''}
              </div>
              {h.memo ? <div className="tip">{h.memo}</div> : null}
            </div>
            <div className="rt">
              {won(h.amount_won)}
              {/* 충전 이력이 있는 고객만 — 없으면 어차피 전부 사비라 물을 이유가 없다 */}
              {hasCharges ? (
                <div style={{ marginTop: 4 }}>
                  <PocketToggle id={h.id} initial={!!h.paid_out_of_pocket} />
                </div>
              ) : null}
            </div>
          </div>
        ))
      ) : (
        <div className="empty">시술 이력이 없어요</div>
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
          <span className="memo-date">{h.date.slice(5).replace('-', '.')}</span>
          <span>{h.service ?? '기타'} · {won(h.amount_won)}</span>
        </div>
      ))}
    </div>
  );
}
