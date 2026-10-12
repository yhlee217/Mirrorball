"""'챙길 고객' 판정 — 앱(web/lib/customers.ts needsCare)과 사전 측정(worker/ux_probe.py)이 같은 답을 내는지.

판정이 두 벌이라 한쪽만 바뀌면 측정 숫자가 화면과 어긋난다. 같은 사례를 양쪽에 돌려 대조한다.
TS 쪽은 tsc 로 컴파일해 node 로 실행한다(test_rules_parity 와 같은 방식). 도구가 없으면 건너뛴다.
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import ux_probe as up  # noqa: E402

TODAY = dt.datetime.now(up.KST).date()
S = up.lapse_settings(None)          # web DEFAULT_SETTINGS 와 같은 값


def ago(days: int | None) -> str | None:
    return None if days is None else (TODAY - dt.timedelta(days=days)).isoformat()


# 경계(180·360일)에서 충분히 떨어진 날짜만 쓴다 — 자정 근처 하루 차이로 흔들리지 않게
CASES = [
    ("재방문 도래 — 챙김",           {"revisit_state": "due", "last_visit": ago(40), "visit_count": 3}, False, True),
    ("이탈 위험 — 챙김",             {"revisit_state": "overdue", "last_visit": ago(60), "visit_count": 4}, False, True),
    ("이탈 위험이지만 이미 예약",     {"revisit_state": "overdue", "last_visit": ago(60), "visit_count": 4}, True, False),
    ("재방문 도래지만 이미 예약",     {"revisit_state": "due", "last_visit": ago(40), "visit_count": 3}, True, False),
    ("디자이너가 이탈 표시",          {"revisit_state": "overdue", "last_visit": ago(60), "visit_count": 4,
                                      "churned_at": "2026-09-01T00:00:00Z"}, False, False),
    ("12개월 넘게 안 옴 — 이탈 판정", {"revisit_state": "overdue", "last_visit": ago(400), "visit_count": 9}, False, False),
    ("6개월 넘고 3회 미만 — 이탈 판정", {"revisit_state": "overdue", "last_visit": ago(200), "visit_count": 2}, False, False),
    ("6개월 넘었지만 단골 — 챙김",    {"revisit_state": "overdue", "last_visit": ago(200), "visit_count": 5}, False, True),
    ("신규는 챙길 고객 아님",         {"revisit_state": "new", "last_visit": ago(20), "visit_count": 1}, False, False),
    ("상태 없음",                    {"revisit_state": None, "last_visit": ago(20), "visit_count": 2}, False, False),
    ("마지막 방문 모름 — 이탈 판정",  {"revisit_state": "due", "last_visit": None, "visit_count": 2}, False, False),
]


@pytest.mark.parametrize("name, c, booked, want", CASES, ids=[c[0] for c in CASES])
def test_python_rule(name, c, booked, want):
    assert up.needs_care(c, S, TODAY, booked) is want


def _node_results() -> list[bool] | None:
    if not shutil.which("node") or not shutil.which("npx"):
        return None
    web = ROOT / "web"
    if not (web / "node_modules" / "@supabase" / "supabase-js").exists():
        return None                      # customers.ts 의 타입 import 를 풀 수 없다
    with tempfile.TemporaryDirectory() as tmp:
        c = subprocess.run(
            ["npx", "tsc", "lib/customers.ts", "lib/settings.ts", "--outDir", tmp,
             "--module", "commonjs", "--target", "es2020", "--esModuleInterop", "--skipLibCheck"],
            cwd=web, capture_output=True, text=True, timeout=300,
        )
        if c.returncode != 0 or not (Path(tmp) / "customers.js").exists():
            return None
        cases = Path(tmp) / "cases.json"
        cases.write_text(json.dumps([{"c": c_, "booked": b} for _, c_, b, _ in CASES]), encoding="utf-8")
        runner = Path(tmp) / "run.cjs"
        runner.write_text(
            "const { needsCare } = require('./customers.js');\n"
            "const { DEFAULT_SETTINGS } = require('./settings.js');\n"
            f"const cases = JSON.parse(require('node:fs').readFileSync({json.dumps(str(cases))}, 'utf8'));\n"
            "process.stdout.write(JSON.stringify(cases.map((k) => needsCare(k.c,\n"
            "  { settings: DEFAULT_SETTINGS, churned: !!k.c.churned_at, booked: k.booked }))));\n",
            encoding="utf-8",
        )
        r = subprocess.run(["node", str(runner)], capture_output=True, text=True, timeout=120)
        return json.loads(r.stdout) if r.returncode == 0 else None


def test_web_rule_matches_python():
    got = _node_results()
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없거나 컴파일 실패 — TS 대조 생략")
    for (name, c, booked, want), web in zip(CASES, got):
        assert web is want, f"[TS] {name}"
        assert web == up.needs_care(c, S, TODAY, booked), f"[TS↔PY 불일치] {name}"
