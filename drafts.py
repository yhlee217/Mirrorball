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

from datetime import date, datetime


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


# 시술 키워드 → 재방문 권유의 '구체적 이유' (과장 없이)
_BENEFIT = [
    (("펌", "perm"), "풀리기 전에 한 번 더 잡으면 한동안 손질이 편하실 거예요"),
    (("발레아주", "컬러", "염색", "톤"), "뿌리 올라오기 전에 톤 정리하면 화사하게 유지돼요"),
    (("클리닉", "트리트먼트"), "결이 가라앉기 전에 한 번 케어하면 컨디션이 오래가요"),
    (("컷", "커트", "단발"), "라인 흐트러지기 전에 다듬으면 스타일이 오래가요"),
]


def _benefit(service: str | None) -> str:
    s = service or ""
    for keys, msg in _BENEFIT:
        if any(k in s for k in keys):
            return msg
    return "시기 맞춰 가볍게 정리하면 더 예쁘게 유지돼요"


def draft_bday(cust: dict) -> str:
    name = cust.get("name") or "고객"
    prefer = cust.get("prefer") or []
    tail = (f"{prefer[0]} 느낌으로 기분 전환도 좋아요. 편하게 연락 주세요!"
            if prefer else "머리도 기분도 새롭게 하고 싶으시면 편하게 연락 주세요!")
    return f"{name}님 생일 축하드려요 :) {tail}"


def draft_revisit(cust: dict, today: date) -> str:
    name = cust.get("name") or "고객"
    service, last = _latest_service(cust)
    m = _months_ago(last, today)
    lead = (f"{name}님 {service} 하신 지 {m}개월쯤 됐네요. "
            if service and m else f"{name}님, 오랜만이에요. ")
    return lead + _benefit(service) + " 시간 되실 때 편하게 봐요!"


def draft_for(kind: str, cust: dict, today: date | None = None) -> str:
    today = today or date.today()
    if kind == "bday":
        return draft_bday(cust)
    if kind == "revisit":
        return draft_revisit(cust, today)
    # season 등 기타
    name = cust.get("name") or "고객"
    return f"{name}님, 시즌 바뀌는데 가볍게 정리 어떠세요? 편하게 연락 주세요!"
