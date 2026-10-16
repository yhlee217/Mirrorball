"""워크플로 손질(개선 계획 v15 P3) — 액션은 Node 24 로 도는 판 · 매일 감시는 정시를 피해서.

GitHub 가 Node 20 액션마다 'deprecated … forced to run on Node.js 24' 경고를 냈다. 판마다 action.yml 의 runs.using 을
열어 보고 node24 인 가장 낮은 판으로 올렸다(2026-10-16 — upload-pages-artifact 는 composite 라 안에서 부르는
upload-artifact 판으로 봤다). 새 액션을 쓰면 여기 표에 그 판의 Node 를 확인해 더한다.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
NODE24 = {
    "actions/checkout": 5,
    "actions/setup-node": 5,
    "actions/setup-python": 6,
    "actions/upload-pages-artifact": 5,   # v4 는 upload-artifact v4(node20)를 부른다
    "actions/deploy-pages": 5,
    "cloudflare/wrangler-action": 4,
}


def test_every_action_is_a_node24_version():
    seen = set()
    for wf in sorted(WF.glob("*.yml")):
        for name, ver in re.findall(r"uses:\s*([\w.-]+/[\w.-]+)@v(\d+)", wf.read_text(encoding="utf-8")):
            assert name in NODE24, f"{wf.name}: {name} — Node 판을 확인해 표에 더한다"
            assert int(ver) >= NODE24[name], f"{wf.name}: {name}@v{ver} 는 Node 20 판"
            seen.add(name)
    assert {"actions/checkout", "actions/setup-node", "actions/setup-python"} <= seen


def test_daily_watch_avoids_the_top_of_the_hour():
    text = (WF / "sync-health.yml").read_text(encoding="utf-8")
    crons = re.findall(r"cron: '([^']+)'", text)
    assert crons and all(c.split()[0] != "0" for c in crons), crons
    assert "10시쯤" in (ROOT / "playbook" / "OPERATIONS_APP.md").read_text(encoding="utf-8")


def test_launch_checklist_points_to_the_runbook():
    head = "\n".join((ROOT / "LAUNCH.md").read_text(encoding="utf-8").splitlines()[:6])
    assert "playbook/OPERATIONS_APP.md" in head and "지금 상태로 읽지 않는다" in head
