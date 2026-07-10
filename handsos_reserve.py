#!/usr/bin/env python3
"""핸드SOS 예약 목록(reserveList.asp) 파싱 → 다가오는 예약(bookings.yaml).

reserveList 화면의 예약 행(strHowCateg=RESERVE)에서 예약시각·이름·전화·담당·시술을 뽑아,
담당(디자이너) 필터 + 상태(예약중) + 오늘 이후만 남겨 clients/{slug}/bookings.yaml 로 저장한다.
build_app.resolve_bookings 가 이 파일을 읽어 앱 '다가오는 예약' 에 띄운다.

수집(브라우저 로그인·로드)은 handsos_sync 가, 파싱은 여기(순수 함수 — 테스트 가능)가 담당한다.
행 셀 구조(진단 확인, 2026-07): [.., 예약시각, .., .., 상태, 매출입력, 이름, 전화, 담당+시술, ..]
  예: '26-07-10 금 19:30' | '예약중' | '강유신' | '010-…' | '하예원. … 예약시술메뉴 : 남자컷(부원장) : 28,000원'
"""

from __future__ import annotations

import re
from pathlib import Path

_RESERVE = "strHowCateg=RESERVE"
_WHEN = re.compile(r"(\d{2})-(\d{1,2})-(\d{1,2})\D+?(\d{1,2}):(\d{2})")
_PHONE = re.compile(r"01\d[-\s]?\d{3,4}[-\s]?\d{4}")
_SVC = re.compile(r"예약시술메뉴\s*[:：]\s*(.+?)(?:\s*[:：]\s*[\d,]+\s*원|$)")
_STAFF = re.compile(r"^\s*([^.\s]+)\s*\.")          # 상세 셀 앞머리 '하예원.' → 하예원
_STATUS = re.compile(r"예약중|예약완료|방문완료|취소|노쇼|대기")


def _clean(x: str) -> str:
    t = re.sub(r"<[^>]+>", " ", x or "").replace("&nbsp;", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def extract_rows(html: str) -> list[list[str]]:
    """reserveList HTML → 예약 행(RESERVE 링크 포함)들의 셀 텍스트 배열."""
    out: list[list[str]] = []
    for tr in re.findall(r"<tr\b.*?</tr>", html or "", re.S):
        if _RESERVE not in tr:
            continue
        cells = [_clean(td) for td in re.findall(r"<td\b[^>]*>(.*?)</td>", tr, re.S)]
        if cells:
            out.append(cells)
    return out


def parse_when(s: str):
    """'26-07-10 금 19:30' → ('2026-07-10', '19:30'). 실패 시 None."""
    m = _WHEN.search(s or "")
    if not m:
        return None
    yy, mm, dd, hh, mi = m.groups()
    return f"20{int(yy):02d}-{int(mm):02d}-{int(dd):02d}", f"{int(hh):02d}:{mi}"


def parse_detail(s: str):
    """상세 셀 → (staff, service). '하예원. … 예약시술메뉴 : 남자컷(부원장) : 28,000원'."""
    s = _clean(s)
    st = _STAFF.match(s)
    staff = st.group(1) if st else ""
    sv = _SVC.search(s)
    return staff, (_clean(sv.group(1)) if sv else "")


def parse_row(cells: list[str]) -> dict | None:
    """예약 행 셀 → {date,time,name,phone,staff,service,status,detail}. 예약시각 없으면 None."""
    cells = [_clean(c) for c in cells]
    when = next((w for w in (parse_when(c) for c in cells) if w), None)
    if not when:
        return None
    date_s, time_s = when
    pidx = next((i for i, c in enumerate(cells) if _PHONE.search(c)), -1)
    phone = re.sub(r"\D", "", _PHONE.search(cells[pidx]).group(0)) if pidx >= 0 else ""
    name = cells[pidx - 1] if pidx > 0 else ""
    status = next((c for c in cells if _STATUS.search(c) and not parse_when(c)), "")
    detail = next((c for c in cells if "예약시술메뉴" in c), "") or (max(cells, key=len) if cells else "")
    staff, service = parse_detail(detail)
    return {"date": date_s, "time": time_s, "name": name, "phone": phone,
            "staff": staff, "service": service, "status": _clean(status), "detail": detail}


def build_bookings(rows: list[dict], staff: str | None, today: str) -> list[dict]:
    """파싱 예약 → 담당 필터 + 예약중 + 오늘 이후 → [{name,phone,service,time,date}] (날짜·시간순)."""
    out = []
    for r in rows:
        if not r:
            continue
        if staff and staff not in (r.get("detail") or "") and staff not in (r.get("staff") or ""):
            continue                                       # 담당(디자이너) 필터 — 상세셀 부분매칭
        if r.get("status") and "예약중" not in r["status"]:
            continue                                       # 취소·노쇼·완료 제외
        if r["date"] < today:
            continue                                       # 오늘 이후만(다가오는 예약)
        out.append({"name": r["name"], "phone": r["phone"], "service": r["service"],
                    "time": r["time"], "date": r["date"]})
    out.sort(key=lambda b: (b["date"], b["time"]))
    return out


def harvest_bookings(html: str, staff: str | None, today: str) -> list[dict]:
    """reserveList HTML → bookings 리스트(담당·예약중·오늘 이후)."""
    parsed = [parse_row(c) for c in extract_rows(html)]
    return build_bookings([p for p in parsed if p], staff, today)


def write_bookings(client_dir, bookings: list[dict]) -> str:
    """clients/{slug}/bookings.yaml 로 저장(build_app.resolve_bookings 가 읽음)."""
    import yaml
    p = Path(client_dir) / "bookings.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(bookings, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(p)
