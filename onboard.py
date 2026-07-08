#!/usr/bin/env python3
"""디자이너 서비스 일괄 세팅 — 수집한 데이터로 각 디자이너의 서비스를 다 만든다.

핸드SOS 담당별 분리(clients/{slug}/)가 끝난 뒤 실행하면, 디자이너마다:
  1) 거래 이력에서 '전문 시술'을 자동 도출(발견 키워드 후보)
  2) 발견케어 설정(targets/{slug}.yaml) 자동 생성(없을 때만) — 지역×전문시술 질문 포함
  3) 앱 CRM 빌드(dist_app/{slug}.json)
  4) 서비스 요약(고객·재방문·VIP·챙길고객·매출) 출력

지역·살롱은 매장 공통(같은 살롱) — 인자로 지정. 이미 만든 target 은 건드리지 않음(수동 우선).

사용:
  python onboard.py --salon 살롱톤 --region 영등포시장역           # 모든 디자이너
  python onboard.py --only hayewoni --salon 살롱톤 --region 영등포시장역
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

import build_app
import stats

# 발견 키워드로는 부적합한 '범용' 시술(누구나 하는 것) — 전문시술 도출에서 제외.
_GENERIC = re.compile(r"^(남자컷|여자컷|주니어컷|학생컷|아동컷|커트|컷)$|앞머리|샴푸|드라이|"
                      r"기장\s*추가|추가$|스타일링$|정리$")
# 서비스명 접미 잡토큰 정리(펌제·시술 등)
_TAIL = re.compile(r"(제|비용|서비스)$")
_DEMO_DIRS = {"minji", "_demo", "_salon", "demohandsos"}


def derive_specialties(records: list[dict], k: int = 4) -> list[str]:
    """거래 이력 → 전문 시술 top-k(범용 컷·추가 제외). 발견케어 키워드 후보."""
    from collections import Counter
    c: Counter = Counter()
    for r in records or []:
        s = (r.get("service") or "").strip()
        if not s or _GENERIC.search(s):
            continue
        c[_TAIL.sub("", s)] += 1
    return [s for s, _ in c.most_common(k)]


def gen_questions(region: str, specialties: list[str]) -> list[str]:
    """지역×전문시술 → 손님이 AI/검색에 칠 법한 질문(자동 초안, 사람이 다듬으면 됨)."""
    qs = [f"{region} {sp} 잘하는 미용실 추천해줘" for sp in specialties[:3]]
    qs.append(f"{region} 근처 미용실 어디가 괜찮아")
    return qs


def bootstrap_target(slug: str, name: str, salon: str, region: str,
                     specialties: list[str], force: bool = False) -> bool:
    """targets/{slug}.yaml 발견케어 설정 자동 생성(없을 때만). 반환: 새로 만들었나."""
    p = Path("targets") / f"{slug}.yaml"
    if p.exists() and not force:
        return False
    data = {
        "designer": {"name": name},
        "salon": {"name": salon, "aliases": [f"{salon} {region}"]},
        "region": region,
        "specialties": specialties or ["커트"],
        "questions": gen_questions(region, specialties or ["커트"]),
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return True


def build_service(slug: str, salon: str, region: str, today=None) -> dict:
    """한 디자이너의 서비스 패키지 세팅 — 전문시술 도출 → target → 앱 빌드 → 요약."""
    cdir = Path("clients") / slug
    records = yaml.safe_load((cdir / "records.yaml").read_text(encoding="utf-8")) or [] \
        if (cdir / "records.yaml").exists() else []
    config = yaml.safe_load((cdir / "config.yaml").read_text(encoding="utf-8")) or {} \
        if (cdir / "config.yaml").exists() else {}
    name = config.get("display_name") or slug

    specs = derive_specialties(records)
    made = bootstrap_target(slug, name, config.get("salon") or salon, region, specs)
    st = stats.compute(records, today) if records else {}
    built = build_app.build_one(str(cdir))
    clients = built.get("clients", 0)
    vip = sum(1 for c in _load_tiers(slug) if c == "vip")
    return {
        "slug": slug, "name": name, "specialties": specs, "target_made": made,
        "customers": clients, "care": built.get("care", 0), "vip": vip,
        "visits": st.get("total_visits", 0), "revisit": st.get("revisit_rate", 0),
        "avg_price": st.get("avg_price", 0), "top": st.get("top_services", []),
    }


def _load_tiers(slug: str) -> list[str]:
    import json
    p = Path("dist_app") / f"{slug}.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    return [c.get("tier") for c in (data.get("clients") or [])]


def designer_slugs(only: str | None = None) -> list[str]:
    if only:
        return [only]
    out = []
    for d in sorted(Path("clients").glob("*")):
        if d.is_dir() and d.name not in _DEMO_DIRS and (d / "records.yaml").exists():
            out.append(d.name)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="디자이너 서비스 일괄 세팅")
    ap.add_argument("--salon", default="살롱톤")
    ap.add_argument("--region", default="영등포시장역")
    ap.add_argument("--only", help="이 slug 만")
    args = ap.parse_args()

    slugs = designer_slugs(args.only)
    if not slugs:
        print("대상 디자이너 없음 (clients/{slug}/records.yaml 필요) — 먼저 핸드SOS 동기화")
        return 1

    print(f"디자이너 {len(slugs)}명 서비스 세팅: {', '.join(slugs)}\n")
    rows = []
    for slug in slugs:
        r = build_service(slug, args.salon, args.region)
        rows.append(r)
        made = " (발견설정 새로 생성)" if r["target_made"] else ""
        print(f"■ {r['name']} [{slug}]{made}")
        print(f"   고객 {r['customers']}명 · 재방문 {r['revisit']}% · VIP {r['vip']}명 · "
              f"챙길고객 {r['care']}명 · 객단가 {r['avg_price']:,}원")
        print(f"   전문시술(발견 키워드): {', '.join(r['specialties']) or '(도출 실패)'}")
        print(f"   앱: dist_app/{slug}.json  (?d={slug})\n")

    print("─" * 48)
    print(f"완료: {len(rows)}명 서비스 세팅 · 앱 빌드 · 발견케어 설정")
    print("발견케어 측정은 각 target 에 네이버 키 넣고:  python expose.py clients/{slug} --measure --place --rank")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
