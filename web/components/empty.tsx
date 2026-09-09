import type { ReactNode } from 'react';

/**
 * 빈 상태 — 화면마다 제각각이던 한 줄짜리 "…없어요"를 한 곳으로 모은다.
 *
 * 빈 화면은 뜻이 셋인데 생김새가 전부 같아서 구분이 안 됐다.
 *   1. 정말 없다 — 그리고 그게 좋은 소식이다(챙길 고객 0명)
 *   2. 필터가 다 걸러냈다 — 손잡이는 화면 위에 있는데 빈칸만 보여 막다른 길처럼 느껴진다
 *   3. 아직 수집 전이다 — 주 1회 수집이라 '없음'과 '아직'은 다른 말이다
 *
 * 그래서 한 줄이 아니라 세 자리를 둔다.
 *   title  무엇이 비었는가            (항상)
 *   hint   왜 비었는가 / 언제 채워지는가 (거의 항상 — 위 셋을 가르는 자리)
 *   action 여기서 뭘 하면 되는가       (막다른 길일 때만)
 */
export function Empty({
  title,
  hint,
  action,
}: {
  title: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-t">{title}</div>
      {hint ? <div className="empty-h">{hint}</div> : null}
      {action ? <div className="empty-a">{action}</div> : null}
    </div>
  );
}
