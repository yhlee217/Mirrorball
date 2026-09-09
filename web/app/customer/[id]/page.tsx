export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { won } from '@/lib/format';
import GenderPicker from './gender-picker';
import CustomerNote from './customer-note';
import ChurnToggle from './churn-toggle';
import { loadCarte } from './data';
import {
  MemoAiCard,
  FamilyCard,
  NextBookingCard,
  TopServicesCard,
  PrepaidCard,
  HistoryCard,
  OtherItemsCard,
} from './cards';

const SIGNAL: Record<string, string> = { overdue: '이탈 위험', due: '재방문 도래', new: '신규' };

/**
 * 고객 카르테 — 화면 배치만 담당한다.
 * 무엇을 어떻게 계산하는지는 ./data, 각 카드의 표시는 ./cards 에 있다.
 * 위에서 아래로 읽으면 이 화면의 순서가 그대로 보인다.
 */
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

        <MemoAiCard cust={cust} />

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

        <div className="stat-grid">
          <div className="stat"><div className="sn">{cust.visit_count}</div><div className="sl">방문</div></div>
          <div className="stat"><div className="sn">{won(cust.total_won)}</div><div className="sl">누적 매출</div></div>
          <div className="stat"><div className="sn">{won(avg)}</div><div className="sl">객단가</div></div>
          <div className="stat"><div className="sn">{cust.revisit_cycle_days ? cust.revisit_cycle_days + '일' : '-'}</div><div className="sl">재방문 주기</div></div>
        </div>

        {/* 손님 앞에서 먼저 필요한 것: 다음에 언제 오시는지 → 지난번에 뭘 했는지 */}
        <NextBookingCard bk={nextBk} />
        <HistoryCard history={history} hasCharges={charges.length > 0} />

        <CustomerNote id={cust.id} initMemo={cust.memo ?? ''} initTags={cust.prefer_tags ?? []} />

        <TopServicesCard top={topSvc} />
        <FamilyCard list={familyList} />
        <PrepaidCard charges={charges} chargedTotal={chargedTotal} balance={balance} />
        <OtherItemsCard items={others} />

        {/* 관리 — 응대 중에는 쓸 일이 없는 것들. 위쪽 자리를 차지하면 정작 필요한 게 밀린다. */}
        <div className="admin-sec">
          <div className="admin-h">관리</div>
          <GenderPicker
            id={cust.id}
            manual={cust.gender_manual === 'M' || cust.gender_manual === 'F' ? cust.gender_manual : null}
            inferred={cust.gender === 'M' || cust.gender === 'F' ? cust.gender : null}
          />
          <ChurnToggle id={cust.id} churnedAt={cust.churned_at} />
        </div>
      </div>
    </main>
  );
}
