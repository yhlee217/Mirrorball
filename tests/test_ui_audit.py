"""UI 측정이 UX 계획 v3 의 목표를 지키는지 — web/scripts/ui-audit(견본으로 그리기 + 폰 크기로 재기).

설명글 비율·작은 글자·대비·회색 글자·첫 화면 줄 수가 목표 밖으로 밀리면 실패한다(measure.py TARGETS).
화면 문구나 배치를 바꿔 목표가 바뀌어야 하면 playbook/UX_PLAN_v3.md 와 TARGETS 를 함께 고친다.
node · web/node_modules · playwright(+chromium) 가 없으면 건너뛴다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
TOOL = WEB / "scripts" / "ui-audit"


def test_ui_meets_v3_targets(tmp_path):
    tsc = WEB / "node_modules" / ".bin" / "tsc"
    if not shutil.which("node") or not tsc.exists():
        pytest.skip("node 또는 web/node_modules 가 없다 — UI 측정 생략")
    pytest.importorskip("playwright.sync_api")

    c = subprocess.run([str(tsc), "-p", str(TOOL / "tsconfig.json"), "--outDir", str(tmp_path / "js")],
                       capture_output=True, text=True, timeout=300)
    assert c.returncode == 0, c.stdout + c.stderr          # 화면 부품이 컴파일되지 않으면 그 자체가 실패
    r = subprocess.run(["node", str(TOOL / "render.cjs"), str(tmp_path)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    if os.environ.get("CI"):
        # 자동 검증(GitHub Actions, 개선 계획 v13 P1) — 글꼴이 다르면 회색 글자 수 · 첫 화면 줄이 흔들려 거짓 실패가 난다.
        # 컴파일 · 그리기는 위에서 확인했고, 재는 것은 작업 환경에서만.
        pytest.skip("자동 검증 — 화면 측정은 작업 환경에서만(글꼴 차이)")
    m = subprocess.run([sys.executable, str(TOOL / "measure.py"), str(tmp_path), "--check"],
                       capture_output=True, text=True, timeout=300)
    if m.returncode == 2:
        pytest.skip("브라우저를 띄우지 못했다 — UI 측정 생략")
    assert m.returncode == 0, m.stdout + m.stderr
