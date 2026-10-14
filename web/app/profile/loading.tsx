import { BackButton } from '@/components/back-button';
import { Block, Line } from '@/components/skeleton';

/** 소개 편집 뼈대 — '‹ 뒤로 소개'(설정에서 들어온다), 입력 칸 자리(components/skeleton). */
export default function Loading() {
  return (
    <main className="wrap" aria-busy="true">
      <div className="bar">
        <BackButton fallback="/settings" />
        <div className="ttl" style={{ marginLeft: 10 }}>소개</div>
      </div>
      <div className="body skw">
        <div className="card" style={{ padding: '14px 15px' }}>
          {[0, 1, 2].map((i) => (
            <div key={i} style={{ marginBottom: i < 2 ? 14 : 0 }}>
              <Line w={72} h={11} style={{ marginBottom: 8 }} />
              <Block w="100%" h={i === 2 ? 96 : 46} />
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
