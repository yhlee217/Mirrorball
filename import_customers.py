#!/usr/bin/env python3
"""고객 마스터 가져오기 — 기존 CRM(핸드SOS 등)·엑셀 고객목록 → 우리 카르테.

핸드SOS·엑셀 등에서 받은 '고객 목록' CSV 를 컬럼 자동 인식으로 읽어
clients/{slug}/customers/*.yaml 로 변환한다(연락처는 로컬 전용).
어떤 export 형식이든 헤더만 맞으면 흡수 — 재입력 없이 이력 부트스트랩.

사용법:
    python import_customers.py 고객목록.csv --slug hayewoni
    python import_customers.py 고객목록.csv --slug hayewoni --dry   # 미리보기만
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

import yaml

COLUMN_ALIASES = {
    "name": ["고객명", "성함", "이름", "회원명", "name"],
    "phone": ["연락처", "전화번호", "휴대폰", "휴대폰번호", "핸드폰", "phone", "tel", "mobile"],
    "birthday": ["생일", "생년월일", "birth", "birthday"],
    "first_visit": ["첫방문", "최초방문", "등록일", "가입일", "first"],
    "last_visit": ["최근방문", "마지막방문", "최종방문", "최근방문일", "last"],
    "last_service": ["최근시술", "마지막시술", "시술명", "최근메뉴", "service", "menu"],
    "visits": ["방문횟수", "누적방문", "총방문", "방문수", "내방횟수", "visits", "count"],
    "memo": ["메모", "비고", "특이사항", "노트", "memo", "note", "비고사항"],
    "prefer": ["선호", "취향", "관심", "선호시술", "prefer"],
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "")).lower()


def _read_text(path: str) -> str:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def map_columns(header: list[str]) -> dict[str, int]:
    norm = [_norm(h) for h in header]
    mapping: dict[str, int] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for i, h in enumerate(norm):
            if any(_norm(a) in h for a in aliases):
                mapping[field] = i
                break
    return mapping


def _date(v: str) -> str:
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", (v or "").strip())
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def _md(v: str) -> str:
    """생일 → 'MM-DD'(연도 있으면 버림)."""
    v = (v or "").strip()
    m = re.search(r"(?:\d{2,4}\D+)?(\d{1,2})\D+(\d{1,2})\s*$", v)
    return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""


def _slugify(name: str, idx: int) -> str:
    base = re.sub(r"[^0-9a-zA-Z가-힣]", "", name or "")
    return base or f"c{idx}"


def parse_customers(path: str) -> list[dict]:
    text = _read_text(path)
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    cmap = map_columns(header)
    if "name" not in cmap:
        raise ValueError(f"'고객명' 컬럼을 찾지 못했습니다. 헤더: {header}")

    out: list[dict] = []
    for i, r in enumerate(body):
        def cell(f: str) -> str:
            j = cmap.get(f)
            return r[j].strip() if j is not None and j < len(r) else ""

        name = cell("name")
        if not name:
            continue
        cust: dict = {"id": _slugify(name, i), "name": name}
        if cell("phone"):
            cust["contact"] = cell("phone")
        if _md(cell("birthday")):
            cust["birthday"] = _md(cell("birthday"))
        if _date(cell("first_visit")):
            cust["first_visit"] = _date(cell("first_visit"))
        if cell("visits"):
            digits = re.sub(r"[^\d]", "", cell("visits"))
            if digits:
                cust["loyalty_visits"] = int(digits)
        if cell("memo"):
            cust["memo"] = cell("memo")
        pref = [p.strip() for p in re.split(r"[,/·]", cell("prefer")) if p.strip()]
        if pref:
            cust["prefer"] = pref
        # 최근 방문/시술 → 시술 이력 한 줄로
        lv, ls = _date(cell("last_visit")), cell("last_service")
        if lv or ls:
            cust["history"] = [{"date": lv or None, "service": ls or None}]
        out.append(cust)
    return out


def dedupe(customers: list[dict]) -> list[dict]:
    seen, out = set(), []
    for c in customers:
        key = re.sub(r"\D", "", c.get("contact", "")) or c.get("name")
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def write_customers(slug: str, customers: list[dict]) -> int:
    cdir = Path("clients") / slug / "customers"
    cdir.mkdir(parents=True, exist_ok=True)
    n = 0
    for c in customers:
        path = cdir / f"{c['id']}.yaml"
        if path.exists():           # 기존 카르테 보존(덮어쓰지 않음)
            continue
        path.write_text(yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="고객 목록 CSV → 카르테")
    ap.add_argument("csv")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dry", action="store_true", help="저장하지 않고 미리보기")
    args = ap.parse_args()

    try:
        customers = dedupe(parse_customers(args.csv))
    except Exception as exc:
        print(f"✗ {exc}")
        return 1

    print(f"인식된 고객: {len(customers)}명")
    for c in customers[:5]:
        print(f"  · {c['name']} (방문 {c.get('loyalty_visits','?')}회"
              f"{', 생일 '+c['birthday'] if c.get('birthday') else ''})")
    if len(customers) > 5:
        print(f"  … 외 {len(customers)-5}명")
    if args.dry:
        print("(--dry: 저장 안 함)")
        return 0
    n = write_customers(args.slug, customers)
    print(f"✓ clients/{args.slug}/customers/ 에 {n}명 신규 저장(기존은 보존)")
    print("  연락처(contact)는 로컬 전용 — build_app 이 배포물에서 제외합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
