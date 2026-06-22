#!/usr/bin/env python3
"""영업 노하우 RAG 검색 — 케이스 상황에 맞는 검증된 원칙을 끌어온다.

지금은 결정론적 토큰 겹침 스코어링(임베딩 불필요, 파일 기반, 테스트 가능).
규모가 커지면 동일 인터페이스로 임베딩 검색으로 승급할 수 있다.

사용:
    python rag.py 발레아주 "뿌리 자람 손상 걱정"     # 매칭 원칙 미리보기
"""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_KB = "kb/knowledge.yaml"

# 가중치
W_SERVICE = 2.0     # 시술 일치
W_SIGNAL = 1.5      # 시그널 토큰 일치
W_UNIVERSAL = 0.4   # 보편(["*"]) 엔트리 기본점
W_PRIORITY = 0.1    # priority 가산


def load_kb(path: str = DEFAULT_KB) -> list[dict]:
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return data.get("entries", []) or []


def case_text(case_input: dict) -> str:
    parts = [
        case_input.get("service", ""),
        case_input.get("audience", ""),
        " ".join(case_input.get("keywords", []) or []),
    ]
    return " ".join(p for p in parts if p)


def score(entry: dict, text: str) -> float:
    a = entry.get("applies_to", {}) or {}
    s = 0.0
    services = a.get("services", []) or []
    if "*" in services:
        s += W_UNIVERSAL
    for sv in services:
        if sv != "*" and sv and sv in text:
            s += W_SERVICE
    for sig in a.get("signals", []) or []:
        if sig and sig in text:
            s += W_SIGNAL
    s += entry.get("priority", 0) * W_PRIORITY
    return round(s, 3)


def retrieve(case_input: dict, kb: list[dict] | None = None,
             kb_path: str = DEFAULT_KB, k: int = 3) -> list[dict]:
    """관련도 높은 엔트리 top-k. 동점은 priority·id 로 안정 정렬."""
    kb = kb if kb is not None else load_kb(kb_path)
    text = case_text(case_input)
    scored = [(score(e, text), e) for e in kb]
    scored = [(sc, e) for sc, e in scored if sc > 0]
    scored.sort(key=lambda x: (-x[0], -x[1].get("priority", 0), x[1].get("id", "")))
    return [e for _, e in scored[:k]]


def principles_for(case_input: dict, kb: list[dict] | None = None,
                   kb_path: str = DEFAULT_KB, k: int = 3) -> list[str]:
    """검색 결과를 카피 주입용 원칙 문자열 리스트로."""
    return [e["principle"] for e in retrieve(case_input, kb, kb_path, k)]


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('사용법: python rag.py {시술} ["오디언스/키워드"]')
    case_input = {"service": sys.argv[1], "audience": sys.argv[2] if len(sys.argv) > 2 else "",
                  "keywords": []}
    for e in retrieve(case_input, k=4):
        print(f"[{score(e, case_text(case_input))}] {e['id']} — {e['principle']}")


if __name__ == "__main__":
    main()
