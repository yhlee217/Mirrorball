#!/usr/bin/env python3
"""추천 문구(초안) 생성 — 키 없이 동작하는 결정적 엔진.

"오늘 챙길 고객"의 한마디 초안을 고객 데이터로 채운다. *자동 발송이 아니라*
디자이너가 그대로/수정해서 직접 보내는 출발점. KB(kb/knowledge.yaml) 원칙 반영:
  · revisit_anchor   유지기간을 구체적으로 언급해 다음 방문을 각인
  · expectation_reset 과장 없이, 부담 없는 권유
  · no_medical_overclaim 의료·효과 과장 금지
  · personal_consult 개인 취향(prefer)·이력을 살려 '나를 기억한다' 느낌

LLM(copygen.py) 은 선택적 고급 패스 — 이 모듈은 항상 작동하는 기본값.
"""

from __future__ import annotations

import re
from datetime import date, datetime

import copydata


def _batchim(s: str) -> bool:
    """한글 마지막 글자에 받침이 있으면 True ('이에요/예요' 선택용)."""
    s = str(s or "")
    if not s:
        return False
    c = ord(s[-1])
    if c < 0xAC00 or c > 0xD7A3:
        return False
    return (c - 0xAC00) % 28 != 0


def greeting(salon: str = "", designer: str = "") -> str:
    """'안녕하세요 살롱톤 하예원이에요! ' — 살롱·디자이너 데이터로 구성(업종 무관)."""
    head = "안녕하세요"
    if salon:
        head += " " + salon
    if designer:
        head += " " + designer + ("이에요" if _batchim(designer) else "예요")
    return head + "! "


_CUT_RE = re.compile(r"[가-힣A-Za-z0-9]*컷")


def _msg_svc(s: str | None) -> str:
    """문구용 시술명 정리: 여자컷·남자컷 등 → '커트', 중복(커트·커트) 제거."""
    out: list[str] = []
    for x in str(s or "").split(" · "):
        x = _CUT_RE.sub("커트", x).strip()
        if x and x not in out:
            out.append(x)
    return " · ".join(out)


def _pd(v):
    if v is None:
        return None
    if isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _latest_service(cust: dict) -> tuple[str | None, date | None]:
    best_d, best_s = None, None
    for h in cust.get("history", []) or []:
        d = _pd(h.get("date"))
        if d and (best_d is None or d > best_d):
            best_d, best_s = d, h.get("service")
    return best_s, best_d


def _months_ago(d: date | None, today: date) -> int | None:
    if not d:
        return None
    return max(1, round((today - d).days / 30))


def _benefit(service: str | None) -> str:
    """시술 키워드 → 재방문 권유 이유. 데이터는 kb/copy.yaml(copydata)."""
    s = service or ""
    cfg = copydata.benefit()
    for rule in cfg.get("rules", []) or []:
        if any(k in s for k in rule.get("keywords", []) or []):
            return rule.get("text", "")
    return cfg.get("default", "")


def draft_bday(cust: dict) -> str:
    name = cust.get("name") or "고객"
    prefer = cust.get("prefer") or []
    tail = (f"{prefer[0]} 느낌으로 기분 전환도 좋아요. 편하게 들러주세요!"
            if prefer else "머리도 기분도 새롭게 하고 싶으시면 편하게 들러주세요!")
    return f"{name}님 생일 축하드려요 :) {tail}"


def draft_revisit(cust: dict, today: date) -> str:
    name = cust.get("name") or "고객"
    service, last = _latest_service(cust)
    m = _months_ago(last, today)
    lead = (f"{name}님 {_msg_svc(service)} 하신 지 {m}개월쯤 됐네요. "
            if service and m else f"{name}님, 오랜만이에요. ")
    return lead + _benefit(service) + " 시간 되실 때 편하게 들러주세요!"


def draft_atrisk(cust: dict, today: date) -> str:
    name = cust.get("name") or "고객"
    service, last = _latest_service(cust)
    m = _months_ago(last, today)
    lead = (f"{name}님, {_msg_svc(service)} 하신 지 {m}개월쯤 됐어요. 그동안 잘 지내셨어요? "
            if service and m else f"{name}님, 오랜만이에요, 잘 지내셨어요? ")
    return lead + _benefit(service) + " 편하실 때 한번 들러주세요!"


def draft_for(kind: str, cust: dict, today: date | None = None,
              salon: str = "", designer: str = "") -> str:
    today = today or date.today()
    g = greeting(salon, designer)
    if kind == "bday":
        return g + draft_bday(cust)
    if kind == "atrisk":
        return g + draft_atrisk(cust, today)
    if kind == "revisit":
        return g + draft_revisit(cust, today)
    # season 등 기타
    name = cust.get("name") or "고객"
    return g + f"{name}님, 시즌 바뀌는데 가볍게 정리 어떠세요? 편하게 들러주세요!"
