"""시술별 표준 재관리 주기(일) — 재방문 판정에 쓰는 워커용 표.

표는 web/lib/care-cycle.json 하나다 — 웹(web/lib/care-cycle.ts)과 같은 파일을 읽어, 한쪽만 고쳐서
점검 스크립트(ux_probe)의 숫자가 화면과 어긋나는 일이 없게 한다(txkind 와 같은 방식).
분류는 '원본 POS 메뉴명'으로 한다 — 남자컷 4주 / 여자컷 8주처럼 성별·부위로 주기가 크게 갈리므로
친화명으로 바꾸기 전 이름이 필요하다. 위에서부터 먼저 매칭되는 규칙을 쓴다(복합 시술은 펌·염색이 우선).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "web" / "lib" / "care-cycle.json"
_RULES: list[dict] = json.loads(_PATH.read_text(encoding="utf-8"))["rules"]

# (정규식, 주기) — 예전 표와 같은 모양
TABLE: list[tuple[str, int]] = [(r["pattern"], r["days"]) for r in _RULES]

_COMPILED = [(re.compile(r["pattern"]), r) for r in _RULES]


def care_for(service: str | None) -> dict | None:
    """원본 메뉴명 → {cat, days, phrase, tip, keep}. 매칭 없으면 None."""
    if not service:
        return None
    for rx, rule in _COMPILED:
        if rx.search(service):
            return rule
    return None


def care_days(service: str | None) -> int | None:
    """원본 메뉴명 → 표준 관리주기(일). 매칭 없으면 None."""
    c = care_for(service)
    return c["days"] if c else None


def soonest_care(services) -> dict | None:
    """그날 받은 시술 중 주기가 가장 짧은 것(web soonestCare) — 먼저 돌아올 이유가 다음 방문을 정한다."""
    best = None
    for s in services or []:
        c = care_for(s)
        if c and (best is None or c["days"] < best["days"]):
            best = c
    return best
