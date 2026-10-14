import Link from 'next/link';
import { Block, Line } from '@/components/skeleton';

/**
 * 홈 뼈대 — 앱을 처음 열 때도 이것이 먼저 보인다. 머리말 · 오늘 · 지난주가 실제 홈과 같은 자리(components/skeleton).
 * 다른 화면은 각자 loading.tsx 가 있다(이 뼈대가 다른 화면에 뜨지 않게 — 로그인 · 공개 소개 포함).
 */
export default function Loading() {
  return (
    <main className="wrap" aria-busy="true">
      <div className="body">
        <div className="top">
          <Line w={58} h={17} />
          <Link href="/settings" className="gear" aria-label="설정" title="설정">⚙</Link>
        </div>
        <div className="sect-h">오늘</div>
        <div className="card bf skw">
          {[0, 1, 2].map((i) => (
            <div className="li" key={i}>
              <div className="bk">
                <Line w={36} h={13} style={{ marginTop: 3 }} />
                <div className="bk-m" style={{ padding: '3px 0 4px' }}>
                  <Line w={[96, 84, 104][i]} h={15} />
                  <Line w={[180, 150, 196][i]} h={11} />
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="sect-h">
          지난주
          <Link href="/stats" className="sect-a">통계 ›</Link>
        </div>
        <div className="card strip skw">
          <div className="strip-r">
            {[0, 1, 2].map((i) => (
              <div className="num" key={i}>
                <Line w={30} h={11} />
                <Line w={46} h={21} />
                <Line w={26} h={11} />
              </div>
            ))}
          </div>
          <div className="strip-l" style={{ flexWrap: 'nowrap' }}>
            {[0, 1, 2].map((i) => (
              <Block key={i} w="auto" h={40} r={20} style={{ flex: 1 }} />
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
