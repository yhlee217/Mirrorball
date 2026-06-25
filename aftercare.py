#!/usr/bin/env python3
"""시술별 애프터케어 팁 — 방문 후 고객에게 보낼 관리 안내(결정적).

고객 카르테에서 '마지막 시술'에 맞는 관리 팁을 띄워, 디자이너가 그대로/수정해
직접 보낼 수 있게 한다. 자동 발송 아님 — 디자이너 손에서.
"""

from __future__ import annotations

import copydata


def tips_for(service: str | None) -> list[str]:
    s = service or ""
    cfg = copydata.aftercare()
    for rule in cfg.get("rules", []) or []:
        if any(k in s for k in rule.get("keywords", []) or []):
            return rule.get("tips", []) or []
    return cfg.get("default", []) or []


def message_for(name: str | None, service: str | None) -> str:
    """팁을 한 통의 메시지 초안으로."""
    tips = tips_for(service)
    head = f"{name}님, 오늘 {service} 예쁘게 잘 나왔어요! " if service else f"{name}님, 오늘 시술 잘 나왔어요! "
    body = " ".join(f"· {t}" for t in tips)
    return head + "집에서 이렇게 관리하면 더 오래가요 — " + body
