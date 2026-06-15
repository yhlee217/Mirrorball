"""content.py — 인용 콘텐츠 생성 (engines.complete 를 fake 로, 네트워크 없음)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import content  # noqa: E402
import engines  # noqa: E402

DATA = {
    "slug": "minji",
    "display_name": "Minji",
    "korean_name": "김 민 지",
    "salon": "살롱드헤어 강남점",
    "region": "강남역",
    "specialties": [{"name": "발레아주", "desc": "그라데이션 컬러"},
                    {"name": "디지털펌", "desc": "열펌"}],
    "about": ["청담 5년"],
    "faq": [{"q": "발레아주는 얼마나 유지되나요?", "a": "3~4개월 유지됩니다."}],
}


def test_render_prompt_contains_fields():
    p = content.render_prompt(DATA)
    assert "Minji" in p and "살롱드헤어 강남점" in p
    assert "강남역" in p
    assert "발레아주" in p and "디지털펌" in p
    assert "발레아주는 얼마나 유지되나요?" in p  # FAQ 주제로 포함


def test_render_prompt_optional_region_absent():
    d = dict(DATA)
    del d["region"]
    p = content.render_prompt(d)
    assert "지역:" not in p  # region 없으면 표기 안 함


def test_generate_content_uses_provider(monkeypatch):
    captured = {}

    async def fake_complete(provider, prompt, models=None, timeout=60.0):
        captured.update(provider=provider, models=models, prompt=prompt)
        return "  # 블로그 글\n본문  "

    monkeypatch.setattr(engines, "complete", fake_complete)
    for env in ("REPORT_PROVIDER", "REPORT_MODEL", "GEMINI_MODEL"):
        monkeypatch.delenv(env, raising=False)

    md = content.generate_content(DATA)
    assert md == "# 블로그 글\n본문"            # strip 적용
    assert captured["provider"] == "gemini"     # 기본 provider
    assert captured["models"] == {"gemini": "gemini-2.5-flash"}
    assert "발레아주" in captured["prompt"]


def test_generate_content_provider_override(monkeypatch):
    captured = {}

    async def fake_complete(provider, prompt, models=None, timeout=60.0):
        captured.update(provider=provider, models=models)
        return "ok"

    monkeypatch.setattr(engines, "complete", fake_complete)
    monkeypatch.setenv("REPORT_PROVIDER", "openai")
    monkeypatch.setenv("REPORT_MODEL", "gpt-4.1")
    content.generate_content(DATA)
    assert captured["provider"] == "openai" and captured["models"] == {"openai": "gpt-4.1"}


def test_write_content(tmp_path):
    p = content.write_content("# 글", "minji", out_dir=str(tmp_path / "content"))
    assert p.exists() and p.read_text(encoding="utf-8") == "# 글"


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
