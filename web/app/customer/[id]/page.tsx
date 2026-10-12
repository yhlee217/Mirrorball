export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { man } from '@/lib/format';
import GenderPicker from './gender-picker';
import CustomerNote from './customer-note';
import ChurnToggle from './churn-toggle';
import { loadCarte } from './data';
import {
  MemoAiCard,
  RecommendCard,
  FactStrip,
  FamilyCard,
  NextBookingCard,
  PrepaidCard,
  HistoryCard,
  OtherItemsCard,
} from './cards';

/**
 * 고객 카르테 — 화면 배치만 담당한다.
 * 무엇을 어떻게 계산하는지는 ./data, 각 카드의 표시는 ./cards 에 있다.
 * 위에서 아래로 읽으면 이 화면의 순서가 그대로 보인다.
 */
export default async function CustomerPage({ params }: { params: { id: string } }) {
  const {
    cust, name, vip, avg,
    history, charges, others,
    chargedTotal, balance, pocketIds,
    familyList, nextBk, topSvc,
    overdue, due, vac, today,
    sinceLast, next, top, recs,
  } = await loadCarte(params.id);
  // 상태 뱃지 — 이탈로 표시한 분, 다음 예약이 잡힌 분에겐 띄우지 않는다(이미 정해졌거나 오시기로 했다)
  const badge = !cust.churned_at && !nextBk && (overdue || due) ? (overdue ? 'overdue' : 'due') : null;

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
              {badge ? <span className={'ctag ' + badge}>{badge === 'overdue' ? '이탈 위험' : '재방문 도래'}</span> : null}
            </h2>
            <div className="s">
              {cust.visit_count}회{cust.total_won ? ' · 누적 ' + man(cust.total_won) : ''}
            </div>
          </div>
        </div>

        {/* 첫 화면에: 누구 · 지금 상태(뱃지) · 한 줄 띠 · 메모 · 권할 것 · 다음 예약(UX 계획 v3) */}
        <FactStrip
          lastVisit={cust.last_visit}
          sinceLast={sinceLast}
          next={next}
          prepaid={chargedTotal > 0}
          balance={balance}
          avg={avg}
          top={top}
          vacation={badge ? vac : 0}
        />
        <MemoAiCard cust={cust} today={today} />
        <RecommendCard items={recs} />
        <NextBookingCard bk={nextBk} />
        <HistoryCard history={history} pocketIds={pocketIds} top={topSvc} />

        <CustomerNote id={cust.id} initMemo={cust.memo ?? ''} initTags={cust.prefer_tags ?? []} />

        <FamilyCard list={familyList} today={today} />
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
