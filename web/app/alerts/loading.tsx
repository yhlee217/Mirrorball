import { SkeletonSeen } from '@/components/screen-timer';
import { Block, Line } from '@/components/skeleton';

/** 챙길 고객 뼈대 — 제목은 처음부터 '챙길 고객', 한 줄에 한 분 + [문자][전화] 자리(components/skeleton). */
export default function Loading() {
  return (
    <main className="wrap" aria-busy="true">
      <SkeletonSeen />
      <div className="bar">
        <div className="ttl">챙길 고객</div>
      </div>
      <div className="body skw">
        <Line w={190} h={11} style={{ margin: '4px 2px 14px' }} />
        <div className="card">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <div className="crow" key={i}>
              <div className="crow-r">
                <div className="crow-m">
                  <Line w={[110, 96, 124, 88][i % 4]} h={15} />
                  <Line w={[150, 170, 136, 160][i % 4]} h={10} />
                </div>
                <Block w={66} h={44} r={22} />
                <Block w={44} h={44} r={22} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
