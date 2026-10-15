"""운영 의존성 주간 점검(scripts/deps_audit.py, 개선 계획 v14 P2) — 받아들이지 않은 높음 · 심각이면 실패.

알고 받아들인 것(빌드 도구 postcss — 바깥 입력이 닿지 않음)만으로는 실패하지 않아야 매주 빨간불에 새 알림이 묻히지 않는다.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("deps_audit", ROOT / "scripts" / "deps_audit.py")
da = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(da)

ADV = lambda title: {"title": title, "url": "https://github.com/advisories/x", "severity": "high"}   # noqa: E731
NOW = {  # 2026-10-15 Next 15.5.28 로 올린 뒤의 모양
    "vulnerabilities": {
        "postcss": {"severity": "high", "via": [ADV("PostCSS sourceMappingURL")]},
        "next": {"severity": "moderate", "via": ["postcss"]},
    },
    "metadata": {"vulnerabilities": {"critical": 0, "high": 1, "moderate": 1, "low": 0}},
}


def test_accepted_build_tool_alone_passes():
    bad, ok = da.judge(NOW)
    assert bad == [] and ok and ok[0].startswith("postcss(high)")


def test_new_high_or_critical_fails():
    new = json.loads(json.dumps(NOW))
    new["vulnerabilities"]["undici"] = {"severity": "high", "via": [ADV("undici request smuggling")]}
    new["vulnerabilities"]["next"] = {"severity": "critical", "via": [ADV("RSC DoS"), "postcss"]}
    bad, _ = da.judge(new)
    assert [b.split("(")[0] for b in bad] == ["next", "undici"]                 # 자기 알림이 있는 next 는 실패


def test_only_via_accepted_is_accepted():
    via_only = json.loads(json.dumps(NOW))
    via_only["vulnerabilities"]["next"] = {"severity": "high", "via": ["postcss"]}
    bad, ok = da.judge(via_only)
    assert bad == [] and any(x.startswith("next(high) — postcss 때문에만") for x in ok)


def test_main_exit_codes(tmp_path, capsys):
    good = tmp_path / "good.json"
    good.write_text(json.dumps(NOW), encoding="utf-8")
    assert da.main(["x", str(good)]) == 0
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"error": {"code": "ENOLOCK"}}), encoding="utf-8")
    assert da.main(["x", str(broken)]) == 2                                     # 결과가 이상하면 '점검 실패'
    assert "결과가 이상해요" in capsys.readouterr().out


def test_workflow_runs_weekly_without_secrets():
    wf = (ROOT / ".github" / "workflows" / "deps-audit.yml").read_text(encoding="utf-8")
    assert "cron: '30 1 * * 1'" in wf and "python3 scripts/deps_audit.py" in wf
    assert "secrets." not in wf and "contents: read" in wf
