#!/usr/bin/env python3
"""Mirrorball 운영 원커맨드 래퍼.

컨시어지 1인이 반복 작업을 한 줄로 실행하기 위한 얇은 디스패처.
각 하위 명령은 기존 스크립트(build.py / cards.py / diagnose.py / copygen.py)를
그대로 호출한다 — 로직 중복 없이 운영 진입점만 모은다.

사용법:
    python ops.py build [--all|designers/{slug}.yaml]   프로필 정적 빌드 → dist/
    python ops.py build-app [--all|clients/{slug}]       원장앱 데이터 빌드 → dist_app/
    python ops.py cards <example.yaml>                   카드 빌드
    python ops.py diagnose <target.yaml>                 AI 노출 진단(로컬, 키 필요)
    python ops.py copy <input.yaml>                      카피 생성(로컬)
    python ops.py check                                  테스트 전체 실행
    python ops.py status                                 운영 현황(디자이너 수·빌드물)

설계 원칙: 고객에게 자동 발송하지 않는다. diagnose/copy 는 컨시어지 손에서만 돈다.
"""

from __future__ import annotations

import glob
import subprocess
import sys
from pathlib import Path

PY = sys.executable


def _run(cmd: list[str]) -> int:
    print("· " + " ".join(cmd))
    return subprocess.call(cmd)


def cmd_build(rest: list[str]) -> int:
    target = rest[0] if rest else "--all"
    return _run([PY, "build.py", target])


def cmd_build_app(rest: list[str]) -> int:
    target = rest[0] if rest else "--all"
    return _run([PY, "build_app.py", target])


def cmd_cards(rest: list[str]) -> int:
    if not rest:
        return _run([PY, "cards.py"])  # cards.py 자체 사용법 출력
    return _run([PY, "cards.py", *rest])


def cmd_diagnose(rest: list[str]) -> int:
    if not rest:
        print("사용법: python ops.py diagnose <target.yaml>")
        return 2
    return _run([PY, "diagnose.py", *rest])


def cmd_copy(rest: list[str]) -> int:
    if not rest:
        print("사용법: python ops.py copy <input.yaml>")
        return 2
    return _run([PY, "copygen.py", *rest])


def cmd_check(_rest: list[str]) -> int:
    return _run([PY, "-m", "pytest", "-q"])


def cmd_status(_rest: list[str]) -> int:
    designers = sorted(glob.glob("designers/*.yaml"))
    built = sorted(glob.glob("dist/*/index.html"))
    print(f"디자이너 정의: {len(designers)}")
    for d in designers:
        print(f"  - {Path(d).stem}")
    print(f"빌드된 프로필: {len(built)}")
    for b in built:
        print(f"  - {b}")
    if not built:
        print("  (아직 빌드 없음 → python ops.py build --all)")
    return 0


COMMANDS = {
    "build": cmd_build,
    "build-app": cmd_build_app,
    "cards": cmd_cards,
    "diagnose": cmd_diagnose,
    "copy": cmd_copy,
    "check": cmd_check,
    "status": cmd_status,
}


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    name, rest = args[0], args[1:]
    fn = COMMANDS.get(name)
    if not fn:
        print(f"알 수 없는 명령: {name}\n")
        print(__doc__)
        return 2
    return fn(rest)


if __name__ == "__main__":
    raise SystemExit(main())
