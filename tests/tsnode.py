"""web/lib 의 TS 함수를 테스트에서 실행한다 — tsc 로 CommonJS 로 뽑아 node 로 돌린다.

test_rules_parity · test_care_rule 과 같은 방식을 한 곳에 모았다. node·npx·web/node_modules 가
없으면 None 을 돌려주고 호출 쪽이 skip 한다(파이썬만 있는 환경에서도 나머지 테스트는 돈다).
도구가 다 있는데 컴파일이 깨지면 그건 코드 문제라 건너뛰지 않고 실패시킨다.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


def run_ts(files: list[str], script: str, data: object) -> object | None:
    """files(web 기준 경로)를 컴파일하고 script 를 실행해 그 결과(JSON)를 돌려준다.

    script 안에서는 `D` 로 data 를 받고 `out(x)` 로 결과를 낸다. require 는 lib 파일 이름으로
    (예: require('./week.js')).
    """
    if not shutil.which("node") or not shutil.which("npx"):
        return None
    if not (WEB / "node_modules" / "typescript").exists():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        # CommonJS 로 뽑는다 — Node ESM 은 확장자 없는 import 와 JSON import 를 거부한다.
        c = subprocess.run(
            ["npx", "tsc", *files, "--outDir", tmp, "--module", "commonjs", "--target", "es2020",
             "--esModuleInterop", "--resolveJsonModule", "--skipLibCheck"],
            cwd=WEB, capture_output=True, text=True, timeout=300,
        )
        if c.returncode != 0:
            raise AssertionError("tsc 컴파일 실패:\n" + c.stdout + c.stderr)
        (Path(tmp) / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        runner = Path(tmp) / "run.cjs"
        runner.write_text(
            "const D = JSON.parse(require('node:fs').readFileSync(__dirname + '/data.json', 'utf8'));\n"
            "const out = (x) => process.stdout.write(JSON.stringify(x));\n" + script,
            encoding="utf-8",
        )
        r = subprocess.run(["node", str(runner)], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise AssertionError("node 실행 실패:\n" + r.stderr)
        return json.loads(r.stdout)
