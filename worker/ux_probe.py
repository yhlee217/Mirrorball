"""UX 계획 v2(playbook/UX_PLAN.md §5) — 시작 전에 실제 숫자를 잰다.

계획의 '바로 가능' 항목이 실제로 쓸모 있을지는 데이터 채움률에 달려 있다. 전화번호가
절반뿐이면 문자 버튼은 반쪽이고, 디자이너당 월 신규가 몇 명뿐이면 전환율을 %로 보여주면
안 된다. 그래서 추측하지 않고 잰다 — gap_check.py · gender_probe.py 와 같은 방식.

읽기만 한다. 전화번호는 복호화해도 '있는지'만 세고, 이름·번호는 어디에도 출력하지 않는다.

사용:
    .venv/bin/python worker/ux_probe.py
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from env import load_env

load_env()


import mirrorball_crypto as mc  # noqa: E402
import supa  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
# web/lib/settings.ts DEFAULT_SETTINGS 와 같은 값 — 테넌트 설정에 없으면 이걸 쓴다
LAPSE_DEFAULTS = {"lapsed_months": 12, "lapsed_soft_months": 6, "lapsed_soft_visits": 3}


# ── 화면과 같은 판정 (TS 원본을 그대로 옮겼다 — 기준이 다르면 잰 숫자가 화면과 어긋난다) ──

def is_real(ext_id) -> bool:
    """web/lib/customers.ts isRealCustomer — 고객번호가 숫자인 행만 실고객(워크인 제외)."""
    return bool(ext_id) and str(ext_id).isdigit()


def is_cancelled(status) -> bool:
    """web/lib/bookings.ts isCancelled."""
    return bool(status) and ("취소" in status or "노쇼" in status)


def is_active_booking(b: dict, now: dt.datetime) -> bool:
    """web/lib/bookings.ts isActiveBooking + kst.isUpcoming — 취소·노쇼 아니고 아직 안 지난 예약."""
    if is_cancelled(b.get("status")) or not b.get("date"):
        return False
    today = now.strftime("%Y-%m-%d")
    if b["date"] != today:
        return b["date"] > today
    t = b.get("time")
    return not t or t >= now.strftime("%H:%M")


def lapse_settings(raw) -> dict:
    s = dict(LAPSE_DEFAULTS)
    if isinstance(raw, dict):
        for k in s:
            v = raw.get(k)
            if isinstance(v, (int, float)) and v > 0:
                s[k] = v
    return s


def is_lapsed(c: dict, s: dict, today: dt.date) -> bool:
    """web/lib/settings.ts isLapsed — N개월 초과 미방문, 또는 M개월 초과이면서 방문 K회 미만."""
    if not c.get("last_visit"):
        return True
    days = (today - dt.date.fromisoformat(c["last_visit"][:10])).days
    return days > s["lapsed_months"] * 30 or (
        days > s["lapsed_soft_months"] * 30 and (c.get("visit_count") or 0) < s["lapsed_soft_visits"])


def needs_care(c: dict, s: dict, today: dt.date, booked: bool) -> bool:
    """web/lib/customers.ts needsCare — 이탈 표시·이미 예약·설정의 이탈 판정이면 챙길 고객이 아니다."""
    if c.get("churned_at") or booked:
        return False
    if c.get("revisit_state") not in ("overdue", "due"):
        return False
    return not is_lapsed(c, s, today)


def last_n_months(today: dt.date, n: int) -> list[str]:
    """이번 달 포함 최근 n개월 'YYYY-MM'. 달 단위로 센다(31일씩 빼면 달을 건너뛴다)."""
    y, m, out = today.year, today.month, []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


# ── 측정 (네트워크·복호화와 분리 — 테스트 가능) ──────────────────────────────

def measure(customers: list[dict], txs: list[dict], bookings: list[dict],
            has_phone: dict, settings: dict, now: dt.datetime) -> dict:
    today = now.date()
    real = [c for c in customers if is_real(c.get("ext_id"))]
    active = {b["customer_id"] for b in bookings if b.get("customer_id") and is_active_booking(b, now)}
    # 화면의 챙길 고객 = 예약 확인 전 후보에서 이미 예약한 분을 뺀 것(2026-10-12 P0 1번)
    cand = [c for c in real if needs_care(c, settings, today, booked=False)]
    care = [c for c in real if needs_care(c, settings, today, booked=c["id"] in active)]

    since = (today - dt.timedelta(days=365)).isoformat()
    recent = [t for t in txs if (t.get("date") or "") >= since]

    status = Counter()
    for b in bookings:
        s = b.get("status") or ""
        status["노쇼" if "노쇼" in s else "취소" if "취소" in s else "그 외"] += 1
    dates = sorted(b["date"] for b in bookings if b.get("date"))

    newc = Counter((c.get("first_visit") or "")[:7] for c in real)
    lo = (today - dt.timedelta(days=183)).isoformat()
    hi = (today - dt.timedelta(days=60)).isoformat()
    cohort = [c for c in real if lo <= (c.get("first_visit") or "") <= hi]
    booked = [c for c in real if c["id"] in active]
    bal = [c.get("prepaid_balance") or 0 for c in real]

    return {
        "customers": len(real),
        "phone": (sum(1 for c in real if has_phone.get(c["id"])), len(real)),
        "care": len(care),
        "care_phone": (sum(1 for c in care if has_phone.get(c["id"])), len(care)),
        "care_booked": len(cand) - len(care),
        "tx_time": (sum(1 for t in recent if (t.get("time") or "").strip()), len(recent)),
        "repeat": (sum(1 for c in real if (c.get("visit_count") or 0) >= 2), len(real)),
        "cycle": (sum(1 for c in real if c.get("revisit_cycle_days")), len(real)),
        "prepaid": (sum(1 for b in bal if b > 0), sum(b for b in bal if b > 0)),
        "bk_status": status,
        "bk_range": (dates[0], dates[-1]) if dates else None,
        "bk_past": sum(1 for d in dates if d < today.isoformat()),
        "new_by_month": [(k, newc.get(k, 0)) for k in last_n_months(today, 6)],
        "convert": (sum(1 for c in cohort if (c.get("visit_count") or 0) >= 2), len(cohort)),
        "memo_ai": (sum(1 for c in real if c.get("memo_ai")), len(real)),
        "memo_ai_booked": (sum(1 for c in booked if c.get("memo_ai")), len(booked)),
    }


def pct(a: int, b: int) -> str:
    return f"{round(a * 100 / b)}% ({a:,}/{b:,})" if b else "— (대상 없음)"


def won(n: int) -> str:
    return f"{round(n / 10000):,}만원" if abs(n) >= 10000 else f"{n:,}원"


def report(slug: str, salon: str, m: dict) -> list[str]:
    st, rng = m["bk_status"], m["bk_range"]
    n, total = m["prepaid"]
    return [
        f"[{slug}] {salon}",
        f"  고객 {m['customers']:,}명",
        f"  C1  전화번호        {pct(*m['phone'])} · 챙길 고객 중 {pct(*m['care_phone'])}",
        f"  1-1 챙길 고객 {m['care']}명 — 이미 예약해서 빠진 {m['care_booked']}명",
        f"  D4  시술 시각       채움 {pct(*m['tx_time'])} — 최근 12개월 거래",
        f"  B2  방문 2회 이상   {pct(*m['repeat'])} · 주기 계산됨 {pct(*m['cycle'])}",
        f"  A3  선불 잔액       남은 손님 {n}명 · 합계 {won(total)} (추정)",
        f"  A4  예약 상태       그 외 {st['그 외']} · 취소 {st['취소']} · 노쇼 {st['노쇼']}"
        + (f"  ({rng[0]} ~ {rng[1]}, 지난 예약 {m['bk_past']}건)" if rng else "  (예약 없음)"),
        "  D2  월 신규         " + " · ".join(f"{int(k[5:])}월 {v}" for k, v in m["new_by_month"]),
        f"      2회차 전환      {pct(*m['convert'])} — 최근 6개월 신규 중 첫 방문 60일 지난 분",
        f"  A1  한눈에 정리     전체 {pct(*m['memo_ai'])} · 예약 있는 손님 중 {pct(*m['memo_ai_booked'])}",
    ]


def verdicts(ms: list[dict]) -> list[str]:
    """세 매장을 합쳐 계획의 우선순위를 판단한다. 기준선은 어림값이다."""
    def tot(key):
        return tuple(map(sum, zip(*(m[key] for m in ms)))) if ms else (0, 0)

    ph, tm, cv = tot("phone"), tot("tx_time"), tot("convert")
    care = sum(m["care"] for m in ms)
    booked = sum(m["care_booked"] for m in ms)
    no_show = sum(m["bk_status"]["노쇼"] for m in ms)
    prepaid = sum(m["prepaid"][0] for m in ms)
    # 이번 달은 진행 중이라 빼고, 디자이너 한 명 기준 월평균 신규
    per = [v for m in ms for _, v in m["new_by_month"][:-1]]
    avg_new = sum(per) / len(per) if per else 0

    def rate(t):
        return t[0] / t[1] if t[1] else 0

    out = []
    out.append(f"1-1 챙길 고객 {care}명 — 이미 예약해서 빠진 {booked}명(앱 숫자도 같다)")
    r = rate(ph)
    out.append(f"C1  전화번호 {round(r * 100)}%"
               + (" → 문자·전화 버튼 효과가 크다" if r >= 0.7 else
                  " → 절반 이상은 바로 연락 가능. '전화없음'은 문구 복사를 유지" if r >= 0.4 else
                  " → 효과가 제한적. 문구 복사가 여전히 주 경로"))
    r = rate(tm)
    out.append(f"D4  시술 시각 {round(r * 100)}%"
               + (" → 요일×시간대 가능" if r >= 0.8 else " → 시간대 분석은 보류"))
    out.append(f"D2  디자이너당 월 신규 약 {avg_new:.0f}명"
               + (" → 전환율을 %로 보여줘도 된다" if avg_new >= 20 else
                  " → %가 크게 흔들린다. 'N명 중 M명'으로 보여준다")
               + (f" (지금 2회차 전환 {round(rate(cv) * 100)}%)" if cv[1] else ""))
    out.append(f"A4  노쇼 기록 {no_show}건" + (" → 노쇼 표시는 데이터가 없어 보류" if not no_show else " → 카르테 표시를 검토할 만하다"))
    out.append(f"A3  선불 잔액 남은 손님 {prepaid}명" + (" → 잔액 표시·합계는 보류" if not prepaid else ""))
    return out


# ── 실행 ──────────────────────────────────────────────────────────────────

def _salon_tenants() -> list:
    """industry 컬럼은 0016 미적용 DB 에는 없다(gap_check 와 같은 폴백)."""
    cols = "id,slug,salon_name,settings,dek_wrapped"
    try:
        rows = supa._get("/tenants", {"select": cols + ",industry", "order": "slug"})
        return [t for t in rows if (t.get("industry") or "salon") == "salon"]
    except RuntimeError as exc:
        if "industry" not in str(exc):
            raise
        return supa._get("/tenants", {"select": cols, "order": "slug"})


def main() -> int:
    now = dt.datetime.now(KST)
    tenants = _salon_tenants()
    if not tenants:
        print("테넌트 없음")
        return 1
    print(f"UX 계획 v2 사전 측정 · {now:%Y-%m-%d %H:%M} KST · 읽기 전용\n")

    ms = []
    for t in tenants:
        tid = t["id"]
        customers = supa.select_all(
            "customers", tid,
            "id,ext_id,pii_enc,visit_count,first_visit,last_visit,revisit_state,"
            "revisit_cycle_days,churned_at,prepaid_balance,memo_ai")
        txs = supa.select_all("transactions", tid, "date,time")
        bookings = supa.select_all("bookings", tid, "customer_id,date,time,status")

        # 전화번호는 '있는지'만 본다 — 값은 이 함수 밖으로 나가지 않는다
        has_phone, bad = {}, 0
        dek = mc.unwrap_dek(t["dek_wrapped"]) if t.get("dek_wrapped") else None
        for c in customers:
            if not (dek and c.get("pii_enc")):
                continue
            try:
                p = mc.decrypt_pii(c["pii_enc"], dek) or {}
                has_phone[c["id"]] = bool(str(p.get("phone") or "").strip())
            except Exception:  # noqa: BLE001 — 한 행이 깨져도 측정은 계속
                bad += 1

        m = measure(customers, txs, bookings, has_phone, lapse_settings(t.get("settings")), now)
        ms.append(m)
        print("\n".join(report(t.get("slug") or tid[:8], t.get("salon_name") or "", m)))
        if bad:
            print(f"  (복호화 실패 {bad}행 — 전화 없음으로 셈)")
        print()

    print("─" * 60)
    print("판단 (세 매장 합산 · 기준선은 어림값)\n")
    print("\n".join("  " + v for v in verdicts(ms)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
