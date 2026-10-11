"""claude CLI 는 저장소 밖에서 돌아야 한다.

저장소에 Stop hook(.claude/settings.json → .claude/hooks/auto_continue.py)이 있다.
claude -p 를 저장소 안에서 부르면 배치마다 hook 이 끼어들어, 마지막 답이 JSON 요약 대신
'완료'가 되어 메모 정리 파싱이 깨질 수 있다. 실제 CLI 는 부르지 않고 subprocess 만 가로챈다.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import claude_cli  # noqa: E402


@pytest.fixture
def calls(monkeypatch, tmp_path):
    # 실제 임시 폴더에 흔적을 남기지 않도록 테스트 동안만 tmp_path 로 돌린다
    monkeypatch.setattr(claude_cli.tempfile, "gettempdir", lambda: str(tmp_path))
    seen = []

    def fake_run(cmd, **kw):
        seen.append(kw)
        out = json.dumps({"result": "ok", "usage": {}}) if "--output-format" in cmd else "안녕"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(claude_cli.subprocess, "run", fake_run)
    return seen, tmp_path


def test_run_claude_runs_in_dedicated_dir(calls):
    seen, tmp = calls
    assert claude_cli.run_claude("요약해줘") == ("ok", "")
    assert seen and all(kw.get("cwd") == str(tmp / "mirrorball-claude-cli") for kw in seen)
    assert Path(seen[0]["cwd"]).is_dir()


def test_check_cli_runs_in_dedicated_dir(calls, capsys):
    seen, tmp = calls
    assert claude_cli.check_cli() == 0
    assert seen[0]["cwd"] == str(tmp / "mirrorball-claude-cli")
    assert "실행 위치" in capsys.readouterr().out


def test_real_tempdir_is_outside_repo_and_sees_no_project_settings():
    """실제로 쓰일 임시 폴더가 저장소 밖이고, 그 위로 어떤 .claude/settings.json 도 없어야 한다."""
    t = Path(tempfile.gettempdir()).resolve()
    chain = [t, *t.parents]
    assert ROOT.resolve() not in chain, f"임시 폴더가 저장소 안: {t}"
    assert not [d for d in chain if (d / ".claude" / "settings.json").exists()]


def test_check_cli_warns_when_answer_is_hijacked(monkeypatch, tmp_path, capsys):
    """CHECK=1 이 이 실패를 스스로 알려주는지 — hook 이 끼면 '안녕' 대신 '완료'가 온다."""
    monkeypatch.setattr(claude_cli.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(claude_cli.subprocess, "run",
                        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="완료\n", stderr=""))
    claude_cli.check_cli()
    assert "Stop hook" in capsys.readouterr().out
