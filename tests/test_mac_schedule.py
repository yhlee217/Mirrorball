"""맥 스케줄 설치물 — 경로가 plist 에 박히면 또 두 달을 날린다.

2026-08~10: 저장소가 ~/Desktop 에 있어 launchd 가 /bin/bash 를 띄우지 못했고
(TCC → posix_spawn EPERM), 1392번 연속 실패했는데 아무 흔적도 안 남았다.
그때 plist 에는 절대 경로가 직접 적혀 있었다.
"""

from __future__ import annotations

import plistlib
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MAC = ROOT / "scripts" / "mac"
PROTECTED = ("Desktop", "Documents", "Downloads")


def _plists():
    return sorted(MAC.glob("com.mirrorball.*.plist"))


def test_plists_exist():
    assert _plists(), "scripts/mac 에 plist 가 없다"


@pytest.mark.parametrize("p", _plists(), ids=lambda p: p.name)
def test_no_hardcoded_home_path(p: Path):
    """plist 는 {PROJECT}/{LOGS} 자리표만 쓴다 — /Users/<이름> 이 박히면 안 된다."""
    body = re.sub(r"<!--.*?-->", "", p.read_text(encoding="utf-8"), flags=re.S)
    assert "/Users/" not in body, f"{p.name} 에 절대 경로가 박혀 있다 — 자리표를 쓸 것"


@pytest.mark.parametrize("p", _plists(), ids=lambda p: p.name)
def test_plist_is_valid(p: Path):
    d = plistlib.loads(p.read_bytes())
    assert d["Label"].startswith("com.mirrorball.")
    assert d["ProgramArguments"][0] == "/bin/bash"


def test_collect_logs_outside_repo():
    """launchd 는 스크립트 실행 '전에' 이 파일을 연다. 저장소 위치와 묶어두면
    저장소를 보호 폴더로 옮기는 순간 다시 조용히 죽는다."""
    d = plistlib.loads((MAC / "com.mirrorball.collect.plist").read_bytes())
    for k in ("StandardOutPath", "StandardErrorPath"):
        assert d[k].startswith("{LOGS}/"), f"{k} 가 {{LOGS}} 밖을 가리킨다: {d[k]}"


def test_installer_refuses_protected_folder(tmp_path):
    """보호 폴더에서 등록하면 매번 실패한다 — 설치 단계에서 막아야 한다."""
    home = tmp_path / "home"
    repo = home / "Desktop" / "Dev" / "Mirrorball"
    (repo / "scripts" / "mac").mkdir(parents=True)
    for f in ("install_schedule.sh", "com.mirrorball.collect.plist"):
        (repo / "scripts" / "mac" / f).write_bytes((MAC / f).read_bytes())
    r = subprocess.run(["bash", "scripts/mac/install_schedule.sh", "collect"],
                       cwd=repo, env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "보호 폴더" in r.stdout + r.stderr


def test_installer_all_excludes_legacy_daily():
    """'all' 이 v1 레거시(매일 03:10)를 같이 깔면 주 1회 결정이 무의미해진다."""
    sh = (MAC / "install_schedule.sh").read_text(encoding="utf-8")
    all_block = sh.split("all)", 1)[1].split(";;", 1)[0]
    assert "com.mirrorball.collect" in all_block
    assert "com.mirrorball.handsos" not in all_block


@pytest.mark.parametrize("script", ["install_schedule.sh", "relocate.sh"])
def test_shell_syntax(script):
    assert subprocess.run(["bash", "-n", str(MAC / script)]).returncode == 0


def test_relocate_refuses_protected_target(tmp_path):
    home = tmp_path / "home"
    repo = home / "Desktop" / "Mirrorball"
    (repo / "scripts" / "mac").mkdir(parents=True)
    (repo / "scripts" / "mac" / "relocate.sh").write_bytes((MAC / "relocate.sh").read_bytes())
    r = subprocess.run(["bash", "scripts/mac/relocate.sh", str(home / "Documents" / "MB")],
                       cwd=repo, env={"HOME": str(home), "PATH": "/usr/bin:/bin", "YES": "1"},
                       capture_output=True, text=True)
    assert r.returncode != 0
    assert "보호 폴더" in r.stdout + r.stderr
    assert repo.exists(), "거부했는데 원본이 사라졌다"
