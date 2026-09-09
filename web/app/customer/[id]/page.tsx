export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { won } from '@/lib/format';
import PocketToggle from './pocket-toggle';
import GenderPicker from './gender-picker';
import CustomerNote from './customer-note';
import ChurnToggle from './churn-toggle';
import { loadCarte } from './data';

const SIGNAL: Record<string, string> = { overdue: '이탈 위험', due: '재방문 도래', new: '신규' };

// 화면 배치만 담당한다 — 무엇을 어떻게 계산하는지는 ./data 에 있다.
export default async function CustomerPage({ params }: { params: { id: string } }) {
  const {
    cust, name, vip, avg,
    history, charges, others,
    chargedTotal, balance,
    familyList, nextBk, topSvc,
    overdue, due, reason,
  } = await loadCarte(params.id);

  return (
    <main className="wrap">
      <div className="bar">
        <Link href="/" className="back">‹ 홈</Link>
      </div>
      <div className="body">
        <div className="chd">
          <div className="cav">{name.charAt(0)}</div>
          <div>
            <h2>
              {name} 님{vip ? <span className="tag-vip">VIP</span> : null}
            </h2>
            <div className="s">
              {cust.visit_count}회 방문{cust.total_won ? ' · 누적 ' + won(cust.total_won) : ''}
            </div>
          </div>
        </div>

        {/* 매장 메모를 맥에서 배치로 정리해 둔 것(customers.memo_ai). 화면에서는 AI 를 부르지 않는다.
            방문마다 흩어진 메모를 이 고객이 누구인지로 바꿔 맨 위에 둔다. */}
        {cust.memo_ai || cust.memo_ai_recent ? (
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
        ) : null}

        {/* 이탈로 표시한 고객은 '이탈 위험' 추정을 띄우지 않는다 — 이미 확정된 걸 재촉하는 꼴이라. */}
        {!cust.churned_at && (overdue || due) && (
          <div className={'signal-card ' + (overdue ? 'x' : 'd')}>
            <div className="sig-t">{SIGNAL[cust.revisit_state as string]}</div>
            <div className="sig-w">
              {reason}
              {cust.revisit_cycle_days ? ` · 평소 ${cust.revisit_cycle_days}일 주기` : ''}
            </div>
          </div>
        )}

        <ChurnToggle id={cust.id} churnedAt={cust.churned_at} />

        {/* 시술명 추정이 못 가른 고객을 사람이 채운다. 저장은 gender_manual 로 가서
            주간 재계산에 덮이지 않는다. */}
        <GenderPicker
          id={cust.id}
          manual={cust.gender_manual === 'M' || cust.gender_manual === 'F' ? cust.gender_manual : null}
          inferred={cust.gender === 'M' || cust.gender === 'F' ? cust.gender : null}
        />

        <div className="stat-grid">
          <div className="stat"><div className="sn">{cust.visit_count}</div><div className="sl">방문</div></div>
          <div className="stat"><div className="sn">{won(cust.total_won)}</div><div className="sl">누적 매출</div></div>
          <div className="stat"><div className="sn">{won(avg)}</div><div className="sl">객단가</div></div>
          <div className="stat"><div className="sn">{cust.revisit_cycle_days ? cust.revisit_cycle_days + '일' : '-'}</div><div className="sl">재방문 주기</div></div>
        </div>

        {familyList.length > 0 && (
          <div className="card">
            <div className="ch">가족 · {familyList.length}명</div>
            {familyList.map((m) => (
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
        )}

        {nextBk && (
          <div className="card" style={{ padding: '13px 15px' }}>
            <div className="ch" style={{ padding: 0, marginBottom: 6 }}>다음 예약</div>
            <div className="set-row">
              {nextBk.date}
              {nextBk.time ? ' ' + nextBk.time : ''}
              {nextBk.service ? ' · ' + nextBk.service : ''}
            </div>
            {nextBk.note ? (
              <div style={{ fontSize: 13, color: 'var(--accent)', marginTop: 5 }}>“{nextBk.note}”</div>
            ) : null}
          </div>
        )}

        <CustomerNote id={cust.id} initMemo={cust.memo ?? ''} initTags={cust.prefer_tags ?? []} />

        {topSvc.length > 0 && (
          <div className="card" style={{ padding: '13px 15px' }}>
            <div className="ch" style={{ padding: 0, marginBottom: 8 }}>자주 받는 시술</div>
            <div className="tags">
              {topSvc.map(([s, n]) => (
                <span key={s} className="tagr">
                  {s} <b>{n}</b>
                </span>
              ))}
            </div>
          </div>
        )}

        {charges.length > 0 && (
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
        )}

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
                  {charges.length > 0 ? (
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

        {others.length > 0 && (
          <div className="card" style={{ padding: '13px 15px' }}>
            <div className="ch" style={{ padding: 0, marginBottom: 6 }}>제품 · 기타</div>
            {others.map((h) => (
              <div className="memo-row" key={h.id}>
                <span className="memo-date">{h.date.slice(5).replace('-', '.')}</span>
                <span>{h.service ?? '기타'} · {won(h.amount_won)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
