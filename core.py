"""빌드 코어 — render(data: dict) -> str.

입력 방식과 무관한 재사용 코어. 지금은 YAML(build.py)이 dict 를 넘기지만,
나중에 웹 폼이 같은 dict 를 넘기면 그대로 재사용된다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import schema

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "profile.html.j2"


@lru_cache(maxsize=1)
def _env():
    from jinja2 import Environment, FileSystemLoader

    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,             # 사용자 텍스트는 자동 이스케이프
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _josa_gwa(word: str) -> str:
    """마지막 글자 받침 유무로 '과'/'와' 선택."""
    if not word:
        return "와"
    last = word[-1]
    if "가" <= last <= "힣":
        return "과" if (ord(last) - 0xAC00) % 28 else "와"
    return "와"


def korean_name_plain(data: dict) -> str:
    return (data.get("korean_name") or "").replace(" ", "")


def make_title(data: dict) -> str:
    return (
        f"{korean_name_plain(data)} · {data.get('display_name','')} | "
        f"{data.get('role','')} · {data.get('salon','')}"
    )


def make_description(data: dict) -> str:
    """knows_about 를 '·'로 잇고 마지막은 과/와로 연결 + 매장·역할·이름·인스타."""
    items = list(data.get("knows_about", []))
    if not items:
        spec_part = ""
    elif len(items) == 1:
        spec_part = items[0]
    else:
        head = items[:-1]
        spec_part = "·".join(head) + _josa_gwa(head[-1]) + " " + items[-1]
    return (
        f"{spec_part}. {data.get('salon','')} {data.get('role','')} "
        f"{korean_name_plain(data)}({data.get('instagram','')})."
    )


def _dumps(obj: dict) -> str:
    # </script> 가 JSON 문자열에 섞여도 스크립트 태그가 깨지지 않게 이스케이프
    return json.dumps(obj, ensure_ascii=False, indent=2).replace("</", "<\\/")


def build_context(data: dict) -> dict:
    """템플릿에 넘길 컨텍스트 (원본 필드 + 파생 값)."""
    from markupsafe import escape

    ctx = dict(data)
    booking = (data.get("booking_url") or "").strip()
    tagline = (data.get("tagline") or "").strip()
    loc = data.get("location") or {}

    # 포트폴리오: 원본처럼 3개씩 한 행으로 (그리드 3열). 직접 이스케이프.
    labels = data.get("portfolio_labels", []) or []
    rows = [
        "".join(f"<div>{escape(l)}</div>" for l in labels[i:i + 3])
        for i in range(0, len(labels), 3)
    ]
    gallery_html = "\n      ".join(rows)

    # 후기: 평균·개수는 입력에서 파생 (중복 입력 줄이기)
    reviews = data.get("reviews") or []
    if reviews:
        stars = [int(r.get("stars") or 0) for r in reviews]
        ctx["review_avg"] = round(sum(stars) / len(stars), 1)
        ctx["review_count"] = len(reviews)

    booking_href = booking or "[예약 링크]"

    # 스타일 찾기 퀴즈: 데이터를 JSON 으로 임베드 (결과 CTA 에 예약 링크 포함)
    if data.get("style_quiz"):
        quiz_data = dict(data["style_quiz"])
        quiz_data["booking"] = booking_href
        ctx["style_quiz_json"] = _dumps(quiz_data)

    ctx.update(
        address=loc.get("address", ""),
        directions=loc.get("directions", ""),
        gallery_html=gallery_html,
        korean_name_plain=korean_name_plain(data),
        instagram_url=f"https://instagram.com/{data.get('instagram','')}",
        has_photo=bool((data.get("photo_url") or "").strip()),
        initial=(data.get("display_name") or "·")[:1].upper(),
        tagline_html="<br>".join(tagline.splitlines()),
        booking_href=booking_href,
        booking_href_loc=booking or "[네이버 예약 링크]",
        title=make_title(data),
        description=make_description(data),
        person_ld_json=_dumps(schema.person_ld(data)),
        faq_ld_json=_dumps(schema.faq_ld(data)),
    )
    return ctx


def render(data: dict) -> str:
    """data dict 를 받아 완성된 정적 HTML 문자열을 반환."""
    return _env().get_template(TEMPLATE_NAME).render(**build_context(data))
