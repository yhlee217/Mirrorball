"""시술별 단가 — HandSOS 결제 기록에서 시술마다 실제로 받은 금액을 정리한다(2026-10-26 운영자 요청). 읽기 전용.

앱엔 가격표가 없다 — 금액은 모두 HandSOS 결제액(실제로 받은 돈)이다(10.16 질문 '가격표가 없는데 어떻게 계산했나').
그래서 시술마다 결제액이 어떻게 퍼져 있는지 본다.
  · 시술별 — 한 가지만 받은 결제를 시술(커트 · 뿌리펌 · 염색 …, 앱의 재방문 주기와 같은 분류 — care-cycle.json)로
    묶는다. 'A+B' 처럼 함께 받은 결제는 금액이 합이라 따로 '함께 받은 시술'에 둔다(나눠 매기지 않는다)
  · 보통 — 가장 흔한 금액과 그 비율. 정가에 가장 가깝다(할인 · 추가 요금이 섞이면 비율이 낮다)
  · 중간값 · 범위(하위 10% ~ 상위 90%) · 최근 6개월의 보통(가격을 올렸으면 여기서 보인다) · 마지막 결제일
시술만 센다(충전 · 제품 · 환불은 뺀다 — worker/txkind 와 같은 분류). 0원(무료 · 서비스) 건은 따로 센다.
메뉴 이름 · 금액 · 날짜만 읽는다 — 손님은 읽지도 찍지도 않는다.

사용:
    .venv/bin/python worker/price_probe.py              # hayewoni
    .venv/bin/python worker/price_probe.py juhwan
    MONTHS=24 .venv/bin/python worker/price_probe.py    # 최근 24개월 결제만(기본 전체)
    MENU=1 .venv/bin/python worker/price_probe.py       # 끝에 메뉴 이름별 자세히
"""

from __future__ import annotations

import datetime as dt
import math
import os
import re
import sys
from collections import Counter, defaultdict

from env import load_env

load_env()

RECENT_MONTHS = 6
TOP = 60          # 메뉴 이름별은 이만큼만 줄로 찍고 나머지는 '그 밖' 한 줄
TOP_COMBOS = 15
PLUS = re.compile(r"\s*\+\s*")


def _date(s: object) -> dt.date:
    return dt.date.fromisoformat(str(s)[:10])


def _pct(sorted_amts: list[int], q: float) -> int:
    """가장 가까운 순위(nearest-rank) 백분위."""
    return sorted_amts[max(0, math.ceil(q * len(sorted_amts)) - 1)]


def _mode(amts: list[int]) -> tuple[int, int]:
    """(가장 흔한 금액, 그 건수). 건수가 같으면 큰 금액 — 할인보다 정가 쪽을 고른다."""
    amt, n = max(Counter(amts).items(), key=lambda kv: (kv[1], kv[0]))
    return amt, n


def _kind(row: dict) -> str:
    if row.get("kind"):
        return str(row["kind"])
    from txkind import classify  # 0019 전 행 — 이름으로 판정(워커 · 화면과 같은 어휘)

    return classify(row.get("service"))


def treatment(part: str) -> str:
    """메뉴 한 가지 → 시술(앱의 재방문 주기와 같은 분류). 맞는 규칙이 없으면 '기타'."""
    from care_cycle import care_for

    rule = care_for(part)
    return rule["cat"] if rule else "기타"


def _stats(items: list[tuple[dt.date, int]], cut: dt.date) -> dict:
    amts = sorted(a for _, a in items)
    common, n_common = _mode(amts)
    recent = [a for d, a in items if d >= cut]
    return {
        "n": len(amts), "common": common, "share": n_common / len(amts),
        "median": _pct(amts, 0.5), "p10": _pct(amts, 0.1), "p90": _pct(amts, 0.9),
        "recent": _mode(recent)[0] if recent else None, "recent_n": len(recent),
        "last": max(d for d, _ in items),
    }


def _paid(rows: list[dict]) -> tuple[list[tuple[str, dt.date, int]], Counter, int]:
    """시술 결제만 — (메뉴 이름, 날짜, 금액), 0원은 메뉴별로 따로 센 것, 뺀 건수(충전 · 제품 · 환불)."""
    paid, zero, skipped = [], Counter(), 0
    for r in rows:
        if _kind(r) != "service":
            skipped += 1
            continue
        name = " ".join(str(r.get("service") or "").split()) or "(이름 없음)"
        amt = int(r.get("amount_won") or 0)
        if amt <= 0:
            zero[name] += 1
        else:
            paid.append((name, _date(r["date"]), amt))
    return paid, zero, skipped


def _cut(today: dt.date, recent_months: int) -> dt.date:
    return today - dt.timedelta(days=round(recent_months * 30.44))


def summarize(rows: list[dict], today: dt.date, recent_months: int = RECENT_MONTHS) -> tuple[list[dict], dict]:
    """메뉴 이름별(HandSOS 메뉴 그대로) 요약 — 건수 많은 순, 전체 숫자. 네트워크 없이 계산만."""
    paid, zero, skipped = _paid(rows)
    groups: dict[str, list[tuple[dt.date, int]]] = defaultdict(list)
    for name, d, a in paid:
        groups[name].append((d, a))
    cut = _cut(today, recent_months)
    out = [{"name": name, **_stats(items, cut), "zero": zero.pop(name, 0)} for name, items in groups.items()]
    out.sort(key=lambda m: (-m["n"], m["name"]))
    dates = [_date(r["date"]) for r in rows if r.get("date")]
    total = {"paid": len(paid), "zero": sum(m["zero"] for m in out) + sum(zero.values()), "skipped": skipped,
             "first": min(dates) if dates else None, "last": max(dates) if dates else None}
    return out, total


def by_treatment(rows: list[dict], today: dt.date, recent_months: int = RECENT_MONTHS) -> tuple[list[dict], list[dict]]:
    """(시술별 — 한 가지만 받은 결제, 함께 받은 시술 — 'A+B' 결제). 둘 다 건수 많은 순."""
    paid, _, _ = _paid(rows)
    single: dict[str, list[tuple[dt.date, int]]] = defaultdict(list)
    menus: dict[str, Counter] = defaultdict(Counter)
    combo: dict[str, list[tuple[dt.date, int]]] = defaultdict(list)
    for name, d, a in paid:
        parts = [p for p in PLUS.split(name) if p]
        if len(parts) == 1:
            cat = treatment(parts[0])
            single[cat].append((d, a))
            menus[cat][name] += 1
        else:
            combo[" + ".join(treatment(p) for p in parts)].append((d, a))
    cut = _cut(today, recent_months)
    singles = [{"name": cat, **_stats(items, cut), "menus": menus[cat].most_common()} for cat, items in single.items()]
    combos = [{"name": key, **_stats(items, cut)} for key, items in combo.items()]
    singles.sort(key=lambda m: (-m["n"], m["name"]))
    combos.sort(key=lambda m: (-m["n"], m["name"]))
    return singles, combos


def won(n: int) -> str:
    return f"{n:,}원"


def _changed(m: dict) -> bool:
    return m["recent"] is not None and m["recent"] != m["common"] and m["recent_n"] >= 3


def line(m: dict) -> str:
    rng = won(m["p10"]) if m["p10"] == m["p90"] else f"{m['p10']:,}~{won(m['p90'])}"
    recent = ("최근 6개월 없음" if m["recent"] is None
              else f"최근 6개월 {won(m['recent'])}" + (" ← 바뀜" if _changed(m) else ""))
    return (f"  {m['name']} — {m['n']}건 · 보통 {won(m['common'])}({round(m['share'] * 100)}%) · 중간 {won(m['median'])}"
            f" · 범위 {rng} · {recent} · 마지막 {m['last']:%y.%m.%d}" + (f" · 0원 {m['zero']}건" if m.get("zero") else ""))


def report(slug: str, menus: list[dict], total: dict, singles: list[dict] | None = None,
           combos: list[dict] | None = None, menu_detail: bool = True) -> list[str]:
    span = f"{total['first']:%Y.%m.%d} ~ {total['last']:%Y.%m.%d}" if total["first"] else "기록 없음"
    out = [f"시술별 단가 — {slug} · 결제 기록 {span} · 시술 {total['paid']:,}건(0원 {total['zero']}건 따로 · 충전 · 제품 · 환불"
           f" {total['skipped']}건 뺌) · 메뉴 {len(menus)}개 · 메뉴 이름과 금액만"]
    if singles is not None:
        out += ["", "시술별 — 한 가지만 받은 결제(분류는 앱의 재방문 주기와 같다)"]
        for m in singles:
            out.append(line(m))
            names = " · ".join(f"{n} {c}건" for n, c in m["menus"][:6])
            more = f" · 그 밖 {len(m['menus']) - 6}개" if len(m["menus"]) > 6 else ""
            out.append(f"      메뉴: {names}{more}")
    if combos:
        out += ["", f"함께 받은 시술 — 'A+B' 결제는 금액이 합이라 따로(많은 순 {min(len(combos), TOP_COMBOS)}개)"]
        out += [line(m) for m in combos[:TOP_COMBOS]]
        if len(combos) > TOP_COMBOS:
            out.append(f"  그 밖 조합 {len(combos) - TOP_COMBOS}개 — {sum(m['n'] for m in combos[TOP_COMBOS:])}건")
    if menu_detail:
        out += ["", "메뉴 이름별 — HandSOS 메뉴 그대로"]
        out += [line(m) for m in menus[:TOP]]
        rest = menus[TOP:]
        if rest:
            out.append(f"  그 밖 메뉴 {len(rest)}개 — {sum(m['n'] for m in rest)}건")
    head = singles if singles is not None else menus
    changed = [m["name"] for m in head if _changed(m)]
    mixed = [m["name"] for m in head[:TOP] if m["share"] < 0.5 and m["n"] >= 5]
    out += ["", "읽는 법 — '보통'이 정가에 가장 가깝다. 비율이 낮으면 할인 · 추가 요금(기장 · 약제)이나 원장 · 부원장 메뉴가"
                " 섞인 것이다(시술마다 '메뉴' 줄을 본다)."]
    if changed:
        out.append(f"  최근 6개월에 보통 금액이 바뀐 것: {', '.join(changed[:15])}")
    if mixed:
        out.append(f"  금액이 여러 가지인 것(보통이 절반 아래): {', '.join(mixed[:15])}")
    return out


def main(argv: list[str]) -> int:
    import supa

    slug = argv[1] if len(argv) > 1 else "hayewoni"
    t = supa.get_tenant_by_slug(slug)
    if not t:
        print(f"매장 '{slug}' 이 없다")
        return 1
    rows = supa.select_all("transactions", t["id"], "service,amount_won,date,kind")
    today = dt.date.today()
    months = int(os.environ.get("MONTHS") or 0)
    if months:
        rows = [r for r in rows if _date(r["date"]) >= _cut(today, months)]
    menus, total = summarize(rows, today)
    singles, combos = by_treatment(rows, today)
    print("\n".join(report(slug, menus, total, singles, combos, menu_detail=bool(os.environ.get("MENU")))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
