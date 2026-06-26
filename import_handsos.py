#!/usr/bin/env python3
"""핸드SOS 매출상세목록(거래내역) → 카르테·이력·통계 부트스트랩.

핸드SOS 웹 '매출분석 → 매출상세목록' 을 엑셀/CSV 로 내보낸 파일을 넣으면,
한 줄=한 거래(시술 line)를 고객별로 묶어:
  · clients/{slug}/customers/*.yaml  (고객 마스터 + 방문 이력)
  · clients/{slug}/records.yaml       (거래 원장 → stats.py 통계)
연락처 등 PII 는 로컬 전용. 기존 카르테(메모·생일)는 보존(덮어쓰지 않음).

컬럼 자동 인식(핸드SOS 한글 헤더). 담당이 섞였으면 --staff 로 한 사람만.

사용법:
    python import_handsos.py 매출상세목록.csv --slug hayewoni
    python import_handsos.py 매출상세목록.csv --slug hayewoni --staff 하예원
    python import_handsos.py 매출상세목록.csv --slug hayewoni --dry
"""

from __future__ import annotations

import argparse
import csv
import io
import re
from collections import defaultdict
from pathlib import Path

import yaml

COLS = {
    "date": ["날짜", "일자", "매출일", "결제일"],
    "name": ["고객명", "성함", "이름", "회원명"],
    "phone": ["핸드폰", "휴대폰", "전화번호", "전화", "연락처"],
    "service": ["상세메뉴", "메뉴", "시술명", "시술"],
    "price": ["결제액", "판매가", "결제금액", "금액"],
    "staff": ["담당", "담당자"],
    "custno": ["고객번호", "회원번호"],
    "memo": ["메모", "비고", "특이사항"],
}


def _clean_name(v: str) -> str:
    """핸드SOS 고객명 칸에 툴팁이 섞여 들어온 경우 정제 ('배상웅*전화 번호:..' → '배상웅')."""
    return re.split(r"[*]|전화\s*번호|고객\s*번호", (v or "").strip(), 1)[0].strip()


# 메모에서 네이버 예약 자동문구·메뉴/가격 줄 제거 → 사람 특징 메모만 남김
_MEMO_BOILER = [
    re.compile(r"네이버\s*예약건"), re.compile(r"잔여금[^!]*현장결제할게요!?"),
    re.compile(r"N-?Pay로\s*현장결제할게요!?"), re.compile(r"미결제금액\s*[:：]\s*[\d,]+원?"),
    re.compile(r"\[네이버담당자[^\]]*\]"), re.compile(r"Pay\s*구분\s*[:：]\s*\S+"),
    re.compile(r"현장결제할게요!?"), re.compile(r"예약시술메뉴\s*[:：]"),
    re.compile(r"모발 클리닉 서비스 사용 완료"),
]
_MEMO_MENU = re.compile(r"[가-힣A-Za-z0-9()+_.&\s]*[:：]\s*[\d,\s]+\s*원")


def _clean_memo(m: str) -> str:
    m = m or ""
    for r in _MEMO_BOILER:
        m = r.sub(" ", m)
    m = _MEMO_MENU.sub(" ", m)
    m = re.sub(r"요청사항\s*[:：]", " ", m)        # 마커 제거, 내용은 유지
    m = re.sub(r"\s+", " ", m).strip(" -·:/()")
    return m if len(m) >= 2 else ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "")).lower()


def _read(path: str) -> str:
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def map_columns(header: list[str]) -> dict[str, int]:
    norm = [_norm(h) for h in header]
    out: dict[str, int] = {}
    for field, aliases in COLS.items():
        for a in aliases:
            na = _norm(a)
            hit = next((i for i, h in enumerate(norm) if na in h), None)
            if hit is not None:
                out[field] = hit
                break
    return out


def _date(v: str) -> str:
    """'26-06-26 19:41' / '2026-06-26' → 'YYYY-MM-DD'."""
    m = re.search(r"(\d{2,4})\D+(\d{1,2})\D+(\d{1,2})", v or "")
    if not m:
        return ""
    y = int(m.group(1))
    if y < 100:
        y += 2000
    return f"{y:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def _price(v: str) -> int | None:
    d = re.sub(r"[^\d]", "", v or "")
    return int(d) if d else None


_ROLE_PAREN = re.compile(r"\s*\((?:부원장|원장|실장|디자이너|점장|대표)\)\s*$")


def _service(v: str) -> str:
    return _ROLE_PAREN.sub("", (v or "").strip())


def parse_rows(path: str, staff: str | None = None) -> list[dict]:
    text = _read(path)
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        return []
    cmap = map_columns(rows[0])
    if "name" not in cmap or "date" not in cmap:
        raise ValueError(f"필수 컬럼(고객명/날짜) 인식 실패. 헤더: {rows[0]}")

    out: list[dict] = []
    last_date = ""
    for r in rows[1:]:
        def cell(f: str) -> str:
            i = cmap.get(f)
            return r[i].strip() if i is not None and i < len(r) else ""

        if staff and cmap.get("staff") is not None and staff not in cell("staff"):
            continue
        name = _clean_name(cell("name"))
        d = _date(cell("date"))
        if d:
            last_date = d
        elif name:                     # 연속행(같은 방문 추가 시술): 직전 방문 날짜 이어받기
            d = last_date
        if not name or not d:
            continue
        rec = {"date": d, "name": name, "service": _service(cell("service"))}
        ph = cell("phone")
        if ph:
            rec["phone"] = ph
        cn = re.sub(r"\D", "", cell("custno")).lstrip("0")
        if cn:
            rec["custno"] = cn
        me = _clean_memo(cell("memo"))      # 보일러플레이트·메뉴/가격 제거
        if me:
            rec["memo"] = me
        p = _price(cell("price"))
        if p is not None:
            rec["price"] = p
        out.append(rec)
    return out


def _cid(name: str, phone: str) -> str:
    base = re.sub(r"[^0-9a-zA-Z가-힣]", "", name or "")
    tail = re.sub(r"\D", "", phone or "")[-4:]
    return (base or "c") + (tail or "")


def build_customers(rows: list[dict]) -> list[dict]:
    """거래 행 → 고객 마스터. 고객번호 우선으로 묶고(없으면 이름+전화), 방문=distinct 날짜.
    시술은 날짜별로 합치고, 메모는 그 방문의 notes 로."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        cn = (r.get("custno") or "").strip()
        ph = re.sub(r"\D", "", r.get("phone", ""))
        key = ("no:" + cn) if cn else ("np:" + r["name"] + "|" + ph)
        groups[key].append(r)

    customers = []
    for recs in groups.values():
        name = recs[0]["name"]
        phone = next((r.get("phone") for r in recs if r.get("phone")), "")
        custno = next((r.get("custno") for r in recs if r.get("custno")), "")
        svc: dict[str, list[str]] = defaultdict(list)
        notes: dict[str, list[str]] = defaultdict(list)
        for r in recs:
            if r.get("service"):
                svc[r["date"]].append(r["service"])
            if r.get("memo"):
                notes[r["date"]].append(r["memo"])
        dates = sorted(set(svc) | set(notes))
        history = []
        for d in dates:
            h = {"date": d, "service": " · ".join(dict.fromkeys(svc.get(d, []))) or None}
            note = " / ".join(dict.fromkeys(notes.get(d, [])))
            if note:
                h["notes"] = note
            history.append(h)
        cust: dict = {
            "id": (f"c{custno}" if custno else _cid(name, phone)),
            "name": name,
            "loyalty_visits": len(dates),
        }
        if phone:
            cust["contact"] = phone
        if custno:
            cust["custno"] = custno
        if dates:
            cust["first_visit"] = dates[0]
        if history:
            cust["history"] = list(reversed(history))   # 최근이 위로
        customers.append(cust)
    return customers


def write_out(slug: str, rows: list[dict], customers: list[dict]) -> tuple[int, int]:
    base = Path("clients") / slug
    (base / "customers").mkdir(parents=True, exist_ok=True)
    # 거래 원장(통계용)
    (base / "records.yaml").write_text(
        yaml.safe_dump(rows, allow_unicode=True, sort_keys=False), encoding="utf-8")
    # 고객 마스터(기존 보존)
    n = 0
    for c in customers:
        p = base / "customers" / f"{c['id']}.yaml"
        if p.exists():
            continue
        p.write_text(yaml.safe_dump(c, allow_unicode=True, sort_keys=False), encoding="utf-8")
        n += 1
    return len(rows), n


def main() -> int:
    ap = argparse.ArgumentParser(description="핸드SOS 매출상세목록 → 카르테·통계")
    ap.add_argument("csv")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--staff", help="이 담당자 행만 (예: 하예원)")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    try:
        rows = parse_rows(args.csv, staff=args.staff)
    except Exception as exc:
        print(f"✗ {exc}")
        return 1
    customers = build_customers(rows)
    print(f"거래 {len(rows)}건 → 고객 {len(customers)}명"
          + (f" (담당={args.staff})" if args.staff else ""))
    for c in sorted(customers, key=lambda x: -x["loyalty_visits"])[:5]:
        print(f"  · {c['name']} (방문 {c['loyalty_visits']}회, 최근 {c['history'][0]['service']})")
    if args.dry:
        print("(--dry: 저장 안 함)")
        return 0
    nr, nc = write_out(args.slug, rows, customers)
    print(f"✓ records.yaml {nr}건 · 신규 고객 {nc}명 저장(기존 보존). 연락처는 로컬 전용.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
