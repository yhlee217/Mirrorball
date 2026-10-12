import type { ReactNode } from 'react';

/**
 * `?` 설명 — 계산 방법·근거처럼 매번 읽을 필요는 없는 글을 접어 둔다(UX 계획 v3 §2).
 * 지우지 않고 숨긴다 — 처음 쓰는 분이 찾을 수 있게. details 라 JS 가 필요 없다.
 * 기본은 카드 오른쪽 위 구석의 ?(카드 안 아무 곳에 두면 된다), 펼치면 둔 자리에 설명이 열린다.
 * inline 이면 글 바로 옆에 ?. inset 은 안쪽 여백이 없는 목록 카드용.
 */
export function Help({ children, inline = false, inset = false }: { children: ReactNode; inline?: boolean; inset?: boolean }) {
  return (
    <details className={'help' + (inline ? ' inl' : '')}>
      <summary aria-label="설명 보기">?</summary>
      <div className={'help-b' + (inset ? ' inset' : '')}>{children}</div>
    </details>
  );
}
