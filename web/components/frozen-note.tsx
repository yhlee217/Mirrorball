/**
 * 멈춘 자료 안내(개선 계획 v17 P0) — lib/sync frozenNote 의 문장을 눈에 띄게 한 줄. 문장이 없으면(8일 안) 아무것도 없다.
 * small — 챙길 고객 펼친 줄 안처럼 좁은 자리.
 */
export function FrozenNote({ text, small = false }: { text: string | null; small?: boolean }) {
  if (!text) return null;
  return (
    <div className={small ? 'frozen-s' : 'frozen'} role="note">
      {text}
    </div>
  );
}
