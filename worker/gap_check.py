"""수집 공백 확인 — 어디까지 모았는지 보고 백필에 쓸 SYNC_DAYS 를 알려준다.

수집을 오래 쉬면 '언제부터 비었는지'가 기억에만 남는다. 그걸 추측하지 않게,
DB 에 실제로 들어와 있는 마지막 거래 날짜를 테넌트별로 읽어 공백 일수를 계산한다.
읽기만 하므로 몇 번을 돌려도 안전하다.

사용:
    .venv/bin/python worker/gap_check.py
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    p = ROOT / "web" / ".env.local"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    if not os.environ.get("SUPABASE_URL") and os.environ.get("NEXT_PUBLIC_SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = os.environ["NEXT_PUBLIC_SUPABASE_URL"]


_load_env()

import supa  # noqa: E402

MARGIN_DAYS = 14  # 겹침 여유 — 경계에서 놓치지 않게


def _list_tenants() -> list:
    """테넌트 목록. industry 컬럼은 세무 마이그레이션(0016) 적용 전 DB 에는 없으므로,
    없으면 컬럼 없이 다시 조회하고 전부 미용실로 본다."""
    try:
        return supa._get("/tenants", {"select": "id,slug,salon_name,industry", "order": "slug"})
    except RuntimeError as exc:
        if "industry" not in str(exc):
            raise
        print("참고: tenants.industry 없음 — 0016_tax_domain 미적용 DB 로 보고 전부 미용실로 처리\n")
        return supa._get("/tenants", {"select": "id,slug,salon_name", "order": "slug"})


def _last_date(table: str, tid: str) -> str | None:
    rows = supa._get(f"/{table}", {"tenant_id": f"eq.{tid}", "select": "date",
                                   "order": "date.desc", "limit": "1"})
    return rows[0]["date"] if rows else None


def _recent_months(tid: str, today: date, months: int = 5) -> list[tuple[str, int]]:
    """최근 N개월 월별 거래 건수 — 어느 달이 비었는지 눈으로 보이게."""
    since = str(today - timedelta(days=31 * months))
    rows = supa._get("/transactions", {"tenant_id": f"eq.{tid}", "select": "date",
                                       "date": f"gte.{since}", "order": "date",
                                       "limit": "20000"})
    c = Counter(r["date"][:7] for r in rows if r.get("date"))
    keys = []
    y, m = today.year, today.month
    for _ in range(months):                 # 달 단위로 거슬러 올라간다(31일 빼기는 달을 건너뛴다)
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return [(k, c.get(k, 0)) for k in reversed(keys)]


def main() -> int:
    today = date.today()
    tenants = _list_tenants()
    if not tenants:
        print("테넌트 없음")
        return 1

    worst = 0
    print(f"오늘 {today}\n")
    for t in tenants:
        if (t.get("industry") or "salon") != "salon":
            continue  # 세무 테넌트는 수집 대상이 아니다
        tid, slug = t["id"], t.get("slug") or t["id"][:8]
        tx_last = _last_date("transactions", tid)
        bk_last = _last_date("bookings", tid)

        print(f"[{slug}] {t.get('salon_name') or ''}")
        if not tx_last:
            print("  거래 없음 — 아직 한 번도 수집되지 않았거나 초기화된 상태")
            print("  → 전체 이력 백필 필요: SYNC_DAYS=1825\n")
            worst = max(worst, 1825)
            continue

        gap = (today - date.fromisoformat(tx_last)).days
        worst = max(worst, gap)
        print(f"  마지막 거래  {tx_last}  ({gap}일 전)")
        print(f"  마지막 예약  {bk_last or '없음'}")
        months = _recent_months(tid, today)
        print("  월별 거래   " + "  ".join(f"{m} {n:>4}" for m, n in months))
        print(f"  → 이 매장만 메꾸려면: SYNC_DAYS={gap + MARGIN_DAYS}\n")

    if worst:
        rec = worst + MARGIN_DAYS
        print("─" * 56)
        print(f"권장 백필 명령 (가장 오래 빈 곳 기준 {worst}일 + 여유 {MARGIN_DAYS}일):")
        print(f"\n    SYNC_DAYS={rec} FORCE=1 bash worker/run_mac.sh\n")
        print("업서트라 중복이 생기지 않고, 스테일 정리는 이번에 실제 수집한")
        print("날짜 범위 안에서만 돌기 때문에 창을 넉넉히 잡아도 과거는 안전하다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
