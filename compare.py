#!/usr/bin/env python3
"""발행 전·후 AI 노출 변화 비교 — runs/*/raw.json 두 개를 비교.

사용법:
    python compare.py kimminji                      # 최근 두 측정 자동 비교
    python compare.py runs/kimminji/A runs/kimminji/B   # 두 run 디렉터리 명시

서버·LLM 없이 raw.json 만으로 변화 리포트(markdown)를 만든다.
출력: 두 번째(최신) run 디렉터리에 compare.md 저장.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from extract import domain_of


def load_raw(run_dir: str | Path) -> dict:
    p = Path(run_dir)
    if p.is_dir():
        p = p / "raw.json"
    return json.loads(p.read_text(encoding="utf-8"))


def find_runs(slug: str) -> list[Path]:
    base = Path("runs") / slug
    if not base.is_dir():
        raise SystemExit(f"runs/{slug} 가 없습니다")
    return sorted(d for d in base.iterdir() if (d / "raw.json").exists())


def summarize(raw: dict) -> dict:
    """raw.json 한 개를 비교용 지표로 집계."""
    records = raw.get("records", [])
    engines: list[str] = []
    questions: list[str] = []
    for r in records:
        if r["engine"] not in engines:
            engines.append(r["engine"])
        if r["question"] not in questions:
            questions.append(r["question"])

    per_engine = {e: 0 for e in engines}
    per_q = {q: 0 for q in questions}
    domains: Counter[str] = Counter()
    competitors: Counter[str] = Counter()
    total_mentions = success = failed = 0

    for r in records:
        if r.get("error"):
            failed += 1
            continue
        success += 1
        ext = r.get("extraction") or {}
        if ext.get("mentioned"):
            total_mentions += 1
            per_engine[r["engine"]] = per_engine.get(r["engine"], 0) + 1
            per_q[r["question"]] = per_q.get(r["question"], 0) + 1
        for url in ext.get("citations", []):
            d = domain_of(url)
            if d:
                domains[d] += 1
        for c in ext.get("competitors_mentioned", []):
            competitors[c] += 1

    return {
        "run_at": raw.get("run_at", ""),
        "engines": engines,
        "questions": questions,
        "per_engine": per_engine,
        "per_q": per_q,
        "domains": domains,
        "competitors": competitors,
        "total_mentions": total_mentions,
        "success": success,
        "failed": failed,
    }


def _delta(before: int, after: int) -> str:
    d = after - before
    if d > 0:
        return f"▲ +{d}"
    if d < 0:
        return f"▼ {d}"
    return "– 0"


def render_compare(before: dict, after: dict) -> str:
    """두 요약을 받아 전후 변화 마크다운을 만든다."""
    L: list[str] = []
    L.append("# AI 노출 변화 리포트 (발행 전 → 후)\n")
    L.append(f"- 발행 전 측정: {before['run_at']}")
    L.append(f"- 발행 후 측정: {after['run_at']}\n")

    L.append("## 한눈에 보기")
    L.append(
        f"- 전체 언급: **{before['total_mentions']}회 → {after['total_mentions']}회** "
        f"({_delta(before['total_mentions'], after['total_mentions'])})\n"
    )

    # 엔진별
    engines = list(dict.fromkeys(before["engines"] + after["engines"]))
    L.append("## 엔진별 언급 변화")
    L.append("| 엔진 | 전 | 후 | 변화 |")
    L.append("|---|---|---|---|")
    for e in engines:
        b = before["per_engine"].get(e, 0)
        a = after["per_engine"].get(e, 0)
        L.append(f"| {e} | {b} | {a} | {_delta(b, a)} |")
    L.append("")

    # 질문별
    questions = list(dict.fromkeys(before["questions"] + after["questions"]))
    L.append("## 질문별 언급 변화")
    L.append("| 질문 | 전 | 후 | 변화 |")
    L.append("|---|---|---|---|")
    for q in questions:
        b = before["per_q"].get(q, 0)
        a = after["per_q"].get(q, 0)
        L.append(f"| {q} | {b} | {a} | {_delta(b, a)} |")
    L.append("")

    # 인용 출처 변화
    new_domains = [d for d in after["domains"] if d not in before["domains"]]
    lost_domains = [d for d in before["domains"] if d not in after["domains"]]
    L.append("## 인용 출처 변화")
    L.append(f"- 새로 등장: {', '.join(new_domains) if new_domains else '없음'}")
    L.append(f"- 사라짐: {', '.join(lost_domains) if lost_domains else '없음'}\n")

    # 경쟁 노출 변화
    L.append("## 경쟁 노출 변화")
    comp_keys = list(dict.fromkeys(list(before["competitors"]) + list(after["competitors"])))
    if comp_keys:
        L.append("| 경쟁 후보 | 전 | 후 | 변화 |")
        L.append("|---|---|---|---|")
        for c in comp_keys:
            b = before["competitors"].get(c, 0)
            a = after["competitors"].get(c, 0)
            L.append(f"| {c} | {b} | {a} | {_delta(b, a)} |")
    else:
        L.append("- 눈에 띄는 경쟁 노출 없음")
    L.append("")
    return "\n".join(L)


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 1:
        runs = find_runs(args[0])
        if len(runs) < 2:
            raise SystemExit(f"비교하려면 측정이 2회 이상 필요합니다 (현재 {len(runs)}회)")
        before_dir, after_dir = runs[-2], runs[-1]
    elif len(args) == 2:
        before_dir, after_dir = Path(args[0]), Path(args[1])
    else:
        raise SystemExit("사용법: python compare.py <slug> | <run_before> <run_after>")

    before = summarize(load_raw(before_dir))
    after = summarize(load_raw(after_dir))
    md = render_compare(before, after)

    out = Path(after_dir)
    out = (out if out.is_dir() else out.parent) / "compare.md"
    out.write_text(md, encoding="utf-8")

    print(f"전: {before_dir}  ({before['run_at']})")
    print(f"후: {after_dir}  ({after['run_at']})")
    print(f"언급 {before['total_mentions']} → {after['total_mentions']} "
          f"({_delta(before['total_mentions'], after['total_mentions'])})")
    print(f"리포트: {out}")


if __name__ == "__main__":
    main()
