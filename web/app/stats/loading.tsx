import { SkeletonSeen } from '@/components/screen-timer';
import { BackButton } from '@/components/back-button';
import { Block, CardSk, Line } from '@/components/skeleton';

/** 통계 뼈대 — '‹ 뒤로 통계', 맨 위 요약 카드 · 아래 카드 자리(components/skeleton). */
export default function Loading() {
  return (
    <main className="wrap" aria-busy="true">
      <SkeletonSeen />
      <div className="bar">
        <BackButton />
        <div className="ttl" style={{ marginLeft: 10 }}>통계</div>
      </div>
      <div className="body skw">
        <div className="card strip">
          <Line w={150} h={12} style={{ marginBottom: 12 }} />
          {[0, 1].map((r) => (
            <div className="strip-r" key={r} style={{ marginTop: r ? 14 : 0 }}>
              {[0, 1, 2].map((i) => (
                <div className="num" key={i}>
                  <Line w={36} h={11} />
                  <Line w={58} h={21} />
                  <Line w={44} h={11} />
                </div>
              ))}
            </div>
          ))}
          <div className="strip-l" style={{ flexWrap: 'nowrap' }}>
            {[0, 1, 2].map((i) => (
              <Block key={i} w="auto" h={40} r={20} style={{ flex: 1 }} />
            ))}
          </div>
        </div>
        <CardSk lines={['86%', '78%', '82%', '70%']} />
      </div>
    </main>
  );
}
