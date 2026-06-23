#!/usr/bin/env python3
"""시술별 애프터케어 팁 — 방문 후 고객에게 보낼 관리 안내(결정적).

고객 카르테에서 '마지막 시술'에 맞는 관리 팁을 띄워, 디자이너가 그대로/수정해
직접 보낼 수 있게 한다. 자동 발송 아님 — 디자이너 손에서.
"""

from __future__ import annotations

# 시술 키워드 → 관리 팁 (구체적·실용적, 과장 없음)
_TIPS = [
    (("펌", "perm", "볼륨"),
     ["첫 24~48시간은 감거나 꽉 묶지 마세요 (컬이 자리잡는 시간)",
      "전용 펌 샴푸·트리트먼트로 컬을 더 오래 유지",
      "드라이는 디퓨저로 가볍게, 비비지 말고 쥐어짜듯"]),
    (("발레아주", "컬러", "염색", "톤", "색"),
     ["첫 2~3일은 약산성 샴푸로 색 빠짐 최소화",
      "너무 뜨거운 물·잦은 샴푸는 탈색을 촉진해요",
      "자외선·수영장 염소는 변색 원인 — 외출 시 주의"]),
    (("클리닉", "트리트먼트", "케어"),
     ["3~4일은 강한 세정 대신 영양을 유지해 주세요",
      "고데기·드라이는 온도를 한 단계 낮춰서"]),
    (("컷", "커트", "단발", "숏"),
     ["2~3주에 한 번 끝 정리하면 라인이 오래가요",
      "드라이 방향만 잡아줘도 모양이 살아요"]),
]


def tips_for(service: str | None) -> list[str]:
    s = service or ""
    for keys, tips in _TIPS:
        if any(k in s for k in keys):
            return tips
    return ["가벼운 관리로도 스타일이 오래 유지돼요. 궁금한 점은 편하게 물어보세요!"]


def message_for(name: str | None, service: str | None) -> str:
    """팁을 한 통의 메시지 초안으로."""
    tips = tips_for(service)
    head = f"{name}님, 오늘 {service} 예쁘게 잘 나왔어요! " if service else f"{name}님, 오늘 시술 잘 나왔어요! "
    body = " ".join(f"· {t}" for t in tips)
    return head + "집에서 이렇게 관리하면 더 오래가요 — " + body
