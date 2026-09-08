"""시술명으로 고객 성별을 추정한다 — 판정 규칙 한 곳.

HandSOS 메뉴에 '남자컷/여자컷/주니어컷'처럼 성별·연령이 박혀 있어 단서가 된다.
다만 **결제자와 시술받은 사람이 다를 수 있다**(엄마가 아들 커트를 결제, 부부 대행결제).
그래서 한 건만 보고 단정하지 않고, 그 고객의 이력 전체 분포로 판단한다:

    남성형만 나옴      → 남성
    여성형만 나옴      → 여성
    둘 다 섞여 나옴    → 불명(대행결제 의심) — 통계에서 빼는 편이 정직하다
    아동·주니어형 있음 → 자녀 동반/대행 신호(성별과 별개로 표시)

care-cycle.ts 가 관리주기용으로 쓰는 것과 같은 어휘를 쓴다.
"""

from __future__ import annotations

import re
from collections import Counter

RE_KID = re.compile(r"(?:주니어|학생|아동|어린이)\s*(?:컷|커트)")
RE_MALE = re.compile(r"(?:남자|남성)\s*(?:컷|커트|펌|파마|염색)|남자|남성")
RE_FEMALE = re.compile(r"(?:여자|여성)\s*(?:컷|커트|펌|파마|염색)|여자|여성")


def service_gender(service: str | None) -> str | None:
    """한 시술명의 성별 단서. 'M' | 'F' | 'K'(아동·주니어) | None."""
    s = service or ""
    if RE_KID.search(s):
        return "K"
    m, f = bool(RE_MALE.search(s)), bool(RE_FEMALE.search(s))
    if m and not f:
        return "M"
    if f and not m:
        return "F"
    return None          # 단서 없음, 또는 한 메뉴에 둘 다(모호)


def infer(services: list[str | None]) -> dict:
    """고객 한 명의 시술 이력 → 성별 추정.

    반환: {gender: 'M'|'F'|None, mixed: bool, kid: bool, counts: {...}, clues: int}
      gender 가 None 이면 '모름' — 단서가 없거나(clues=0) 섞여서(mixed) 판단 불가.
    """
    c = Counter(g for g in (service_gender(s) for s in services) if g)
    m, f, k = c.get("M", 0), c.get("F", 0), c.get("K", 0)
    mixed = m > 0 and f > 0
    gender = None if mixed else ("M" if m else ("F" if f else None))
    return {
        "gender": gender,
        "mixed": mixed,          # 남·여가 함께 → 대행결제 의심
        "kid": k > 0,            # 아동·주니어 시술 이력 → 자녀 결제
        "counts": {"M": m, "F": f, "K": k},
        "clues": m + f + k,
    }
