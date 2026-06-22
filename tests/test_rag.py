"""rag.py 검색 + copygen RAG 통합 — LLM 없이 결정론적 검증."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import copygen  # noqa: E402
import rag  # noqa: E402

KB = rag.load_kb("kb/knowledge.yaml")

PRICE = {"service": "커트", "audience": "가격이 부담돼 자주 못 가는 고객", "keywords": ["가성비"]}
PERM = {"service": "디지털펌", "audience": "펌이 빨리 풀려 실망한 고객", "keywords": ["펌 풀림", "재시술"]}


def test_load_kb():
    assert len(KB) >= 11
    assert all("id" in e and "principle" in e and "applies_to" in e for e in KB)


def test_score_components():
    text = "디지털펌 펌 풀려 재시술"
    fc = next(e for e in KB if e["id"] == "failure_cause")
    ql = next(e for e in KB if e["id"] == "question_lead")  # universal, signals []
    assert rag.score(fc, text) > rag.score(ql, text)        # 시술+시그널 매칭이 보편보다 높음
    assert rag.score(ql, "관계없는 텍스트") > 0              # 보편 엔트리는 항상 기본점


def test_retrieve_price_sensitive():
    top = rag.retrieve(PRICE, KB, k=3)
    ids = [e["id"] for e in top]
    assert ids[0] == "transparent_price"      # 가격·부담·가성비 3 시그널
    assert "need_only" in ids


def test_retrieve_perm_redo():
    top = rag.retrieve(PERM, KB, k=3)
    ids = [e["id"] for e in top]
    assert ids[0] == "failure_cause"          # 시술 2 + 시그널 3
    assert len(top) == 3


def test_principles_for_returns_strings():
    ps = rag.principles_for(PRICE, KB, k=3)
    assert len(ps) == 3 and all(isinstance(p, str) for p in ps)
    assert any("투명" in p for p in ps)        # transparent_price 의 principle


def test_retrieve_deterministic_order():
    # 동일 입력 → 동일 결과(안정 정렬)
    a = [e["id"] for e in rag.retrieve(PERM, KB, k=4)]
    b = [e["id"] for e in rag.retrieve(PERM, KB, k=4)]
    assert a == b


# --- copygen 통합 ----------------------------------------------------------
def test_resolve_principles_explicit_wins():
    case = {"input": PRICE, "rag_principles": ["내가 직접 적은 원칙"]}
    # 명시 원칙이 있으면 KB 검색을 무시
    assert copygen.resolve_principles(case, kb_path="kb/knowledge.yaml") == ["내가 직접 적은 원칙"]


def test_resolve_principles_falls_back_to_rag():
    case = {"input": PERM}  # rag_principles 없음
    ps = copygen.resolve_principles(case, kb_path="kb/knowledge.yaml", k=3)
    assert len(ps) == 3
    assert any("원인" in p for p in ps)         # failure_cause 의 principle


def test_resolve_principles_no_kb_returns_empty():
    case = {"input": PERM}
    assert copygen.resolve_principles(case, kb_path=None) == []


def test_render_prompt_injects_retrieved_principles():
    case = {"input": PERM, "must_include": ["디지털펌"], "must_not_claim": []}
    prompt = copygen.render_prompt(case, kb_path="kb/knowledge.yaml")
    # RAG 가 끌어온 원칙이 프롬프트에 실제로 들어감
    assert "고객의 과거 실패를 탓하지 않고" in prompt


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
