"""수집 쉼(COLLECT_PAUSED, 2026-11-23 운영자 결정) — 매일 감시가 수집 · 백업 지연으로 실패 메일을 보내지 않는다.

HandSOS 약관(스크래핑 금지) · 맥 운영 부담으로 운영자가 맥 수집을 멈췄다. 그 전에도 맥이 꺼져 10.21 뒤 수집이 없어
감시가 날마다 실패했다(10.27 ~ 11.22, 27번). 쉬는 동안엔 수집 · 백업 지연은 알림만 — 백업도 맥 수집에 붙어 함께
멈춘다. 화면 오류 · DB 용량은 그대로 실패한다.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("sync_health_check", ROOT / "scripts" / "sync_health_check.py")
shc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shc)

MB = 1048576
ROWS = [{"slug": s, "last_ok": "2026-10-21T07:08:55+00:00", "last_attempt": "2026-10-21T07:08:55+00:00", "days_since": 33.0}
        for s in ("daunbu", "hayewoni", "juhwan")]
HEALTH = [{"slug": "hayewoni", "last_backup": "2026-10-21T07:20:00+00:00", "errors_24h": 0}]


def run(monkeypatch, capsys, paused: str | None, health=HEALTH, db_mb: int = 30) -> tuple[int, str]:
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("BACKUP_REQUIRED_SINCE", "2026-10-20")
    for k in ("COLLECT_PAUSED", "DB_WARN_MB", "DB_LIMIT_MB", "ALERT_WEBHOOK", "STALE_DAYS"):
        monkeypatch.delenv(k, raising=False)
    if paused:
        monkeypatch.setenv("COLLECT_PAUSED", paused)
    answers = {"sync_health": ROWS, "ops_health": health, "ops_db_size": [{"part": "total", "bytes": db_mb * MB}],
               "ops_speed": [], "ops_usage": [], "ops_csp": []}
    monkeypatch.setattr(shc, "fetch", lambda url, key, fn="sync_health": answers[fn])
    code = shc.main()
    return code, capsys.readouterr().out


def test_paused_watch_stays_green_and_says_why(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, "2026-11-23")
    assert code == 0 and "정상 — 모두 기준 안입니다." in out
    assert "수집 쉼 — 11.23부터(운영자 결정) · 수집 · 백업 지연은 실패로 치지 않는다" in out
    assert "  hayewoni     마지막 성공 2026-10-21T07:08:55 (33.0일 전)" in out                 # 매장 줄은 그대로
    for loud in ("일요일 수집 없음", "그 뒤 시도 없음", "X 갱신 지연", "X 운영 기록"):
        assert loud not in out, loud
    assert "! hayewoni: 마지막 백업" in out and "(수집 쉼 동안은 경고만 — 백업도 맥 수집과 함께 멈췄다)" in out


def test_without_pause_it_still_fails_as_before(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, None)
    assert code == 1 and "X 갱신 지연 3곳" in out and "일요일 수집 없음" in out and "X 운영 기록" in out


def test_pause_does_not_hide_screen_errors_or_db_size(monkeypatch, capsys):
    code, out = run(monkeypatch, capsys, "2026-11-23", health=[{**HEALTH[0], "errors_24h": 7}])
    assert code == 1 and "지난 24시간 화면 오류 7건" in out
    code, out = run(monkeypatch, capsys, "2026-11-23", db_mb=431)
    assert code == 1 and "DB 용량 431MB" in out


def test_backup_rule_and_workflow():
    import datetime as dt

    now = dt.datetime(2026, 11, 24, tzinfo=dt.timezone.utc)
    bad, warn = shc.evaluate_ops(HEALTH + [{"slug": "neu", "last_backup": None, "errors_24h": 0}], now, 8, 5, True,
                                 backup_paused=True)
    assert bad == [] and len(warn) == 2                                                     # 기록 없음도 경고만
    bad, _ = shc.evaluate_ops(HEALTH, now, 8, 5, True)
    assert bad and "마지막 백업" in bad[0]                                                   # 쉼이 아니면 그대로 실패
    wf = (ROOT / ".github" / "workflows" / "sync-health.yml").read_text(encoding="utf-8")
    assert "COLLECT_PAUSED: '2026-11-23'" in wf
