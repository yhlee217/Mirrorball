#!/usr/bin/env python3
"""launchd plist 생성 — Mirrorball 10분 배치 스케줄.

macOS launchd 의 StartInterval(고정 간격)은 시계에 정렬되지 않아 '정시 23:00' 같은
지점을 맞추기 어렵다. 그래서 StartCalendarInterval(정확한 시:분) 배열로 굽는다.

스케줄:
  · 영업시간 10:00~20:00 매 10분 (10~19시 :00/10/20/30/40/50, 그리고 20:00)
  · 추가 단발 23:00, 06:00, 08:00

사용(맥에서):
  .venv/bin/python scripts/make_launchd_plist.py > ~/Library/LaunchAgents/com.mirrorball.batch.plist
  launchctl unload ~/Library/LaunchAgents/com.mirrorball.batch.plist 2>/dev/null
  launchctl load  ~/Library/LaunchAgents/com.mirrorball.batch.plist

경로(런너·로그)는 이 스크립트 위치에서 자동 계산 → 맥에서 실행하면 그 맥 경로로 구워진다.
로그: _raw/batch.out.log / _raw/batch.err.log (gitignore).
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape

LABEL = "com.mirrorball.batch"
ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "scripts" / "mirrorball_batch.sh"
PATH_ENV = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"


def schedule() -> list[tuple[int, int]]:
    """(시, 분) 목록 — 영업시간(10~20시) 10분 간격 + 단발 3회(23·06·08시)."""
    out: list[tuple[int, int]] = []
    for h in range(10, 20):                       # 10~19시: 매 10분
        for m in (0, 10, 20, 30, 40, 50):
            out.append((h, m))
    out.append((20, 0))                           # 20:00 (영업 마감 정각)
    for h in (23, 6, 8):                          # 야간/아침 단발
        out.append((h, 0))
    return out


def build_plist() -> str:
    cal = "\n".join(
        "    <dict>\n"
        f"      <key>Hour</key><integer>{h}</integer>\n"
        f"      <key>Minute</key><integer>{m}</integer>\n"
        "    </dict>"
        for h, m in schedule())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>{escape(str(RUNNER))}</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>{PATH_ENV}</string>
  </dict>
  <key>StartCalendarInterval</key>
  <array>
{cal}
  </array>
  <key>StandardOutPath</key><string>{escape(str(ROOT / "_raw" / "batch.out.log"))}</string>
  <key>StandardErrorPath</key><string>{escape(str(ROOT / "_raw" / "batch.err.log"))}</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
"""


if __name__ == "__main__":
    sys.stdout.write(build_plist())
