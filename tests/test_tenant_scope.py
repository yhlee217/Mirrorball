"""매장 섞임 막기(개선 계획 v8 P0) — 앱이 손님 · 거래 · 예약 · 연락 · 수집 기록을 읽을 때 매장 조건이 있는지.

RLS 는 '소속된 매장 전부'를 보여 준다. 계정 하나에 매장 하나일 땐 같지만, 여러 매장에 속한 계정(운영자 · 한 살롱의
여러 디자이너)이면 매장 조건 없이 읽은 목록에 다른 매장 손님이 섞이고 이름이 '고객'으로 보인다. 정적 검사로 막는다:
읽기 사슬에 tenant_id 조건이 있거나, 한 행 · 한 손님으로 좁히거나(.eq('id'), .eq('customer_id')), 쓰기(insert · upsert)여야 한다.
"""

from __future__ import annotations

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
TABLES = ("customers", "transactions", "bookings", "care_items", "sync_jobs", "ops_events", "store_stats")
FROM = re.compile(r"\.from\('(" + "|".join(TABLES) + r")'\)")
SCOPED = ("tenant_id", ".eq('id'", ".eq('customer_id'", ".insert(", ".upsert(")


def _chain(text: str, start: int) -> str:
    """.from(...) 부터 그 문장의 끝까지(다음 ; 또는 빈 줄) — 사슬이 여러 줄에 걸쳐도 함께 본다."""
    end = len(text)
    for stop in (";", "\n\n"):
        i = text.find(stop, start)
        if i != -1:
            end = min(end, i)
    return text[start:end]


def test_every_read_is_scoped_to_a_tenant():
    bad = []
    for path in sorted(list((WEB / "app").rglob("*.ts*")) + list((WEB / "lib").rglob("*.ts"))):
        text = path.read_text(encoding="utf-8")
        for m in FROM.finditer(text):
            chain = _chain(text, m.start())
            if not any(s in chain for s in SCOPED):
                line = text.count("\n", 0, m.start()) + 1
                bad.append(f"{path.relative_to(WEB)}:{line} {m.group(1)}")
    assert not bad, "매장 조건 없는 읽기:\n" + "\n".join(bad)


def test_current_tenant_is_stable():
    """여러 매장에 속한 계정의 '현재 매장'이 요청마다 바뀌지 않게 — 정렬해서 고른다."""
    src = (WEB / "lib" / "tenant.ts").read_text(encoding="utf-8")
    fn = src[src.index("export async function getTenantId"):]
    fn = fn[: fn.index("\n}\n")]
    assert ".order('created_at'" in fn and ".limit(1)" in fn
    assert "pickTenant(" in fn  # 데모 매장은 뒤로(v11 P0, tests/test_onboarding)


def test_last_synced_takes_a_tenant():
    src = (WEB / "lib" / "sync.ts").read_text(encoding="utf-8")
    assert "tenantId: string" in src and ".eq('tenant_id', tenantId)" in src
