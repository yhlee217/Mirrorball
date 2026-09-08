"""시술명으로 고객 성별을 추정한다 — 판정 규칙 한 곳.

HandSOS 메뉴에 '남자컷/여자컷/주니어컷'처럼 성별·연령이 박혀 있어 단서가 된다.
다만 **결제자와 시술받은 사람이 다를 수 있다**(엄마가 아들 커트를 결제, 부부 대행결제).
그래서 한 건만 보고 단정하지 않고, 그 고객의 이력 전체 분포로 판단한다:

    남성형만 나옴      → 남성
    여성형만 나옴      → 여성
    둘 다 섞여 나옴    → 불명(대행결제 의심) — 통계에서 빼는 편이 정직하다

아동·주니어형(주니어컷·학생컷)은 '자녀 결제'로 단정하면 안 된다. **그 아이 본인이 고객일 수
있다.** 그래서 성인형과 함께 나오는지, 그리고 시간 순서가 어떤지로 갈라 본다:

    아동형만                       → 본인이 아동·학생 (성별은 별개로 판단)
    아동형이 전부 성인형보다 앞섬    → 자라서 성인 메뉴로 옮긴 같은 사람
    아동형과 성인형이 뒤섞임        → 대행결제 의심 (엄마가 아이 것을 같이 결제)

care-cycle.ts 가 관리주기용으로 쓰는 것과 같은 어휘를 쓴다.
"""

from __future__ import annotations

import re
from collections import Counter

RE_KID = re.compile(r"(?:주니어|학생|아동|어린이)\s*(?:컷|커트)")

# 메모에 적힌 관계어. "남자컷" 옆에 '아드님'이 적혀 있으면 그 시술은 본인 것이 아니다.
# 남·여가 섞인 고객을 바로 버리지 않고, 이걸로 먼저 귀속을 풀어본다.
RE_FAMILY = re.compile(r"아드님|따님|아들|딸|남편|신랑|아내|와이프|집사람|어머님|아버님|"
                       r"어머니|아버지|엄마|아빠|손주|손자|손녀|조카|동생|형|누나|언니|오빠")
# 본인 성별을 거꾸로 알려주는 말(배우자 언급). '남편분과 함께' → 본인은 여성 쪽.
RE_SPOUSE_M = re.compile(r"남편|신랑")          # 배우자가 남성 → 본인 여성 추정
RE_SPOUSE_F = re.compile(r"아내|와이프|집사람")  # 배우자가 여성 → 본인 남성 추정
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


def owner_hint(memo: str | None) -> str | None:
    """이 거래가 본인 것인지 가족 것인지 메모로 짐작. 'family' | None."""
    return "family" if memo and RE_FAMILY.search(memo) else None


def spouse_hint(memos: list[str | None]) -> str | None:
    """메모 전체에서 배우자 언급으로 본인 성별을 되짚는다. 'M' | 'F' | None."""
    joined = " ".join(m for m in memos if m)
    m, f = bool(RE_SPOUSE_M.search(joined)), bool(RE_SPOUSE_F.search(joined))
    if m and not f:
        return "F"      # 남편이 있다 → 본인 여성
    if f and not m:
        return "M"      # 아내가 있다 → 본인 남성
    return None


def infer(rows: list[dict]) -> dict:
    """고객 한 명의 시술 이력 → 성별·연령대 추정.

    rows: [{"service": 시술명, "date": "YYYY-MM-DD", "memo": 매장메모}]

    바로 포기하지 않고 단계적으로 좁힌다:
      1) 메모에 가족 관계어가 있는 거래는 '가족 것'으로 보고 성별 투표에서 뺀다.
         ("남자컷 + 아드님" → 아들 것이므로 본인 성별 근거가 아니다)
      2) 남은 것으로 판정. 그래도 남·여가 섞이면 배우자 언급으로 되짚는다.
         ("남편분과 같이" → 본인 여성)
      3) 그래도 모르면 그때 제외한다(proxy=True).

    반환 {gender, age_band, proxy, resolved_by, counts, clues}
      resolved_by: 'service' | 'memo-family' | 'memo-spouse' | None — 무엇으로 갈랐는지
    """
    memos = [r.get("memo") for r in rows]

    def vote(items):
        tagged = []
        for r in items:
            g = service_gender(r.get("service"))
            if g:
                tagged.append((g, r.get("date") or ""))
        c = Counter(g for g, _ in tagged)
        return c.get("M", 0), c.get("F", 0), c.get("K", 0), tagged

    m, f, k, tagged = vote(rows)
    resolved_by = "service"

    # 1) 남·여가 섞였으면 가족 것으로 보이는 거래를 빼고 다시 센다
    if m > 0 and f > 0:
        own = [r for r in rows if owner_hint(r.get("memo")) is None]
        m2, f2, k2, tagged2 = vote(own)
        if (m2 > 0) != (f2 > 0):          # 한쪽만 남아 갈렸다
            m, f, k, tagged = m2, f2, k2, tagged2
            resolved_by = "memo-family"

    proxy = m > 0 and f > 0
    gender = None if proxy else ("M" if m else ("F" if f else None))

    # 2) 아직 섞여 있으면 배우자 언급으로 되짚는다
    if proxy:
        sp = spouse_hint(memos)
        if sp:
            gender, proxy, resolved_by = sp, False, "memo-spouse"

    age_band = None
    if k:
        adult_dates = [d for g, d in tagged if g in ("M", "F") and d]
        kid_dates = [d for g, d in tagged if g == "K" and d]
        if not (m or f):
            age_band = "kid"                     # 아동형만 — 본인이 아동·학생
        elif kid_dates and adult_dates and max(kid_dates) < min(adult_dates):
            age_band = "adult"                   # 아동 → 성인 순서: 자란 같은 사람
        elif not proxy and gender:
            age_band = "adult"                   # 메모로 갈린 경우 — 아동분은 가족 것
        else:
            proxy = True                         # 뒤섞임 — 아이 것을 같이 결제한 정황
            gender = None
    elif m or f:
        age_band = "adult"

    return {
        "gender": gender,
        "age_band": age_band,
        "proxy": proxy,
        "resolved_by": None if (proxy or not gender) else resolved_by,
        "counts": {"M": m, "F": f, "K": k},
        "clues": m + f + k,
    }
