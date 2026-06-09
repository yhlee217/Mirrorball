"""추출 로직 단위 테스트 — mock AI 응답 기반.

엔진/네트워크 호출 없이 extract.analyze 만 검증한다.
실행: python -m pytest tests/ -q
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from extract import analyze, normalize, mention_context, extract_competitors  # noqa: E402

DESIGNER = ["김민지", "민지 디자이너", "minji.hair"]
SALON = ["살롱드헤어 강남점", "살롱드헤어"]


# mock 응답: 디자이너가 언급되고 네이버 출처 인용, 경쟁사도 등장
MOCK_MENTIONED = (
    "강남역에서 발레아주를 잘하는 곳으로는 살롱드헤어 강남점이 유명합니다. "
    "특히 김민지 디자이너가 발레아주 전문으로 평이 좋습니다. "
    "예약은 네이버 플레이스에서 가능합니다. https://blog.naver.com/example/123 "
    "근처 미미헤어 도 인기가 있습니다."
)

# mock 응답: 본인 언급 없이 경쟁사만
MOCK_NOT_MENTIONED = (
    "강남역 디지털펌은 라온살롱 과 청담스타일헤어 가 추천됩니다. "
    "자세한 후기는 https://example.com/review 에서 확인하세요."
)


def test_mentioned_detection():
    result = analyze(MOCK_MENTIONED, DESIGNER, SALON, ["https://blog.naver.com/example/123"])
    assert result["mentioned"] is True


def test_not_mentioned():
    result = analyze(MOCK_NOT_MENTIONED, DESIGNER, SALON, [])
    assert result["mentioned"] is False
    assert result["context"] is None


def test_context_includes_mention_sentence():
    result = analyze(MOCK_MENTIONED, DESIGNER, SALON, [])
    assert result["context"] is not None
    assert "김민지" in result["context"] or "살롱드헤어" in result["context"]


def test_citations_merge_and_dedup():
    result = analyze(
        MOCK_MENTIONED, DESIGNER, SALON, ["https://blog.naver.com/example/123"]
    )
    # 엔진 인용 + 본문 URL 병합, 중복 제거
    assert "https://blog.naver.com/example/123" in result["citations"]
    assert len(result["citations"]) == len(set(result["citations"]))


def test_competitors_exclude_self():
    comps = extract_competitors(MOCK_MENTIONED, DESIGNER + SALON)
    # 자기 매장(살롱드헤어)은 제외, 미미헤어는 포함
    assert any("미미헤어" in c for c in comps)
    assert all("살롱드헤어" not in c for c in comps)


def test_normalize_ignores_spaces_and_case():
    assert normalize("minji.hair") == normalize("MINJI HAIR")
    assert normalize("살롱드헤어 강남점") == normalize("살롱드헤어강남점")


def test_mention_context_returns_none_when_absent():
    assert mention_context(MOCK_NOT_MENTIONED, DESIGNER + SALON) is None


def test_competitors_no_leading_junk():
    # "추천됩니다. 라온살롱" 에서 "다 라온살롱" 처럼 앞 단어가 딸려오면 안 됨
    comps = extract_competitors(MOCK_NOT_MENTIONED, DESIGNER + SALON)
    assert "라온살롱" in comps
    assert "청담스타일헤어" in comps
    assert all(" " not in c for c in comps)  # 공백 섞인 후보 없음


def test_competitors_dedup():
    text = "미미헤어 추천. 또 미미헤어 가 좋고 라온살롱 도 있어요."
    comps = extract_competitors(text, DESIGNER + SALON)
    assert comps.count("미미헤어") == 1


def test_citations_strip_trailing_punctuation():
    from extract import extract_citations

    text = "후기는 https://example.com/review, 그리고 (https://naver.com/x)."
    cites = extract_citations(text, [])
    assert "https://example.com/review" in cites
    assert "https://naver.com/x" in cites
    assert all(not c.endswith((",", ")", ".")) for c in cites)


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
