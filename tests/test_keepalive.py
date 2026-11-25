"""DB 깨어 있게(개선 계획 v17 P1, 2026-11-25) — GitHub 60일 규칙에 매일 감시가 꺼지지 않게.

수집을 쉬는 동안 Supabase 무료(7일 활동이 적으면 멈춤)를 깨우는 건 매일 감시뿐이다. GitHub 은 공개 저장소에 60일 활동이
없으면 예약 워크플로를 끈다. keepalive 가 한 달 두 번 예약 워크플로를 모두 다시 켠다 — 새 예약 워크플로를 만들면 여기에도
넣어야 한다(아래 테스트가 잡는다).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
KEEP = (WF / "keepalive.yml").read_text(encoding="utf-8")


def test_runs_twice_a_month_off_the_hour_and_by_hand():
    crons = re.findall(r"cron: '([^']+)'", KEEP)
    assert crons == ["23 2 1,15 * *"] and "workflow_dispatch" in KEEP


def test_every_scheduled_workflow_is_kept_alive_including_itself():
    scheduled = sorted(p.name for p in WF.glob("*.yml") if "schedule:" in p.read_text(encoding="utf-8"))
    assert scheduled == ["deps-audit.yml", "keepalive.yml", "sync-health.yml"]
    loop = re.search(r"for wf in ([^;]+); do", KEEP).group(1).split()
    assert sorted(loop) == scheduled                                                    # 새 예약 워크플로도 여기에
    assert 'gh api -X PUT "repos/${{ github.repository }}/actions/workflows/$wf/enable"' in KEEP   # 켜져 있어도 204


def test_least_privilege_and_no_secrets():
    perms = KEEP[KEEP.index("permissions:"):KEEP.index("jobs:")]
    assert "actions: write" in perms and "contents" not in perms
    assert re.findall(r"secrets\.(\w+)", KEEP) == ["GITHUB_TOKEN"]
    assert "gh workflow enable" not in KEEP[KEEP.index("jobs:"):]                       # 이미 켜진 것엔 실패할 수 있다
