import { SkeletonSeen } from '@/components/screen-timer';
import { BackButton } from '@/components/back-button';
import { Block, Line } from '@/components/skeleton';

/** 설정 뼈대 — '‹ 뒤로 설정', 입력 카드 자리(components/skeleton). */
export default function Loading() {
  return (
    <main className="wrap" aria-busy="true">
      <SkeletonSeen />
      <div className="bar">
        <BackButton />
        <div className="ttl" style={{ marginLeft: 10 }}>설정</div>
      </div>
      <div className="body skw">
        {[0, 1, 2].map((c) => (
          <div className="card" key={c} style={{ padding: '14px 15px' }}>
            <Line w={64} h={11} style={{ marginBottom: 14 }} />
            {[0, 1].map((i) => (
              <div key={i} style={{ marginBottom: i ? 0 : 14 }}>
                <Line w={80} h={11} style={{ marginBottom: 8 }} />
                <Block w="100%" h={46} />
              </div>
            ))}
          </div>
        ))}
      </div>
    </main>
  );
}
