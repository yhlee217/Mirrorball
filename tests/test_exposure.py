"""노출 데이터 — diagnose.exposure_from_records + build_app 주입."""

import diagnose


def test_exposure_from_records_counts_mentions():
    records = [
        {"question": "Q1", "engine": "openai", "extraction": {"mentioned": True}},
        {"question": "Q1", "engine": "gemini", "extraction": {"mentioned": False}},
        {"question": "Q1", "engine": "openai", "extraction": {"mentioned": True}},  # 샘플2
        {"question": "Q2", "engine": "openai", "extraction": {"mentioned": False}},
        {"question": "Q3", "engine": "openai", "error": "x", "extraction": None},
    ]
    e = diagnose.exposure_from_records(records, generated="2026-06-23")
    assert e["score"] == 2                          # Q1 에서 2회 언급
    qmap = {q["q"]: q["count"] for q in e["questions"]}
    assert qmap == {"Q1": 2, "Q2": 0, "Q3": 0}
    assert e["generated"] == "2026-06-23"


def test_build_app_injects_exposure(tmp_path):
    import build_app
    cdir = tmp_path / "clients" / "demo"
    (cdir / "customers").mkdir(parents=True)
    (cdir / "config.yaml").write_text("slug: demo\ntoday: 2026-06-23\n", encoding="utf-8")
    (cdir / "exposure.yaml").write_text(
        "score: 5\ngenerated: 2026-06-23\nquestions:\n  - q: 'Q'\n    count: 2\n",
        encoding="utf-8",
    )
    build_app.build_one(str(cdir), dist=str(tmp_path / "out"))
    import json
    d = json.loads((tmp_path / "out" / "demo.json").read_text(encoding="utf-8"))
    assert d["exposure"]["score"] == 5
    assert d["exposure"]["questions"][0]["q"] == "Q"
