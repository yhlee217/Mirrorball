#!/usr/bin/env python3
"""앱 '소개 편집' → designers/{slug}.yaml 역동기화(공개 소개페이지 소스).

앱에서 편집한 소개 필드(JSON)를 디자이너 프로필 YAML 에 반영한다. **편집 가능한 필드만**
덮어쓰고, slug·display_name·영문(en)·knows_about·SEO 등 나머지는 그대로 보존한다.
반영 후 build.py 로 공개 소개페이지를 재빌드·재배포(자동 발행 브리지가 이 흐름을 돌린다).

편집 필드는 build_app.PROFILE_EDITABLE 과 동일해야 함(앱에 싣는 것 = 되받는 것).

사용법:
    python import_profile_edits.py edits.json --slug hayewoni
    (edits.json = 앱이 내보낸/브리지가 저장한 소개 편집 JSON. {"profile": {...}} 래핑도 허용)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

# 앱에서 편집 가능한 필드(= 반영 대상). 이 외(en·slug·display_name·korean_name·role·salon·
# knows_about·portfolio_labels·address_* 등)는 절대 건드리지 않는다.
EDITABLE = ("tagline", "about", "specialties", "portfolio_labels", "faq",
            "location", "booking_url", "instagram", "photo_url")


def apply_edits(profile: dict, edits: dict) -> dict:
    """편집 가능한 필드만 병합. 편집에 없는/빈 필드는 원본 유지(실수로 지우지 않음).

    profile(원본 dict)을 제자리 수정해 반환 — 기존 키 순서(YAML 필드 순서)는 보존된다."""
    if not isinstance(edits, dict):
        raise ValueError("edits 가 매핑(JSON object)이 아닙니다")
    for k in EDITABLE:
        if k not in edits:
            continue
        v = edits[k]
        if v is None or (isinstance(v, (str, list, dict)) and len(v) == 0):
            continue                       # 빈 값은 무시(기존 보존)
        profile[k] = v
    return profile


def changed_fields(edits: dict) -> list[str]:
    return [k for k in EDITABLE
            if k in edits and edits[k] not in (None, "", [], {})]


def load_edits(path: str | Path) -> dict:
    """편집 JSON 로드. {"profile": {...}} 래핑(앱 내보내기 형식)이면 벗겨낸다."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "profile" in data and isinstance(data["profile"], dict):
        return data["profile"]
    return data


def write_profile(path: str | Path, profile: dict) -> None:
    Path(path).write_text(
        yaml.safe_dump(profile, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="앱 소개 편집 → designers/{slug}.yaml 반영")
    ap.add_argument("edits", help="소개 편집 JSON 파일")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--designers-dir", default="designers")
    args = ap.parse_args()

    path = Path(args.designers_dir) / f"{args.slug}.yaml"
    if not path.exists():
        print(f"✗ 프로필 없음: {path}")
        return 1
    profile = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    edits = load_edits(args.edits)

    before = yaml.safe_dump(profile, allow_unicode=True, sort_keys=False)
    apply_edits(profile, edits)
    after = yaml.safe_dump(profile, allow_unicode=True, sort_keys=False)
    if before == after:
        print("· 변경 없음")
        return 0
    write_profile(path, profile)
    print(f"✓ {path} 반영: {', '.join(changed_fields(edits)) or '(구조)'} — build.py 로 재빌드하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
