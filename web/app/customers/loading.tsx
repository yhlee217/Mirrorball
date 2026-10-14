import { Block, RowSk } from '@/components/skeleton';

/** 고객 목록 뼈대 — 제목 '고객', 찾기 줄 · 조건 칩 · 목록 줄 자리(components/skeleton). */
export default function Loading() {
  return (
    <main className="wrap" aria-busy="true">
      <div className="bar">
        <div className="ttl">고객</div>
      </div>
      <div className="body skw">
        <div className="sbar">
          <Block w="auto" h={44} style={{ flex: 1 }} />
          <Block w={104} h={44} />
        </div>
        <div className="fchips">
          {[70, 82, 46, 46, 56].map((w, i) => (
            <Block key={i} w={w} h={36} r={20} />
          ))}
        </div>
        <div className="card">
          {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
            <RowSk key={i} i={i} tag />
          ))}
        </div>
      </div>
    </main>
  );
}
