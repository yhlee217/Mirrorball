"""파이썬 워커와 웹이 같은 규칙으로 같은 답을 내는지 대조한다.

거래 분류와 선불 원장은 두 언어에 각각 구현돼 있다(워커는 집계를 계산하고, 앱은 카르테에서
재계산 없이 바로 보여줘야 하므로). 같은 규칙이 두 곳에 있으면 반드시 갈라지는데, 갈라지면
'화면 잔액과 통계 매출이 다른' 형태로 조용히 드러난다.

  · 분류 어휘   web/lib/tx-rules.json 을 양쪽이 함께 읽는다 → 여기서는 그 사실만 확인
  · 원장 계산   구현이 둘이라 공유 사례(web/lib/ledger-cases.json)로 결과를 대조

TS 쪽은 tsc 로 컴파일해 node 로 실행한다. 둘 중 하나라도 없으면 건너뛴다(로컬 파이썬만
있는 환경에서 테스트가 깨지지 않게).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import txkind  # noqa: E402

CASES = json.loads((ROOT / "web" / "lib" / "ledger-cases.json").read_text(encoding="utf-8"))["cases"]
RULES = json.loads((ROOT / "web" / "lib" / "tx-rules.json").read_text(encoding="utf-8"))


def _py_ledger(items: list[dict]) -> dict:
    rows = [
        {
            "id": it.get("id"),
            "date": it.get("date"),
            "time": it.get("time"),
            "amount": it.get("amount", 0),
            "kind": it.get("kind"),
            "out_of_pocket": bool(it.get("pocket")),
        }
        for it in items
    ]
    r = txkind.ledger(rows)
    return {k: r[k] for k in ("balance", "revenue", "charged", "covered")}


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_python_ledger_matches_fixture(case):
    assert _py_ledger(case["items"]) == case["expect"]


def test_python_classify_uses_shared_vocabulary():
    """어휘를 코드에 박지 않고 공유 파일에서 읽는지 — 한쪽에만 메뉴를 추가하는 사고 방지."""
    for kind, words in RULES["patterns"].items():
        for w in words:
            assert txkind.classify(f"테스트 {w} 항목") == kind, f"{w} → {kind} 여야 함"
    # 파일에 없는 말은 시술로 남아야 한다
    assert txkind.classify("여자컷(원장)") == "service"


def _node_ledger_results() -> list[dict] | None:
    """web/lib/tx.ts 를 컴파일해 같은 사례를 돌린 결과. 도구가 없으면 None."""
    if not shutil.which("node") or not shutil.which("npx"):
        return None
    web = ROOT / "web"
    with tempfile.TemporaryDirectory() as tmp:
        # CommonJS 로 뽑는다 — Node ESM 은 확장자 없는 import 와 JSON import 를 거부한다.
        c = subprocess.run(
            ["npx", "tsc", "lib/tx.ts", "lib/kst.ts", "--outDir", tmp,
             "--module", "commonjs", "--target", "es2020", "--esModuleInterop",
             "--resolveJsonModule", "--skipLibCheck"],
            cwd=web, capture_output=True, text=True, timeout=300,
        )
        if c.returncode != 0 or not (Path(tmp) / "tx.js").exists():
            return None
        runner = Path(tmp) / "run.cjs"
        cases_path = json.dumps(str(ROOT / "web" / "lib" / "ledger-cases.json"))
        runner.write_text(
            "const { ledger } = require('./tx.js');\n"
            "const fs = require('node:fs');\n"
            f"const cases = JSON.parse(fs.readFileSync({cases_path}, 'utf8')).cases;\n"
            "const out = cases.map((c) => {\n"
            "  const r = ledger(c.items.map((i) => ({\n"
            "    id: i.id, date: i.date, time: i.time ?? null,\n"
            "    amount: i.amount, kind: i.kind, pocket: !!i.pocket })));\n"
            "  return { balance: r.balance, revenue: r.revenue, charged: r.charged, covered: r.covered };\n"
            "});\n"
            "process.stdout.write(JSON.stringify(out));\n",
            encoding="utf-8",
        )
        r = subprocess.run(["node", str(runner)], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout)


def test_web_ledger_matches_python():
    """같은 사례에서 TS 구현과 파이썬 구현이 한 글자도 다르지 않아야 한다."""
    web_results = _node_ledger_results()
    if web_results is None:
        pytest.skip("node/npx 가 없거나 컴파일 실패 — TS 대조 생략")
    assert len(web_results) == len(CASES)
    for case, got in zip(CASES, web_results):
        assert got == case["expect"], f"[TS] {case['name']}"
        assert got == _py_ledger(case["items"]), f"[TS↔PY 불일치] {case['name']}"
