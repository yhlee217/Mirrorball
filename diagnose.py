#!/usr/bin/env python3
"""미용사 AI 노출 진단 — CLI 엔트리.

사용법:
    python diagnose.py targets/kimminji.yaml

질문 × 엔진(3) × sampling 만큼 3개 AI 엔진에 질의하고, 각 답변에서
디자이너/매장 언급·맥락·인용을 추출해 raw.json 으로 저장한 뒤,
Anthropic API 로 고객용 마크다운 리포트(report.md)를 만든다.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

import engines
import extract
import report


def load_config(path: str) -> dict:
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not cfg.get("questions"):
        raise SystemExit("config 에 questions 가 없습니다. 질문은 사람이 직접 넣어야 합니다.")
    cfg.setdefault("sampling", 1)
    cfg.setdefault("designer", {})
    cfg.setdefault("salon", {})
    return cfg


def slug_from_path(path: str) -> str:
    return Path(path).stem


def _names(node: dict) -> list[str]:
    names = []
    if node.get("name"):
        names.append(node["name"])
    names.extend(node.get("aliases", []) or [])
    return names


def confirm_cost(n_questions: int, sampling: int) -> bool:
    total = n_questions * 3 * sampling
    print(f"\n질문 {n_questions} × 엔진 3 × 샘플 {sampling} = 총 {total}회 호출 예정.")
    try:
        ans = input("진행할까요? [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


async def run_all(config: dict, models: dict) -> list[dict]:
    """질문 × 엔진 × sampling 을 동시 3개 세마포어로 병렬 질의 + 추출."""
    designer_names = _names(config["designer"])
    salon_names = _names(config["salon"])
    sampling = int(config["sampling"])
    sem = asyncio.Semaphore(3)

    jobs = [
        (q, eng, idx)
        for q in config["questions"]
        for eng in ("openai", "gemini", "perplexity")
        for idx in range(sampling)
    ]

    async def worker(question: str, engine: str, idx: int) -> dict:
        try:
            async with sem:
                result = await engines.call_engine(engine, question, models)
        except Exception as exc:  # 한 호출의 사고가 전체 실행/저장을 막지 않게
            result = {"text": "", "citations": [], "model": None,
                      "error": f"{type(exc).__name__}: {exc}"}

        record = {
            "question": question,
            "engine": engine,
            "model": result.get("model"),
            "sample_idx": idx,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "response_text": result.get("text", ""),
            "citations": result.get("citations", []),
            "error": result.get("error"),
            "extraction": None,
        }
        if not result.get("error"):
            try:
                record["extraction"] = extract.analyze(
                    result["text"], designer_names, salon_names, result["citations"]
                )
                done = "○" if record["extraction"]["mentioned"] else "✕"
                print(f"  [{done}] {engine:<10} | {question[:30]}")
            except Exception as exc:  # 추출 실패도 에러로 기록하고 계속
                record["error"] = f"extract: {type(exc).__name__}: {exc}"
                print(f"  [!] {engine:<10} | {question[:30]} — {record['error']}")
        else:
            print(f"  [!] {engine:<10} | {question[:30]} — {result['error']}")
        return record

    return await asyncio.gather(*(worker(q, e, i) for q, e, i in jobs))


def save_raw(
    run_dir: Path, config: dict, records: list[dict], models: dict
) -> tuple[Path, dict]:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "designer": config["designer"],
        "salon": config["salon"],
        "region": config.get("region", ""),
        "specialties": config.get("specialties", []),
        "sampling": config["sampling"],
        "run_at": datetime.now().isoformat(timespec="minutes"),
        "models": models,
        "records": records,
    }
    path = run_dir / "raw.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, payload


def print_summary(records: list[dict], report_path: Path | None) -> None:
    success = sum(1 for r in records if not r.get("error"))
    failed = sum(1 for r in records if r.get("error"))
    mentions = sum(
        1 for r in records if r.get("extraction") and r["extraction"]["mentioned"]
    )
    print("\n" + "=" * 48)
    print(f"성공 호출: {success}  /  실패 호출: {failed}")
    print(f"언급 횟수: {mentions}")
    print(f"리포트: {report_path if report_path else '(생성 실패)'}")
    print("=" * 48)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("사용법: python diagnose.py targets/{slug}.yaml")

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    config_path = sys.argv[1]
    config = load_config(config_path)
    slug = slug_from_path(config_path)
    models = engines.resolve_models()  # .env 로드 이후 호출되어야 오버라이드 반영

    if not confirm_cost(len(config["questions"]), int(config["sampling"])):
        print("취소했습니다.")
        return

    print("\n질의 중...")
    records = asyncio.run(run_all(config, models))

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    run_dir = Path("runs") / slug / stamp
    raw_path, payload = save_raw(run_dir, config, records, models)
    print(f"\nraw 저장: {raw_path}")

    report_path = None
    try:
        markdown = report.generate_report(payload)
        report_path = report.write_report(markdown, run_dir)
    except Exception as exc:  # 리포트 실패해도 raw 는 남는다
        print(f"리포트 생성 실패 (raw 는 저장됨): {type(exc).__name__}: {exc}")

    print_summary(records, report_path)


if __name__ == "__main__":
    main()
