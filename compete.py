#!/usr/bin/env python3
"""경쟁 노출 스캔 (영업용) — 같은 질문에서 누가 AI에 노출되는지.

사용법:
    python compete.py targets/gangnam_balayage.yaml

진단 엔진을 재사용해 질문 × 엔진 × 샘플로 질의하고, 답변에 등장한
경쟁 미용실/디자이너를 집계한다. 대상 디자이너(있으면)가 몇 번
노출되는지도 함께 보여 영업 자료로 쓴다.
출력: runs/{slug}/{stamp}/compete.md (+ raw.json)
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import diagnose
import engines


def aggregate_competitors(records: list[dict], designer_names: list[str]) -> dict:
    competitors: Counter[str] = Counter()
    target_mentions = success = failed = 0
    for r in records:
        if r.get("error"):
            failed += 1
            continue
        success += 1
        ext = r.get("extraction") or {}
        if ext.get("mentioned"):
            target_mentions += 1
        for c in ext.get("competitors_mentioned", []):
            competitors[c] += 1
    return {
        "competitors": competitors.most_common(),
        "target_mentions": target_mentions,
        "success": success,
        "failed": failed,
        "has_target": bool(designer_names),
    }


def render_compete(agg: dict, config: dict) -> str:
    L: list[str] = []
    region = config.get("region", "")
    specialties = ", ".join(config.get("specialties", []) or [])
    L.append(f"# 경쟁 노출 스캔 — {region} {specialties}\n".rstrip() + "\n")
    L.append(f"- 측정일: {datetime.now().isoformat(timespec='minutes')}")
    L.append(f"- 성공 호출: {agg['success']} / 실패: {agg['failed']}\n")

    L.append("## AI 답변에 노출된 경쟁 후보 (많은 순)")
    if agg["competitors"]:
        L.append("| 순위 | 이름 | 노출 횟수 |")
        L.append("|---|---|---|")
        for i, (name, cnt) in enumerate(agg["competitors"], 1):
            L.append(f"| {i} | {name} | {cnt} |")
    else:
        L.append("- 뚜렷한 경쟁 노출이 잡히지 않았습니다.")
    L.append("")

    if agg["has_target"]:
        name = config.get("designer", {}).get("name", "대상")
        n = agg["target_mentions"]
        L.append("## 대상 노출")
        if n == 0:
            top = agg["competitors"][0][0] if agg["competitors"] else "경쟁 매장"
            L.append(
                f"- **{name} 님은 이 키워드에서 한 번도 노출되지 않았습니다 (0회).**"
            )
            L.append(
                f"- 같은 질문에서는 {top} 등 경쟁이 대신 나옵니다 — "
                "지금이 비어 있는 자리를 선점할 기회입니다."
            )
        else:
            L.append(f"- {name} 님은 {n}회 노출되었습니다.")
        L.append("")
    return "\n".join(L)


def main() -> None:
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("사용법: python compete.py targets/{slug}.yaml")

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    config_path = sys.argv[1]
    config = diagnose.load_config(config_path)
    slug = diagnose.slug_from_path(config_path)

    active = engines.active_engines()
    if not active:
        raise SystemExit("활성 엔진이 없습니다. .env 에 API 키를 설정하세요.")
    print(f"활성 엔진: {', '.join(active)}")

    if not diagnose.confirm_cost(len(config["questions"]), len(active), int(config["sampling"])):
        print("취소했습니다.")
        return

    models = engines.resolve_models()
    records = asyncio.run(diagnose.run_all(config, models, active))

    designer_names = diagnose._names(config.get("designer", {}))
    agg = aggregate_competitors(records, designer_names)
    md = render_compete(agg, config)

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    run_dir = Path("runs") / slug / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "raw.json").write_text(
        json.dumps({"run_at": datetime.now().isoformat(timespec="minutes"),
                    "config": {k: config.get(k) for k in ("region", "specialties", "designer")},
                    "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out = run_dir / "compete.md"
    out.write_text(md, encoding="utf-8")
    print(f"경쟁 노출 리포트: {out}")


if __name__ == "__main__":
    main()
