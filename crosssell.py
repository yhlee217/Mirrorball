#!/usr/bin/env python3
"""교차판매 규칙 — 단일 소스(파이썬·테스트됨). 앱 JS 는 이 결과를 렌더만 한다.

기존엔 규칙이 앱 JS 에만 있어 pytest 가 매출엔진 핵심을 검증 못 했다(드리프트 위험).
build_app 이 고객 카드에 `crosssell` 로 실어 보내고, JS 는 카드에 값이 있으면 그대로 사용
(없는 옛 JSON 은 JS 폴백 계산 — 하위호환).

규칙(우선순위): 반복염색+클리닉0 > 컷만 > 펌+클리닉0 > 4회+옵션0. 방문 2회 미만은 제안 없음.
"""

from __future__ import annotations

import re

# 시술 카테고리(교차판매·분석용) — JS catOf 와 동일 계약
_PERM = re.compile(r"펌|아이롱|셋팅|매직")
_COLOR = re.compile(r"염색|이노아|새치|탈색")
_CLINIC = re.compile(r"클리닉|트리트|두피")
_OPTION = re.compile(r"추가|기장")


def cat_of(s: str) -> str:
    s = s or ""
    if "컷" in s:
        return "컷"
    if _PERM.search(s):
        return "펌"
    if _COLOR.search(s):
        return "염색"
    if _CLINIC.search(s):
        return "클리닉"
    if _OPTION.search(s):
        return "옵션"
    return "기타"


def crosssell_for(cust: dict) -> dict | None:
    """고객 카드 → 가장 강한 교차판매 제안 1개(없으면 None). 결정적."""
    hist = cust.get("history") or []
    v = cust.get("loyalty_visits") or len(hist)
    if v < 2:
        return None
    cnt = {"컷": 0, "펌": 0, "염색": 0, "클리닉": 0, "옵션": 0, "기타": 0}
    color_days = set()
    for h in hist:
        for s in str(h.get("service") or "").split(" · "):
            k = cat_of(s)
            cnt[k] += 1
            if k == "염색" and h.get("date"):
                color_days.add(h["date"])
    nm = cust.get("name") or "고객"

    if len(color_days) >= 2 and cnt["클리닉"] == 0:
        return {"id": "color_care", "label": "염색 주기 · 손상케어 제안",
                "copy": f"{nm}님, 염색 주기 꾸준히 잘 지키고 계세요! 반복 염색은 끝 손상이 쌓이기 쉬워서, "
                        "다음 염색 때 트리트먼트 한 번 같이 하면 색 빠짐도 늦춰지고 머릿결도 부드러워져요."}
    if cnt["컷"] >= 1 and cnt["펌"] == 0 and cnt["염색"] == 0 and cnt["클리닉"] == 0:
        return {"id": "cut_only", "label": "컷만 · 염색/펌 제안",
                "copy": f"{nm}님, 컷 라인은 늘 깔끔하게 잘 유지하세요! 분위기 살짝 바꿔보고 싶으시면 "
                        "가벼운 염색이나 다운펌도 잘 어울리실 거예요. 부담 없이 상담만 받아보세요!"}
    if cnt["펌"] >= 1 and cnt["클리닉"] == 0:
        return {"id": "perm_clinic", "label": "펌 모발 · 클리닉 제안",
                "copy": f"{nm}님, 펌 모양 예쁘게 나오고 있죠? 펌한 모발은 속건조가 와서 컬이 늘어지기 쉬워요. "
                        "다음에 트리트먼트 한 번 같이 하면 컬 탄력이랑 윤기가 훨씬 오래 가요!"}
    if v >= 4 and cnt["옵션"] == 0:
        return {"id": "upsell", "label": "단골 · 부가 케어 업셀",
                "copy": f"{nm}님, 늘 찾아주셔서 감사해요! 다음 방문 때 두피 스케일링이나 끝 케어 한 가지만 "
                        "곁들이면 스타일 유지력이 확 올라가요. 추천드려볼게요!"}
    return None
