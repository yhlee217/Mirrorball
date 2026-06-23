"""프로필 카피 생성기 테스트 — gen_profile (LLM 호출 없이 프롬프트·병합)."""

import gen_profile as gp

BRIEF = {
    "slug": "demo", "display_name": "Demo", "role": "헤어디자이너",
    "salon": "데모살롱", "region": "합정역", "instagram": "demo",
    "services": ["단발컷", "곱슬 교정"],
    "audience": "첫 방문 불안한 분",
    "facts": ["미용 경력 8년", "손상 신경 써서 약한 약제부터"],
    "must_not_claim": ["연예인", "수상"],
}


def test_build_case_extracts_service_and_keywords():
    case = gp.build_case(BRIEF)
    assert case["service"] == "단발컷"
    assert "곱슬 교정" in case["keywords"]
    assert "손상" in case["keywords"]          # facts 신호어 반영


def test_render_prompt_injects_facts_region_principles():
    p = gp.render_prompt(BRIEF)
    assert "합정역" in p and "미용 경력 8년" in p
    assert "연예인, 수상" in p                  # must_not_claim 주입
    # RAG 원칙이 최소 1개 들어감(KB 에서 검색)
    assert "[반드시 녹여야 할 검증된 영업 원칙(RAG)" in p
    assert "- " in p.split("RAG)")[1][:400]


def test_parse_copy_handles_fenced_yaml():
    text = "잡담\n```yaml\ntagline: |\n  한 줄\nabout:\n  - 불릿\n```\n끝"
    d = gp.parse_copy(text)
    assert d["tagline"].strip() == "한 줄" and d["about"] == ["불릿"]


def test_parse_copy_plain():
    d = gp.parse_copy("tagline: 하이\nknows_about: [a, b]")
    assert d["tagline"] == "하이" and d["knows_about"] == ["a", "b"]


def test_merge_combines_passthrough_and_copy():
    copy = {"tagline": "T", "specialties": [{"name": "단발", "desc": "d"}],
            "about": ["x"], "faq": [{"q": "q", "a": "a"}], "knows_about": ["k"]}
    out = gp.merge(BRIEF, copy)
    assert out["slug"] == "demo" and out["salon"] == "데모살롱"   # passthrough
    assert out["tagline"] == "T" and out["knows_about"] == ["k"]  # 생성분
    assert "facts" not in out                                     # brief 전용 필드는 제외
