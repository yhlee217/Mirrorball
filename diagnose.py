#!/usr/bin/env python3
"""미용사 AI 노출 진단 — CLI 엔트리.

사용법:
    python diagnose.py targets/kimminji.yaml

키가 설정된 AI 엔진(들)에 질문을 질의하고, 각 답변에서 디자이너/매장
언급·맥락·인용을 추출해 raw.json 으로 저장한 뒤, REPORT_PROVIDER 로
고객용 마크다운 리포트(report.md)를 만든다.

초기 비용 0 원칙: 키 있는 provider만 자동 활성화. 활성 엔진 0개면 종료.
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


def resolve_report_provider(active: list[str]) -> str:
    """REPORT_PROVIDER(기본 gemini) 검증. 미지원/키없음이면 명확히 종료."""
    import os

    provider = (os.getenv("REPORT_PROVIDER") or "gemini").strip()
    if provider not in engines.PROVIDERS:
        raise SystemExit(
            f"REPORT_PROVIDER='{provider}' 는 지원하지 않습니다. "
            f"({', '.join(engines.PROVIDERS)} 중 하나)"
        )
    if provider not in active:
        raise SystemExit(
            f"REPORT_PROVIDER={provider} 인데 {engines.KEY_ENV[provider]} 가 없습니다. "
            "키를 설정하거나 활성 엔진 중 하나로 REPORT_PROVIDER 를 바꾸세요."
        )
    return provider


def confirm_cost(n_questions: int, n_engines: int, sampling: int) -> bool:
    total = n_questions * n_engines * sampling
    print(f"\n질문 {n_questions} × 엔진 {n_engines} × 샘플 {sampling} = 총 {total}회 호출 예정.")
    try:
        ans = input("진행할까요? [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


async def run_all(config: dict, models: dict, engines_list: list[str]) -> list[dict]:
    """질문 × (활성 엔진) × sampling 을 동시 3개 세마포어로 병렬 질의 + 추출."""
    designer_names = _names(config["designer"])
    salon_names = _names(config["salon"])
    sampling = int(config["sampling"])
    sem = asyncio.Semaphore(3)

    jobs = [
        (q, eng, idx)
        for q in config["questions"]
        for eng in engines_list
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
    run_dir: Path, config: dict, records: list[dict],
    models: dict, engines_list: list[str], report_provider: str,
) -> tuple[Path, dict]:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "designer": config["designer"],
        "salon": config["salon"],
        "region": config.get("region", ""),
        "specialties": config.get("specialties", []),
        "sampling": config["sampling"],
        "run_at": datetime.now().isoformat(timespec="minutes"),
        "models": {e: models[e] for e in engines_list},
        "report_provider": report_provider,
        "records": records,
    }
    path = run_dir / "raw.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, payload


def exposure_from_records(records: list[dict], generated=None) -> dict:
    """진단 records → 원장앱 노출 데이터(build_app/app 이 읽는 exposure 스키마).
    질문별 '언급된 (질문,엔진,샘플) 수'를 count 로, 합을 score 로."""
    from collections import OrderedDict
    from datetime import date as _date

    qs: "OrderedDict[str, int]" = OrderedDict()
    for r in records:
        q = r.get("question")
        if q is None:
            continue
        qs.setdefault(q, 0)
        ex = r.get("extraction") or {}
        if ex.get("mentioned"):
            qs[q] += 1
    return {
        "score": sum(qs.values()),
        "generated": str(generated or _date.today()),
        "questions": [{"q": q, "count": c} for q, c in qs.items()],
    }


def write_exposure(slug: str, records: list[dict], clients_dir: str = "clients") -> Path:
    """clients/{slug}/exposure.yaml 로 저장 → build_app 이 앱 노출 탭에 주입."""
    import yaml as _yaml

    out = Path(clients_dir) / slug / "exposure.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        _yaml.safe_dump(exposure_from_records(records), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return out


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

    active = engines.active_engines()
    if not active:
        raise SystemExit(
            "활성 엔진이 없습니다. .env 에 "
            "OPENAI_API_KEY / GOOGLE_API_KEY / PERPLEXITY_API_KEY 중 "
            "하나 이상을 설정하세요."
        )
    report_provider = resolve_report_provider(active)
    models = engines.resolve_models()

    print(f"활성 엔진: {', '.join(active)} / 리포트: {report_provider}")

    if not confirm_cost(len(config["questions"]), len(active), int(config["sampling"])):
        print("취소했습니다.")
        return

    print("\n질의 중...")
    records = asyncio.run(run_all(config, models, active))

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    run_dir = Path("runs") / slug / stamp
    raw_path, payload = save_raw(run_dir, config, records, models, active, report_provider)
    print(f"\nraw 저장: {raw_path}")

    report_path = None
    try:
        markdown = report.generate_report(payload, provider=report_provider)
        report_path = report.write_report(markdown, run_dir)
    except Exception as exc:  # 리포트 실패해도 raw 는 남는다
        print(f"리포트 생성 실패 (raw 는 저장됨): {type(exc).__name__}: {exc}")

    try:
        exp_path = write_exposure(slug, records)
        print(f"앱 노출 데이터: {exp_path}  (build_app 이 노출 탭에 주입)")
    except Exception as exc:
        print(f"노출 데이터 저장 실패: {type(exc).__name__}: {exc}")

    print_summary(records, report_path)


if __name__ == "__main__":
    main()
