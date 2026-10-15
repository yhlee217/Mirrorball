"""브라우저 테스트가 쓰는 크롬 — playwright 가 기본으로 찾는 크롬이 없으면 이 환경에 깔린 크롬으로(개선 계획 v12 P3).

파이썬 playwright 판이 바라는 크롬(chromium_headless_shell-NNNN)과 깔려 있는 크롬 판이 다르면 기본 실행이 실패해,
원장 앱(MVP, app/index.html) 브라우저 테스트 22개가 매번 '건너뜀'으로 끝났다 — 깨져도 몰랐다. 깔린 크롬으로 돌리면
모두 통과한다. 어느 크롬도 없으면 지금처럼 건너뛴다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FALLBACKS = (
    Path("/opt/pw-browsers/chromium"),
    Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome"),
)


def launch_chromium(p):
    try:
        return p.chromium.launch()
    except Exception as exc:  # noqa: BLE001 — 판이 안 맞거나 크롬이 없다
        for exe in FALLBACKS:
            if exe.exists():
                return p.chromium.launch(executable_path=str(exe))
        pytest.skip(f"chromium 실행 불가: {exc}")
