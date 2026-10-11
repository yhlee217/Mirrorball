"""핸드SOS 자가치유(Claude) — 브라우저/CLI 없는 순수 로직 테스트."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("handsos_heal", ROOT / "scripts" / "handsos_heal.py")
heal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(heal)


def test_parse_selectors_from_fenced_yaml():
    out = "찾았어요:\n```yaml\nreport:\n  date_from_sel: '#a'\n  search_js: 'GoSearch()'\n```\n끝."
    d = heal.parse_selectors(out)
    assert d["report"]["date_from_sel"] == "#a" and d["report"]["search_js"] == "GoSearch()"


def test_parse_selectors_plain_yaml():
    d = heal.parse_selectors("report:\n  date_to_sel: '#z'\n")
    assert d["report"]["date_to_sel"] == "#z"


def test_parse_selectors_garbage_returns_empty():
    assert heal.parse_selectors("그냥 설명만 있고 yaml 이 없음") == {}


def test_pick_relevant_html_trims_around_anchor(tmp_path):
    d = tmp_path / "fail_x"
    d.mkdir()
    (d / "page0.html").write_text("A" * 8000 + "<input id='strDateS'>" + "B" * 8000, encoding="utf-8")
    h = heal.pick_relevant_html(d, budget=2000)
    assert "strDateS" in h and len(h) <= 2000          # 앵커 주변만, 예산 내


def test_build_prompt_contains_asks():
    p = heal.build_prompt("demo", "<html>x</html>", "no-table")
    assert "셀렉터" in p and "yaml" in p and "no-table" in p


def test_find_latest_fail_picks_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(heal, "ROOT", tmp_path)
    base = tmp_path / "clients" / "demo" / "_raw"
    base.mkdir(parents=True)
    (base / "fail_20260101-000000").mkdir()
    (base / "fail_20260102-120000").mkdir()
    assert heal.find_latest_fail("demo").name == "fail_20260102-120000"


def test_find_latest_fail_none(tmp_path, monkeypatch):
    monkeypatch.setattr(heal, "ROOT", tmp_path)
    assert heal.find_latest_fail("nope") is None


# ── claude CLI 실행 위치 ────────────────────────────────────────────────
# 저장소 안에서 부르면 Stop hook(.claude/settings.json)이 끼어들어 답이 '완료'로 바뀌고,
# YAML 이 없어 '제안 파싱 실패'로 끝난다. 실제 CLI 는 안 부르고 subprocess 만 가로챈다.

def test_run_claude_runs_outside_repo(monkeypatch, tmp_path):
    monkeypatch.setattr(heal.tempfile, "gettempdir", lambda: str(tmp_path))
    seen = []

    def fake_run(cmd, **kw):
        seen.append(kw)
        return heal.subprocess.CompletedProcess(cmd, 0, stdout="```yaml\nreport: {}\n```", stderr="")

    monkeypatch.setattr(heal.subprocess, "run", fake_run)
    assert heal.run_claude("셀렉터 찾아줘").startswith("```yaml")
    cwd = Path(seen[0]["cwd"]).resolve()
    assert cwd == (tmp_path / "mirrorball-claude-cli").resolve() and cwd.is_dir()
    assert ROOT.resolve() not in [cwd, *cwd.parents]


def test_same_dedicated_dir_as_worker(monkeypatch, tmp_path):
    """자가치유와 워커가 같은 전용 폴더를 쓴다 — 여러 벌이라 한쪽만 바뀌는 걸 막는다."""
    import sys
    sys.path.insert(0, str(ROOT / "worker"))
    import claude_cli
    monkeypatch.setattr(heal.tempfile, "gettempdir", lambda: str(tmp_path))
    assert heal._cli_cwd() == claude_cli.cli_cwd()


def test_hijacked_answer_is_reported_not_applied():
    """hook 이 끼어 '완료'만 돌아오면 셀렉터를 바꾸지 않고 파싱 실패로 끝나야 한다."""
    assert heal.parse_selectors("완료") == {}
