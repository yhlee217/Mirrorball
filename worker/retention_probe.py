"""개선 계획 v4 사전 측정 — 첫 방문 손님 · 연락 효과 · 화면이 받는 데이터 양. 읽기 전용.

v4(playbook/IMPROVE_PLAN_v4.md)의 기본값을 추측하지 않고 실제 기록으로 확인한다.
  · 첫 방문 뒤 두 번째 방문까지 며칠 걸리나 — '다시 오실 때' 권유 시점이 시술 표준 주기와 맞나
  · 한 주에 첫 방문이 몇 명인가 — '첫 방문 안부' 목록이 한 주에 몇 명씩 생기나
  · 방문 1회로 남은 분이 지금 몇 명인가 — '다시 오실 때' 목록이 첫 주에 몇 명으로 시작하나
  · 연락 기록과 그 뒤 방문·예약 — '연락 효과'의 기준선
  · 거래 건수 — 화면을 한 번 열 때 몇 번에 나눠 받나(1,000건씩)
  · 선불 잔액이 남은 채 발길이 끊긴 손님 — 개선 계획 v5 P3(선불 손님 챙기기)의 규모
이름·전화번호는 읽지 않는다. 날짜와 건수만 센다. 판정(실고객·활성 예약)은 ux_probe 와 같다.

사용:
    .venv/bin/python worker/retention_probe.py
"""

from __future__ import annotations

import datetime as dt
import math
from collections import Counter, defaultdict

import txkind
import ux_probe as up  # 실고객·활성 예약 판정 — 화면(web/lib)과 같은 기준(환경 읽기도 여기서)

import supa  # noqa: E402

PAGE = 1000  # PostgREST 한 번에 최대 행 수(web/lib/customers fetchAllRows 와 같다)
REACH = (28, 42, 56, 90)  # 첫 방문 뒤 이 날수 안에 다시 오신 비율을 본다
POOL = ((0, 13), (14, 27), (28, 56), (57, 90), (91, 180))  # 방문 1회 손님 — 첫 방문 뒤 지난 날
AWAY = (60, 90, 180)  # 선불 잔액 남은 손님 — 마지막 방문 뒤 이 날수를 넘겨 안 오신 분


def visit_dates(txs: list[dict]) -> dict[str, list[str]]:
    """손님별 방문일(시술을 받은 날, 오름차순). 충전·제품만 산 날은 방문이 아니다."""
    by: dict[str, set] = defaultdict(set)
    for t in txs:
        cid, d = t.get("customer_id"), (t.get("date") or "")[:10]
        if not cid or not d:
            continue
        if (t.get("kind") or txkind.classify(t.get("service"))) != "service":
            continue
        by[cid].add(d)
    return {k: sorted(v) for k, v in by.items()}


def quantiles(xs: list[int]) -> dict | None:
    """사분위 — 표본이 작으니 보간 없이 순위로."""
    if not xs:
        return None
    a = sorted(xs)

    def q(p: float) -> int:
        return a[min(len(a) - 1, int(p * len(a)))]

    return {"n": len(a), "p25": q(0.25), "p50": q(0.5), "p75": q(0.75), "p90": q(0.9)}


def _days(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def measure(customers: list[dict], txs: list[dict], bookings: list[dict], contacts: list[dict],
            now: dt.datetime) -> dict:
    today = now.date()
    t_iso = today.isoformat()
    real = {c["id"]: c for c in customers if up.is_real(c.get("ext_id")) and not c.get("churned_at")}
    visits = visit_dates(txs)
    active = {b["customer_id"] for b in bookings if b.get("customer_id") and up.is_active_booking(b, now)}

    # ① 첫 방문 → 두 번째 방문. 첫 방문이 1년 안이고 90일 넘게 지난 분(결과가 닫힌 분)만 비율에 쓴다.
    closed, gaps = 0, []
    reach = Counter()
    for cid in real:
        ds = visits.get(cid) or []
        if not ds:
            continue
        since_first = _days(ds[0], t_iso)
        if len(ds) >= 2 and since_first <= 365:
            gaps.append(_days(ds[0], ds[1]))
        if 90 <= since_first <= 365:
            closed += 1
            if len(ds) >= 2:
                g = _days(ds[0], ds[1])
                for r in REACH:
                    if g <= r:
                        reach[r] += 1

    # ② 한 주에 첫 방문 몇 명 — 오늘 전까지 꽉 찬 8주(월~일)
    monday = today - dt.timedelta(days=today.weekday())
    weeks = [monday - dt.timedelta(weeks=w) for w in range(8, 0, -1)]
    per_week = [0] * len(weeks)
    for cid in real:
        ds = visits.get(cid)
        if not ds:
            continue
        f = dt.date.fromisoformat(ds[0])
        for i, w in enumerate(weeks):
            if w <= f < w + dt.timedelta(days=7):
                per_week[i] += 1

    # ③ 방문 1회로 남은 분 — 예약 없는 분만(예약했으면 챙길 일이 없다)
    pool = Counter()
    for cid in real:
        ds = visits.get(cid) or []
        if len(ds) != 1 or cid in active:
            continue
        ago = _days(ds[0], t_iso)
        for lo, hi in POOL:
            if lo <= ago <= hi:
                pool[(lo, hi)] += 1

    # ④ 연락 기록과 그 뒤 — 연락한 날 이후 방문(수집되면 잡힌다) 또는 지금 잡혀 있는 예약
    sent = sorted((c for c in contacts if c.get("customer_id") and c.get("sent_at")), key=lambda c: c["sent_at"])
    first_contact: dict[str, str] = {}
    via = Counter()
    for c in sent:
        first_contact.setdefault(c["customer_id"], c["sent_at"][:10])
        via[c.get("why") or "?"] += 1
    came = booked = 0
    for cid, day in first_contact.items():
        if any(d >= day for d in visits.get(cid) or []):
            came += 1
        elif any(b.get("customer_id") == cid and (b.get("date") or "") >= day and up.is_active_booking(b, now)
                 for b in bookings):
            booked += 1

    # ⑤ 선불 잔액이 남은 손님 — 잔액은 워커의 추정(충전 뒤 시술은 잔액에서 쓴 것으로 봄)
    prepaid = [c for c in real.values() if (c.get("prepaid_balance") or 0) > 0]
    away = []
    for n in AWAY:
        gone = [c for c in prepaid if c.get("last_visit") and _days(c["last_visit"][:10], t_iso) > n]
        away.append((n, len(gone), sum(c["prepaid_balance"] for c in gone)))

    year_ago = (today - dt.timedelta(days=365)).isoformat()
    tx_year = sum(1 for t in txs if (t.get("date") or "") >= year_ago)
    return {
        "customers": len(real),
        "closed": closed,
        "reach": [(r, reach[r]) for r in REACH],
        "gap": quantiles(gaps),
        "per_week": per_week,
        "pool": [((lo, hi), pool[(lo, hi)]) for lo, hi in POOL],
        "contacts": len(sent),
        "contacted": len(first_contact),
        "contact_since": sent[0]["sent_at"][:10] if sent else None,
        "via": dict(via),
        "came": came,
        "booked": booked,
        "tx": len(txs),
        "tx_year": tx_year,
        "prepaid": (len(prepaid), sum(c["prepaid_balance"] for c in prepaid)),
        "prepaid_away": away,
    }


def pct(a: int, b: int) -> str:
    return f"{round(a * 100 / b)}% ({a:,}/{b:,})" if b else "— (대상 없음)"


def man(n: int) -> str:
    return f"{round(n / 10000):,}만원"


def pages(n: int) -> int:
    return max(1, math.ceil(n / PAGE))


def report(slug: str, m: dict) -> list[str]:
    g = m["gap"]
    wk = m["per_week"]
    out = [
        f"[{slug}] 고객 {m['customers']:,}명(이탈 표시 제외)",
        "  첫 방문 → 다시   " + (" · ".join(f"{r}일 안 {pct(n, m['closed'])}" for r, n in m["reach"])
                               if m["closed"] else "— (첫 방문 뒤 90일~1년 지난 분 없음)"),
        "  다시 오기까지    " + (f"중앙값 {g['p50']}일 · 가운데 절반 {g['p25']}~{g['p75']}일 · 90% {g['p90']}일 안 (n={g['n']})"
                               if g else "— (두 번 오신 분 없음)"),
        f"  주당 첫 방문     평균 {sum(wk) / len(wk):.1f}명 · 많을 때 {max(wk)}명 (최근 8주: {' '.join(map(str, wk))})",
        "  방문 1회·예약 없음 " + " · ".join(f"{lo}~{hi}일 {n}명" for (lo, hi), n in m["pool"]),
        (f"  연락 기록        {m['contacts']}건 · {m['contacted']}명 ({m['contact_since']}부터) — "
         f"그 뒤 오심 {m['came']}명 · 예약 잡힘 {m['booked']}명 · 수단 "
         + " ".join(f"{k} {v}" for k, v in sorted(m["via"].items()))) if m["contacts"] else "  연락 기록        아직 없음",
        f"  거래             전체 {m['tx']:,}건({pages(m['tx'])}번에 나눠 받음) · 최근 1년 {m['tx_year']:,}건({pages(m['tx_year'])}번)",
        (f"  선불 잔액        {m['prepaid'][0]}명 · {man(m['prepaid'][1])} — 그중 안 오신 지 "
         + " · ".join(f"{n}일+ {k}명({man(w)})" for n, k, w in m["prepaid_away"])) if m["prepaid"][0]
        else "  선불 잔액        남은 손님 없음",
    ]
    return out


def verdicts(ms: list[dict]) -> list[str]:
    """세 매장을 합쳐 v4 의 기본값을 판단한다. 기준선은 어림값이다."""
    closed = sum(m["closed"] for m in ms)
    reach = {r: sum(dict(m["reach"])[r] for m in ms) for r in REACH}
    gaps_n = sum(m["gap"]["n"] for m in ms if m["gap"])
    med = sorted(m["gap"]["p50"] for m in ms if m["gap"])
    weekly = [sum(m["per_week"]) / len(m["per_week"]) for m in ms]
    start = sum(n for m in ms for (lo, _), n in m["pool"] if lo >= 28)
    contacts = sum(m["contacts"] for m in ms)
    tx = max((m["tx"] for m in ms), default=0)

    out = []
    if closed:
        r90 = reach[90] / closed
        out.append(f"첫 방문 손님 90일 안 재방문 {round(r90 * 100)}% ({reach[90]}/{closed}) — "
                   + ("넷 중 셋 넘게 다시 안 온다 → 첫 방문 챙기기(P1)가 가장 큰 몫" if r90 < 0.25
                      else "절반 넘게 다시 온다 → P1 은 작게" if r90 >= 0.5 else "P1 을 그대로 진행"))
    if med:
        out.append(f"다시 오신 분은 매장마다 중앙값 {'·'.join(map(str, med))}일 만에 (n={gaps_n}) — "
                   "표준 주기(남자커트 28 · 뿌리염색 35 · 여자커트 56 · 펌 90)보다 이르면 '다시 오실 때'를 앞당긴다")
    if weekly:
        out.append(f"첫 방문 안부 — 디자이너당 주 {min(weekly):.0f}~{max(weekly):.0f}명"
                   + (" → 한 주에 감당할 만하다" if max(weekly) <= 10 else " → 많다. 시술·금액 큰 분부터 보여준다"))
    out.append(f"'다시 오실 때' 첫 주 후보 {start}명(방문 1회 · 28~180일 · 예약 없음, 세 매장)"
               + (" → 첫 주는 오래된 분이 몰린다. 처음엔 최근 90일 안만" if start > 60 else ""))
    out.append(f"연락 기록 {contacts}건" + (" → 4주 넘게 쌓인 뒤 효과 표시(P2)" if contacts < 100 else " → 효과 표시를 바로 해도 된다"))
    if tx:
        out.append(f"거래 가장 많은 매장 {tx:,}건 → 1,000건씩 {pages(tx)}쪽(지금은 넷씩 한꺼번에 받는다)")
    gone = [(n, sum(dict((x[0], x[1]) for x in m["prepaid_away"])[n] for m in ms),
             sum(dict((x[0], x[2]) for x in m["prepaid_away"])[n] for m in ms)) for n in AWAY]
    if sum(m["prepaid"][0] for m in ms):
        n90 = next(k for n, k, _ in gone if n == 90)
        w90 = next(w for n, _, w in gone if n == 90)
        out.append(f"선불 잔액 남은 채 90일 넘게 안 오신 분 {n90}명 · {man(w90)}"
                   + (" → 선불 손님 챙기기(v5 P3)의 몫이 크다" if n90 >= 20 else " → 선불 손님 챙기기는 작게"))
    return out


def main() -> int:
    now = dt.datetime.now(up.KST)
    tenants = up._salon_tenants()
    if not tenants:
        print("테넌트 없음")
        return 1
    print(f"개선 계획 v4·v5 사전 측정 · {now:%Y-%m-%d %H:%M} KST · 읽기 전용(날짜·건수만)\n")
    ms = []
    for t in tenants:
        tid = t["id"]
        customers = supa.select_all("customers", tid, "id,ext_id,visit_count,first_visit,last_visit,churned_at,prepaid_balance")
        txs = supa.select_all("transactions", tid, "customer_id,date,kind,service")
        bookings = supa.select_all("bookings", tid, "customer_id,date,time,status")
        contacts = [r for r in supa.select_all("care_items", tid, "customer_id,kind,why,sent_at")
                    if r.get("kind") == "contact"]
        m = measure(customers, txs, bookings, contacts, now)
        ms.append(m)
        print("\n".join(report(t.get("slug") or tid[:8], m)))
        print()
    print("─" * 60)
    print("판단 (세 매장 합산 · 기준선은 어림값)\n")
    print("\n".join("  " + v for v in verdicts(ms)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
