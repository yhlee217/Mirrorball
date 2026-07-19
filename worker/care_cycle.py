"""시술별 표준 재관리 주기(일) — 재방문 판정(due/overdue)에 쓰는 워커용 표.

web/lib/care-cycle.ts 와 같은 규칙이다(둘 다 고칠 것). 분류는 '원본 POS 메뉴명'으로 한다 —
남자컷 4주 / 여자컷 8주처럼 성별·부위로 주기가 크게 갈리므로 친화명으로 바꾸기 전 이름이 필요하다.
위에서부터 먼저 매칭되는 규칙을 쓴다(복합 시술은 펌·염색이 우선).
"""
from __future__ import annotations

import re

TABLE: list[tuple[str, int]] = [
    (r"뿌리\s*(?:볼륨)?\s*펌", 70),                      # 펌인데 '뿌리'에 먼저 걸리지 않도록 위에
    (r"뿌리|새치", 35),
    (r"다운펌", 56),
    (r"매직|셋팅|디지털|볼륨|웨이브|펌", 90),
    (r"염색|컬러|이노아|탈색|블리치|하이라이트|톤다운|톤업", 56),   # '염색클리닉'은 염색으로
    (r"클리닉|트리트|케어|앰플|두피|스켈프", 28),
    (r"앞머리\s*(?:컷|커트)", 21),
    (r"(?:주니어|학생|아동|어린이)\s*(?:컷|커트)", 28),
    (r"(?:남자|남성)\s*(?:컷|커트)", 28),
    (r"(?:여자|여성)\s*(?:컷|커트)", 56),
    (r"컷|커트", 35),
]

_COMPILED = [(re.compile(p), d) for p, d in TABLE]


def care_days(service: str | None) -> int | None:
    """원본 메뉴명 → 표준 관리주기(일). 매칭 없으면 None."""
    if not service:
        return None
    for rx, days in _COMPILED:
        if rx.search(service):
            return days
    return None
