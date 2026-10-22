"""맥을 켤 때 밀린 수집(worker/catchup.py, 2026-10-21) — 네트워크 · 맥 없이.

10.18 일요일 14시에 맥이 꺼져 있어 그 주 수집이 통째로 빠졌다(launchd 는 꺼진 동안의 예약을 다시 켜도 돌리지 않는다).
로그인할 때 마지막 일요일 수집 차례(일 14:00) 뒤로 성공이 없으면 평소 수집을 한 번 돌린다. 밀린 주만 — '주 1회'는 그대로.
실패했으면 하루 한 번까지만, 일요일 수집이 돌고 있거나 2시간 안에 돌 차례면 건너뛴다.
첫 판은 '마지막 성공이 7일 넘었나'로 봐서 주중(10.21 수요일)에 수동 수집을 한 다음 주를 놓쳤다(10.22 발견).
"""

from __future__ import annotations

import datetime as dt
import plistlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import catchup as cu  # noqa: E402

NOW = dt.datetime(2026, 10, 21, 8, 0, tzinfo=dt.timezone.utc)   # 수요일 17시(KST)
H = dt.timedelta(hours=1)
D = dt.timedelta(days=1)


def kst(m: int, d: int, h: int, mi: int = 0) -> dt.datetime:
    return dt.datetime(2026, m, d, h, mi, tzinfo=cu.KST)


def test_decide_runs_only_for_a_missed_week():
    sun = kst(10, 11, 14, 5)                                                    # 10.11 일요일 수집 성공
    run, why = cu.decide(sun, sun, NOW)                                         # 10.18 일요일에 꺼져 있었다 — 이번 일
    assert run and "10.1일 전" in why and "10.18 일요일 수집 차례를 놓쳤다" in why
    run, why = cu.decide(kst(10, 18, 14, 5), kst(10, 18, 14, 5), NOW)           # 일요일 수집이 돌았다 — 평소
    assert not run and "밀리지 않았다" in why
    assert not cu.decide(kst(10, 18, 14, 5), kst(10, 18, 14, 5), kst(10, 25, 13, 30))[0]   # 이번 일요일 차례 전에 켬
    assert cu.decide(None, None, NOW)[0]                                        # 처음 — 기록 없음


def test_decide_counts_missed_sundays_not_days():
    """주중에 수동 · 밀린 수집이 돈 다음 주. '7일 넘었나'로 보면 월 · 화요일엔 건너뛰고 수요일 16시에야 돌았다."""
    wed = kst(10, 21, 16, 8)                                                    # 10.21 수요일 수동 수집
    run, why = cu.decide(wed, wed, kst(10, 26, 9))                              # 10.25 일요일에 꺼짐 → 월요일 아침에 켬
    assert run and "4.7일 전" in why and "10.25 일요일" in why
    assert cu.decide(wed, wed, kst(10, 27, 21))[0]                              # 화요일 밤에 켜도
    assert cu.decide(wed, wed, kst(10, 25, 15))[0]                              # 일요일 15시에 켬 — 14시엔 꺼져 있었다
    assert not cu.decide(wed, wed, kst(10, 24, 20))[0]                          # 토요일 — 아직 차례 전
    run, why = cu.decide(kst(10, 11, 14, 5), kst(10, 11, 14, 5), kst(10, 25, 13))   # 밀렸어도 곧 일요일 수집 차례
    assert not run and "60분 뒤 — 그쪽에 맡긴다" in why
    assert cu.decide(kst(10, 11, 14, 5), kst(10, 11, 14, 5), kst(10, 25, 11, 59))[0]   # 2시간보다 많이 남았으면 지금


def test_slot_is_the_weekly_collection_time():
    cal = plistlib.loads((ROOT / "scripts" / "mac" / "com.mirrorball.collect.plist").read_bytes())["StartCalendarInterval"]
    assert (cal["Weekday"] % 7, cal["Hour"], cal.get("Minute", 0)) == ((cu.SLOT_WEEKDAY + 1) % 7, cu.SLOT_HOUR, 0)   # launchd 일=0
    assert cu.last_slot(NOW) == kst(10, 18, 14)
    assert cu.last_slot(kst(10, 25, 13, 59)) == kst(10, 18, 14) and cu.last_slot(kst(10, 25, 14)) == kst(10, 25, 14)
    assert cu.last_slot(dt.datetime(2026, 10, 25, 5, 0, tzinfo=dt.timezone.utc)) == kst(10, 25, 14)   # UTC 로 줘도 KST 로


def test_decide_retries_a_failed_week_once_a_day():
    run, why = cu.decide(NOW - 10 * D, NOW - 3 * H, NOW)                        # 3시간 전에 돌다 실패
    assert not run and "하루 한 번까지만" in why
    assert cu.decide(NOW - 10 * D, NOW - 21 * H, NOW)[0]                       # 하루가 지나면 다시
    assert not cu.decide(None, NOW - 1 * H, NOW)[0]                            # 성공 기록 없이 실패만 — 그래도 하루 한 번
    assert not cu.decide(NOW - 1 * H, NOW - 1 * H, NOW)[0]                      # 방금 성공 — 마지막 시도가 그 성공


def _fake(monkeypatch, last=None, running=False, fails=0):
    calls = {"collect": 0, "reads": 0}

    def last_times():
        calls["reads"] += 1
        if calls["reads"] <= fails:
            raise RuntimeError("network down")
        return last

    monkeypatch.setattr(cu, "_last_times", last_times)
    monkeypatch.setattr(cu, "_running", lambda: running)
    monkeypatch.setattr(cu, "_collect", lambda: calls.__setitem__("collect", calls["collect"] + 1) or 0)
    monkeypatch.setattr(cu, "_now", lambda: NOW)                                # 요일에 따라 결과가 바뀌지 않게
    monkeypatch.setattr(cu.time, "sleep", lambda s: None)
    monkeypatch.delenv("CATCHUP_DRY", raising=False)
    return calls


def test_main_runs_the_usual_collection_when_missed(monkeypatch, capsys):
    old = NOW - 10 * D
    calls = _fake(monkeypatch, last=(old, old))
    assert cu.main() == 0 and calls["collect"] == 1
    out = capsys.readouterr().out
    assert "[catchup] 마지막 성공 10.0일 전" in out and "밀린 수집 시작" in out and "밀린 수집 종료(exit=0)" in out


def test_main_skips_when_fresh_running_or_dry(monkeypatch, capsys):
    fresh = NOW - 2 * D
    calls = _fake(monkeypatch, last=(fresh, fresh))
    assert cu.main() == 0 and calls["collect"] == 0
    old = NOW - 10 * D
    calls = _fake(monkeypatch, last=(old, old), running=True)
    assert cu.main() == 0 and calls["collect"] == 0 and "이미 돌고 있다" in capsys.readouterr().out
    calls = _fake(monkeypatch, last=(old, old))
    monkeypatch.setenv("CATCHUP_DRY", "1")
    assert cu.main() == 0 and calls["collect"] == 0 and "판단만" in capsys.readouterr().out


def test_main_waits_for_network_then_gives_up_quietly(monkeypatch, capsys):
    old = NOW - 10 * D
    calls = _fake(monkeypatch, last=(old, old), fails=3)                       # 로그인 직후 와이파이가 늦다
    assert cu.main() == 0 and calls["reads"] == 4 and calls["collect"] == 1
    calls = _fake(monkeypatch, last=(old, old), fails=99)                      # 끝내 안 되면 다음 로그인 때
    assert cu.main() == 0 and calls["reads"] == cu.NET_TRIES and calls["collect"] == 0
    assert "다음 로그인 때" in capsys.readouterr().out


def test_agent_runs_at_login_and_shares_the_collect_log():
    d = plistlib.loads((ROOT / "scripts" / "mac" / "com.mirrorball.catchup.plist").read_bytes())
    assert d["Label"] == "com.mirrorball.catchup" and d["RunAtLoad"] is True
    assert "StartCalendarInterval" not in d and "StartInterval" not in d                    # 로그인할 때만
    assert d["ProgramArguments"] == ["/bin/bash", "{PROJECT}/worker/run_catchup.sh"]
    assert d["StandardOutPath"] == "{LOGS}/collect.out.log"                                 # 한 곳만 보면 된다
    sh = (ROOT / "worker" / "run_catchup.sh").read_text(encoding="utf-8")
    assert 'exec "$ROOT/.venv/bin/python" worker/catchup.py' in sh
    src = (ROOT / "worker" / "catchup.py").read_text(encoding="utf-8")
    assert '"worker" / "run_mac.sh"' in src and "pgrep" in src                              # 평소 수집 그대로 · 겹치지 않게


def test_installer_puts_catchup_with_the_weekly_collection():
    sh = (ROOT / "scripts" / "mac" / "install_schedule.sh").read_text(encoding="utf-8")
    collect = sh.split("  collect)", 1)[1].split(";;", 1)[0]
    assert "com.mirrorball.collect" in collect and "com.mirrorball.catchup" in collect
    assert "_uninstall com.mirrorball.catchup" in sh.split("uninstall)", 1)[1].split(";;", 1)[0]
    reloc = (ROOT / "scripts" / "mac" / "relocate.sh").read_text(encoding="utf-8")
    assert "com.mirrorball.catchup" in reloc.split('AGENTS="', 1)[1].split('"', 1)[0]


def test_installer_really_writes_and_loads_both_agents(tmp_path):
    """맥 없이 — 가짜 launchctl 로 '일요일 수집 + 밀린 수집'이 함께 깔리고 자리표가 채워지는지 본다."""
    import shutil
    import subprocess

    home = tmp_path / "home"
    repo = home / "Dev" / "Mirrorball"
    shutil.copytree(ROOT / "scripts" / "mac", repo / "scripts" / "mac")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    log = tmp_path / "launchctl.log"
    (fake_bin / "launchctl").write_text(f'#!/bin/sh\necho "$@" >> "{log}"\n', encoding="utf-8")
    (fake_bin / "launchctl").chmod(0o755)
    r = subprocess.run(["bash", "scripts/mac/install_schedule.sh", "collect"], cwd=repo,
                       env={"HOME": str(home), "PATH": f"{fake_bin}:/usr/bin:/bin"}, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    la = home / "Library" / "LaunchAgents"
    for label in ("com.mirrorball.collect", "com.mirrorball.catchup"):
        d = plistlib.loads((la / f"{label}.plist").read_bytes())
        assert d["ProgramArguments"][1].startswith(str(repo)) and "{" not in d["StandardOutPath"]
        assert f"load {la / (label + '.plist')}" in log.read_text(encoding="utf-8")
    catch = plistlib.loads((la / "com.mirrorball.catchup.plist").read_bytes())
    assert catch["StandardOutPath"] == str(home / "Library" / "Logs" / "Mirrorball" / "collect.out.log")
