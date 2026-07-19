"""HandSOS 스크레이프 — v1 handsos_sync.harvest_store 재사용 + 워커용 정규화.

컨테이너에 리포의 scripts/handsos_sync.py, scripts/handsos_harvest.js,
scripts/handsos_selectors.yaml, handsos_reserve.py 가 있어야 한다(Dockerfile 참고).
브라우저 자동화(로그인·saleList 프레임 수확·예약)는 검증된 v1을 그대로 호출하고,
여기서는 (1) 자격증명→store 구성 (2) 수확 행(9열 dict)→우리 스키마 정규화 만 담당.

반환: {"customers":[{ext_id,name,phone?,visit_count,first_visit,last_visit,total_won,revisit_cycle_days,revisit_state}],
       "transactions":[{ext_id,customer_ext,date,service,amount_won}],
       "bookings":[{ext_id,customer_ext,date,time,service}]}
PII(name/phone)는 평문 반환 → sync_tenant 가 DEK로 암호화.
"""

from __future__ import annotations

import html
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))


def _norm_date(v) -> str | None:
    if not v:
        return None
    m = re.search(r"(\d{2,4})\D(\d{1,2})\D(\d{1,2})", str(v))
    if not m:
        return None
    y, mo, d = m.groups()
    if len(y) == 2:
        y = "20" + y
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def _norm_time(v) -> str | None:
    """'26-07-19 14:30' / '14:30' → '14:30'(HH:MM). 시각이 없으면 None."""
    if not v:
        return None
    m = re.search(r"(\d{1,2}):(\d{2})", str(v))
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def _won(v) -> int:
    if v is None:
        return 0
    m = re.findall(r"-?\d+", str(v).replace(",", ""))
    return int("".join(m)) if m else 0


def _derive(dates_desc: list[str], visits: int, today: str):
    last = dates_desc[0] if dates_desc else None
    cycle = None
    if len(dates_desc) >= 2:
        ds = [datetime.fromisoformat(x) for x in dates_desc]
        gaps = sorted((ds[i] - ds[i + 1]).days for i in range(len(ds) - 1))
        m = gaps[len(gaps) // 2]
        if m > 0:
            cycle = m
    state = None
    if visits <= 1:
        state = "new"
    elif last:
        days = (datetime.fromisoformat(today) - datetime.fromisoformat(last)).days
        cyc = cycle or 42
        if days > cyc * 1.6:
            state = "overdue"
        elif days >= cyc:
            state = "due"
    return cycle, state


_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")


def _clean(s) -> str | None:
    """스크레이프 텍스트 정제 — HTML 엔티티 디코드(&lt;→<, &amp;→&, &nbsp;→공백) + 진짜 HTML
    태그(<br>, <b>, <span…>) 제거. 각괄호로 감싼 한글 홍보문구(<첫 방문…>)는 태그가 아니므로
    보존한다 — HTML 태그명은 ASCII 문자/'/'로 시작하므로 한글로 시작하는 각괄호는 미매치."""
    if not s:
        return None
    s = html.unescape(str(s))
    s = _TAG_RE.sub("", s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


_NPAY = "잔여금 N-Pay로 현장결제할게요"  # 네이버 N-Pay 자동문구(전 예약 반복) — 개별 메모 아님, 제거


def _note(detail) -> str | None:
    """예약 상세셀 → 개별 메모만. 네이버 보일러플레이트(예약건·미결제금액·네이버담당자·예약시술메뉴·
    N-Pay 자동문구·담당접두)를 제거하고 남는 자유문구(요청·시간변경·취소사유 등)만 반환."""
    base = _clean(detail)
    if not base:
        return None
    s = " " + base + " "
    req = re.search(r"요청사항\s*[:：]\s*(.+?)\s*$", s)
    req_text = req.group(1).strip() if req else ""
    s = re.sub(r"요청사항\s*[:：].*$", " ", s)
    s = re.sub(r"네이버\s*예약건", " ", s)
    s = re.sub(r"미결제금액\s*[:：]\s*[\d,]+\s*원?", " ", s)
    s = re.sub(r"\[네이버담당자[^\]]*\]", " ", s)
    s = re.sub(r"예약시술메뉴\s*[:：].*?[\d][\d,]*\s*원", " ", s)  # 서비스+가격(가격 앞 숫자 요구)
    s = re.sub(r"[가-힣A-Za-z()＋+]+\s*[:：]\s*[\d][\d,]{2,}\s*원", " ", s)  # 남은 '서비스 : 가격원'
    s = re.sub(r"잔여금\s*N-Pay로\s*현장결제할게요\s*!*", " ", s)  # N-Pay 자동문구(꼬리 ! 포함)
    s = re.sub(r"-->|상세보기", " ", s)
    s = re.sub(r"^\s*[^.\s]{1,10}\s*\.\s", " ", s)  # 담당 접두(하예원.)
    s = re.sub(r"\s+", " ", s).strip()
    if req_text and _NPAY not in req_text:
        s = (s + " · " if s else "") + "요청: " + req_text
    s = s.strip(" ·!.,")
    return s if (s and re.search(r"[가-힣0-9A-Za-z]", s)) else None


def normalize(rows: list[dict], reserve_rows: list[dict], staff: str | None = None,
              reservations_ok: bool = True) -> dict:
    """수확 행(한글 9열 dict) + 예약 행 → 스키마. 고객번호로 집계.

    reservations_ok: 예약 수확이 정상 완료됐는지(False 면 예약 delete_stale 을 스킵해
    수집 실패 시 기존 예약이 전량 삭제되는 사고를 막는다 — 코드리뷰 H1)."""
    custs: dict[str, dict] = {}
    raw_tx: list[dict] = []
    today = str(date.today())

    for r in rows:
        if staff and r.get("담당") and staff not in str(r.get("담당")):
            continue  # 테넌트=디자이너: 자기 담당 행만(라벨 상이 시 secrets 매핑으로 보정)
        ext = (r.get("고객번호") or "").strip() or (r.get("고객명") or "").strip()
        if not ext:
            continue
        name = _clean(r.get("고객명")) or ""
        d = _norm_date(r.get("날짜"))
        won = _won(r.get("결제액"))
        svc = _clean(r.get("상세메뉴"))
        memo = _note(r.get("메모"))  # 매출 메모에도 네이버 보일러플레이트가 섞여옴 → 개별 메모만 남김
        c = custs.setdefault(ext, {"ext_id": ext, "name": name, "phone": (r.get("전화번호") or "").strip() or None, "dates": set(), "total_won": 0, "memos": set()})
        if name and not c["name"]:
            c["name"] = name
        if memo:
            c["memos"].add(memo)
        if d:
            c["dates"].add(d)
        c["total_won"] += won
        raw_tx.append({"customer_ext": ext, "date": d, "time": _norm_time(r.get("시간")),
                       "service": svc, "amount_won": won})

    customers = []
    for ext, c in custs.items():
        dates = sorted(c["dates"], reverse=True)
        cycle, state = _derive(dates, len(dates), today)
        customers.append({
            "ext_id": ext, "name": c["name"] or None, "phone": c["phone"],
            "visit_count": len(dates), "first_visit": dates[-1] if dates else None,
            "last_visit": dates[0] if dates else None, "total_won": c["total_won"],
            "revisit_cycle_days": cycle, "revisit_state": state,
            "pos_note": " · ".join(sorted(c.get("memos") or []))[:1000] or None,
        })

    # 안정 키: 고객번호-날짜-당일순번. 수집 창(31일/전체)과 무관하게 같은 방문=같은 키 → 병합 정확.
    seq: dict = defaultdict(int)
    transactions = []
    for t in raw_tx:
        key = (t["customer_ext"], t["date"])
        i = seq[key]
        seq[key] += 1
        transactions.append({"ext_id": f"{t['customer_ext']}-{t['date']}-{i}", **t})

    # 예약도 담당(디자이너)별로 필터 — 각 디자이너 테넌트엔 자기 예약만(멀티테넌트).
    bookings = []
    idx = 0
    for b in reserve_rows or []:
        # 취소·노쇼도 수집해 화면에 '취소됨'으로 보여준다(그 시간이 비었다는 정보가 필요).
        # 이미 다녀간 '방문완료/입력완료'만 제외 — 다가오는 예약이 아니므로.
        st = _clean(b.get("status")) or ""
        if "방문완료" in st or "입력완료" in st:
            continue
        d = _norm_date(b.get("날짜") or b.get("date"))
        if not d or d < today:  # 오늘 이후(다가오는 예약)만
            continue
        bstaff = (b.get("staff") or "").strip() or None
        if not bstaff and b.get("detail"):  # 상세셀 앞머리 '하예원.' → 담당 추출(폴백)
            m = re.match(r"\s*([^.\s]+)\s*\.", str(b.get("detail")))
            bstaff = m.group(1) if m else None
        if staff and staff not in (bstaff or "") and staff not in str(b.get("detail") or ""):
            continue  # 담당(디자이너) 필터 — 이 디자이너 예약만
        bookings.append({
            "ext_id": f"B{idx}",
            "customer_ext": (b.get("고객번호") or b.get("custno") or b.get("customer_ext")),
            "name": _clean(b.get("name") or b.get("고객명")),                       # 예약자 이름(연결·표시용)
            "phone": re.sub(r"\D", "", str(b.get("phone") or b.get("전화번호") or "")) or None,
            "staff": bstaff,                                                       # 담당 디자이너(화면 필터용)
            "date": d,
            "time": b.get("시간") or b.get("time"),
            "service": _clean(b.get("메뉴") or b.get("service")),
            "note": _note(b.get("detail")),
            "status": st or None,
        })
        idx += 1

    return {"customers": customers, "transactions": transactions, "bookings": bookings,
            "reservations_ok": reservations_ok}


def _windows(total_days: int, today: date) -> list[tuple[date, date]]:
    """HandSOS 1회 조회 최대 365일 → 과거로 창 분할. 인접 창이 '경계일을 공유하지 않게' 만든다
    (코드리뷰 M3: end-win 이면 경계일이 두 창에 겹쳐 그날 거래가 두 번 수집·이중집계됨).
    각 창은 [end-(win-1), end] 로 win 일을 '포함'하고, 다음 창의 end 는 그 하루 전."""
    wins: list[tuple[date, date]] = []
    off = 0
    while off < total_days:
        win = min(365, total_days - off)
        end = today - timedelta(days=off)
        start = end - timedelta(days=win - 1)   # win 일 포함(경계 중복 없음)
        wins.append((start, end))
        off += win
    return wins


def _harvest_history(hs, store: dict, total_days: int) -> list:
    """HandSOS 는 1회 조회 최대 365일 → 창을 나눠 과거로 반복 수집·누적."""
    import time

    if total_days <= 365:
        res = hs.harvest_store(store)
        if res.get("error") == "login-failed":
            raise RuntimeError("harvest 실패: login-failed")
        return res.get("rows") or []

    rows: list = []
    wins = _windows(total_days, date.today())
    for i, (start, end) in enumerate(wins):
        s = {**store, "report": {**store["report"], "date_from": str(start), "date_to": str(end),
                                 "date_range_days": (end - start).days + 1}}
        res = hs.harvest_store(s)
        if res.get("error") == "login-failed":
            raise RuntimeError("harvest 실패: login-failed")
        wr = res.get("rows") or []
        print(f"  창 {start}~{end}: {len(wr)}행 (누적 {len(rows) + len(wr)})")
        rows += wr
        if not wr and i > 0:   # 첫 창 이후 빈 창 = 더 과거 데이터 없음 → 중단
            break
        time.sleep(2)
    return rows


def scrape_salon(creds: dict) -> dict:
    """살롱 로그인 1회로 매출+예약 원본 수확(정규화 전). 담당 분리는 호출측 normalize 에서."""
    import handsos_sync as hs  # noqa: 지연 import

    total_days = int(os.environ.get("SYNC_DAYS") or creds.get("days", 7))
    store = {
        "slug": creds.get("slug") or "salon",
        "company_code": creds.get("company") or creds.get("company_code") or "",
        "username": creds.get("id"),
        "password": creds.get("pw"),
        "report": {"date_range_days": min(total_days, 365)},
        "collect_reservations": True,
    }
    hs.apply_overrides(store)
    rows = _harvest_history(hs, store, total_days)
    if not rows:
        raise RuntimeError("harvest 실패: 0행(로그인/기간 확인)")
    reserve_rows = []
    reservations_ok = True
    try:
        rres = hs.harvest_reservations(store) or {}
        if rres.get("error"):                  # 소프트 실패(예외 없이 error)도 미확정 처리(H1)
            reservations_ok = False
        reserve_rows = rres.get("parsed") or []
    except Exception as exc:                     # 예약 수확 실패 → 예약 보존(스테일 정리 스킵)
        print(f"  ⚠ 예약 수확 실패({exc}) — 기존 예약 보존")
        reservations_ok = False
        reserve_rows = []
    return {"rows": rows, "reserve_rows": reserve_rows, "reservations_ok": reservations_ok}


def scrape_tenant(creds: dict, session_cookie: str | None = None) -> dict:
    """v1 harvest_store/harvest_reservations 재사용 → normalize."""
    import handsos_sync as hs  # noqa: 지연 import(playwright 등)

    slug = creds.get("slug") or "tenant"
    staff = creds.get("staff")
    store = {
        "slug": slug,
        "staff": staff,
        "company_code": creds.get("company") or creds.get("company_code") or "",
        "username": creds.get("id"),
        "password": creds.get("pw"),
        "report": {"date_range_days": min(int(os.environ.get("SYNC_DAYS") or creds.get("days", 7)), 365)},
        "collect_reservations": True,
    }
    hs.apply_overrides(store)  # secrets/{slug}.selectors.yaml 오버라이드(있으면)

    total_days = int(os.environ.get("SYNC_DAYS") or creds.get("days", 7))
    rows = _harvest_history(hs, store, total_days)  # 365 초과 시 창 분할 누적
    if not rows:
        raise RuntimeError("harvest 실패: 0행(로그인/기간 확인)")

    reserve_rows = []
    reservations_ok = True
    try:
        rres = hs.harvest_reservations(store)
        if rres.get("error"):                 # 소프트 실패(예외 없이 error 반환)도 미확정 처리
            reservations_ok = False
        reserve_rows = rres.get("parsed") or []
    except Exception as exc:                   # 예약 수확 실패 → 확정 실패로 표시(예약 보존)
        print(f"  ⚠ 예약 수확 실패({exc}) — 기존 예약 보존(스테일 정리 스킵)")
        reservations_ok = False
        reserve_rows = []

    return normalize(rows, reserve_rows, staff, reservations_ok=reservations_ok)
