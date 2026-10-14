import { SkeletonSeen } from '@/components/screen-timer';
import { Line, RowSk } from '@/components/skeleton';

/** 방문 뼈대 — 머리말 '방문 2주', 날짜 머리줄 · 방문 줄 자리(components/skeleton). */
export default function Loading() {
  return (
    <main className="wrap" aria-busy="true">
      <SkeletonSeen />
      <div className="body">
        <div className="top">
          <b>방문</b>
          <span className="sect-n">2주</span>
        </div>
        <div className="card skw">
          {[0, 1].map((d) => (
            <div key={d}>
              <div className="bf-day">
                <Line w={64} h={11} />
              </div>
              {[0, 1, 2, 3].map((i) => (
                <RowSk key={i} i={i + d} />
              ))}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
