export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import { BackButton } from '@/components/back-button';
import { ContactButtons } from '@/components/contact-buttons';
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
import { ScreenReady } from '@/components/screen-timer';

const BADGE: Record<string, string> = { overdue: '이탈 위험', due: '재방문 도래', hello: '첫 방문', back: '첫 방문' };

/**
 * 고객 카르테 — 화면 배치만 담당한다.
 * 무엇을 어떻게 계산하는지는 ./data, 각 카드의 표시는 ./cards 에 있다.
 * 위에서 아래로 읽으면 이 화면의 순서가 그대로 보인다.
 */
export default async function CustomerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params; // Next 15 — 주소 값도 기다려 읽는다(개선 계획 v14 P1)
  const {
    cust, name, phone, vip, avg,
    history, charges, others,
    chargedTotal, balance, pocketIds,
    familyList, nextBk, topSvc,
    vac, today,
    visitCount, lastVisit, seenLast, recentBks,
    sinceLast, next, top, recs,
    badge, draft, button,
  } = await loadCarte(id);

  return (
    <main className="wrap">
      <div className="bar">
        <BackButton />
      </div>
      <div className="body">
        <div className="chd">
          <div className="cav">{name.charAt(0)}</div>
          <div>
            <h2>
              {name} 님{vip ? <span className="tag-vip">VIP</span> : null}
              {badge ? <span className={'ctag ' + badge}>{BADGE[badge]}</span> : null}
            </h2>
            <div className="s">
              {visitCount}회{cust.total_won ? ' · 누적 ' + man(cust.total_won) : ''}
            </div>
          </div>
          {/* 챙길 고객 대상(뱃지)일 때만 '연락함'으로 남긴다 — 예약 확인 전화까지 세면 연락 효과가 부푼다.
              대상이면 챙길 고객 탭과 같은 문구 · 같은 수단(설정 '연락 버튼', v12 P1) */}
          <ContactButtons id={cust.id} phone={phone} log={!!badge} draft={draft} button={button} />
        </div>

        {/* 첫 화면에: 누구 · 지금 상태(뱃지) · 한 줄 띠 · 메모 · 추천 시술 · 다음 예약(UX 계획 v3) */}
        <FactStrip
          lastVisit={lastVisit}
          seenLast={seenLast}
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
        <HistoryCard history={history} pocketIds={pocketIds} top={topSvc} pending={recentBks} />

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
      <ScreenReady />
    </main>
  );
}
