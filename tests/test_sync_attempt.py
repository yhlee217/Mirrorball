"""매일 감시 — 수집이 밀렸을 때 '시작도 안 했나 · 돌다 실패했나'를 가른다(2026-10-20).

10.18 일요일 수집이 안 돌아 10.19 · 10.20 감시가 실패했는데, 출력엔 '마지막 성공'만 있어 맥이 꺼져 있었는지(시도 없음)
수집이 실패했는지(시도 있음) 알 수 없었다. 로그 위치 안내도 옮기기 전 경로(runs/)로 남아 있었다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("sync_health_check", ROOT / "scripts" / "sync_health_check.py")
shc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shc)


def test_line_tells_no_attempt_from_failed_attempt():
    never = {"slug": "hayewoni", "last_ok": "2026-10-11T05:01:03+00:00", "last_attempt": "2026-10-11T05:01:03+00:00",
             "days_since": 9.0}
    failed = {"slug": "juhwan", "last_ok": "2026-10-11T05:01:07.5+00:00", "last_attempt": "2026-10-18T05:03:41.2+00:00",
              "days_since": 9.0}
    fresh = {"slug": "daunbu", "last_ok": "2026-10-18T05:01:10+00:00", "last_attempt": "2026-10-18T05:01:10+00:00",
             "days_since": 2.0}
    assert shc._fmt(never, 8).endswith("· 그 뒤 시도 없음")
    assert shc._fmt(failed, 8).endswith("· 마지막 시도 10.18 14:03(KST) 실패")
    assert "시도" not in shc._fmt(fresh, 8)
    assert "시도" not in shc._fmt({"slug": "x", "last_ok": None, "last_attempt": None, "days_since": None}, 8)


def test_hints_point_to_the_real_log_and_manual_run():
    src = (ROOT / "scripts" / "sync_health_check.py").read_text(encoding="utf-8")
    main = src[src.index("def main"):]
    assert "tail -40 ~/Library/Logs/Mirrorball/collect.out.log" in main and "runs/collect.out.log" not in main
    assert "FORCE=1 bash worker/run_mac.sh" in main and "print(_fmt(r, stale_days))" in main
    deploy = (ROOT / "DEPLOY.md").read_text(encoding="utf-8")
    assert "~/Library/Logs/Mirrorball/collect.out.log" in deploy                              # 안내서와 같은 경로
