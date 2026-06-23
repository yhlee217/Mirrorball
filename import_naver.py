#!/usr/bin/env python3
"""네이버 예약 내보내기(CSV) → 원장 앱 예약 데이터로 변환.

네이버 예약 파트너센터에서 '예약자 목록'을 CSV/엑셀로 내려받아 넣으면,
컬럼 이름을 자동 인식해 정규화된 예약 목록(clients/{slug}/bookings.yaml)으로 만든다.
손님이 예약을 *만드는* 곳은 네이버 그대로 — 원장이 *보는* 데이터만 여기서 동기화.

사용법:
    python import_naver.py export.csv --slug minji
    python import_naver.py export.csv --slug minji --date 2026-06-23   # 특정일만
    → clients/minji/bookings.yaml 갱신

설계: 스크래핑/비공식 접근 없음. 파트너센터 공식 내보내기만 사용.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

import yaml

# 논리 필드 → 네이버/일반 CSV 헤더 후보 (부분 일치, 공백 무시)
COLUMN_ALIASES = {
    "date": ["예약일", "이용일", "방문일", "날짜", "예약날짜", "date"],
    "time": ["예약시간", "이용시간", "시간", "time"],
    "name": ["예약자", "예약자명", "고객명", "이름", "성함", "name"],
    "service": ["예약상품", "상품명", "상품", "서비스", "시술", "메뉴", "menu", "service"],
    "phone": ["연락처", "전화번호", "휴대폰", "휴대폰번호", "phone", "tel"],
    "status": ["예약상태", "상태", "status"],
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "")).lower()


def _read_text(path: str) -> str:
    """네이버 내보내기는 cp949/euc-kr 또는 utf-8(-sig) 가 섞여 옴. 순서대로 시도."""
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def map_columns(header: list[str]) -> dict[str, int]:
    """헤더 행 → {논리필드: 컬럼인덱스}. 부분 일치로 견고하게."""
    norm = [_norm(h) for h in header]
    mapping: dict[str, int] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for i, h in enumerate(norm):
            if any(_norm(a) in h for a in aliases):
                mapping[field] = i
                break
    return mapping


def _clean_time(v: str) -> str:
    """'오후 2:00' / '14:00:00' / '14시' → 'HH:MM' 로 최대한 정규화."""
    v = (v or "").strip()
    m = re.search(r"(\d{1,2})\s*[:시]\s*(\d{2})", v)
    if not m:
        m2 = re.search(r"(\d{1,2})\s*시", v)
        if m2:
            h = int(m2.group(1))
            if "오후" in v and h < 12:
                h += 12
            return f"{h:02d}:00"
        return v
    h, mi = int(m.group(1)), m.group(2)
    if "오후" in v and h < 12:
        h += 12
    if "오전" in v and h == 12:
        h = 0
    return f"{h:02d}:{mi}"


def _clean_date(v: str) -> str:
    """'2026. 6. 23.' / '2026-06-23(화)' → 'YYYY-MM-DD'."""
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", (v or "").strip())
    if not m:
        return (v or "").strip()
    y, mo, d = m.groups()
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def parse_csv(path: str) -> list[dict]:
    """CSV → [{date,time,name,service,phone,status}]. 취소건 제외."""
    text = _read_text(path)
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(c.strip() for c in r)]
    if not rows:
        return []
    header, body = rows[0], rows[1:]
    cmap = map_columns(header)
    if "name" not in cmap or "date" not in cmap:
        raise ValueError(
            f"필수 컬럼(예약자/예약일)을 찾지 못했습니다. 인식된 컬럼: {sorted(cmap)}\n"
            f"헤더: {header}"
        )

    out: list[dict] = []
    for r in body:
        def cell(field: str) -> str:
            i = cmap.get(field)
            return r[i].strip() if i is not None and i < len(r) else ""

        status = cell("status")
        if "취소" in status:   # 취소된 예약은 제외
            continue
        name = cell("name")
        if not name:
            continue
        out.append({
            "date": _clean_date(cell("date")),
            "time": _clean_time(cell("time")),
            "name": name,
            "service": cell("service"),
            "phone": cell("phone"),
        })
    return out


def write_bookings(slug: str, bookings: list[dict], date: str | None = None) -> Path:
    if date:
        bookings = [b for b in bookings if b["date"] == date]
    out = Path("clients") / slug / "bookings.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(bookings, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="네이버 예약 CSV → bookings.yaml")
    ap.add_argument("csv", help="네이버 예약 내보내기 CSV 경로")
    ap.add_argument("--slug", required=True, help="디자이너 slug (clients/{slug})")
    ap.add_argument("--date", help="이 날짜(YYYY-MM-DD)만 추출")
    args = ap.parse_args()

    try:
        bookings = parse_csv(args.csv)
    except Exception as exc:
        print(f"✗ {exc}")
        return 1

    out = write_bookings(args.slug, bookings, args.date)
    n = len(yaml.safe_load(out.read_text(encoding="utf-8")) or [])
    print(f"✓ {out}  (예약 {n}건{' · ' + args.date if args.date else ''})")
    print("  연락처(phone)는 원장 로컬에만 — 배포물엔 build_app 이 제외합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
