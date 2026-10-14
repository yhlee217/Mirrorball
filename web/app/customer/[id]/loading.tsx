import { BackButton } from '@/components/back-button';
import { CardSk, Line } from '@/components/skeleton';

/** 손님 상세보기 뼈대 — '‹ 뒤로'는 처음부터 누를 수 있고, 머리말 · 한 줄 띠 · 메모 자리(components/skeleton). */
export default function Loading() {
  return (
    <main className="wrap" aria-busy="true">
      <div className="bar">
        <BackButton />
      </div>
      <div className="body skw">
        <div className="chd">
          <span className="cav" />
          <div style={{ flex: 1 }}>
            <Line w={96} h={22} />
            <Line w={60} h={18} />
            <Line w={120} h={12} />
          </div>
        </div>
        <div className="card facts">
          {[0, 1, 2, 3].map((i) => (
            <div className="fact" key={i}>
              <Line w={48} h={14} />
              <Line w={40} h={10} />
            </div>
          ))}
        </div>
        <CardSk lines={['72%', '58%', '64%']} />
        <CardSk lines={['40%', '66%']} />
      </div>
    </main>
  );
}
