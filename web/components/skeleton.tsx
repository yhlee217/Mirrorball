import type { CSSProperties } from 'react';

/**
 * 화면 전환 중 뼈대 — 가는 화면과 같은 모양(제목 · 줄 모양)을 먼저 보여준다(각 화면의 loading.tsx).
 *
 * 전에는 모든 화면이 같은 '불러오는 중…' 머리줄 + 큰 회색 상자 넷이라, 옛 화면 → 상자 → 새 화면으로
 * 제목이 두 번 바뀌고 모양이 튀었다. 이제 제목은 처음부터 그 화면 것이고, 회색 줄은 실제 줄 자리에
 * 0.15초 뒤에 나타난다(.skw) — 금방 열리는 화면에선 회색이 번쩍이지 않는다.
 */

/** 글 한 줄 자리 */
export function Line({ w, h = 12, style }: { w: number | string; h?: number; style?: CSSProperties }) {
  return <span className="sk skl" style={{ width: w, height: h, ...style }} />;
}

/** 덩어리 자리(버튼 · 입력 칸 · 알약) */
export function Block({ w, h, r = 12, style }: { w: number | string; h: number; r?: number; style?: CSSProperties }) {
  return <span className="sk" style={{ display: 'block', flex: 'none', width: w, height: h, borderRadius: r, ...style }} />;
}

/** 목록 한 줄 — 동그라미 + 이름 줄 + 보조 줄(고객 목록 · 방문). i 로 길이를 조금씩 달리한다 */
export function RowSk({ i = 0, tag = false }: { i?: number; tag?: boolean }) {
  return (
    <div className="li">
      <span className="av" />
      <div className="bd">
        <Line w={[64, 52, 72, 58][i % 4]} h={14} />
        <Line w={[132, 116, 148, 124][i % 4]} h={10} />
      </div>
      {tag && i % 3 === 0 ? <Block w={60} h={20} r={20} /> : null}
    </div>
  );
}

/** 카드 안 글 줄 몇 개(메모 · 설정 · 통계 카드) */
export function CardSk({ lines, title = true }: { lines: (number | string)[]; title?: boolean }) {
  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      {title ? <Line w={72} h={11} style={{ marginBottom: 12 }} /> : null}
      {lines.map((w, i) => (
        <Line key={i} w={w} h={12} />
      ))}
    </div>
  );
}
