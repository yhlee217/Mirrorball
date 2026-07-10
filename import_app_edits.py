#!/usr/bin/env python3
"""앱 편집 → 카르테 역동기화 (파일 라운드트립 업스트림 동기화).

디자이너가 앱에서 넣은 수동 편집(생일·메모·취향·관계 등)을 앱 '내보내기' JSON 으로 받아
clients/{slug}/customers/{id}.yaml 에 되돌린다. 거래 필드(이력·매출)는 건드리지 않고,
앱 값이 '있을 때만' 덮어써(빈값 무시) HandSOS 데이터를 지우지 않는다.

병합 규칙·수동필드 집합은 import_handsos 와 단일 소스(_preserve_manual / _MANUAL_FIELDS)를
공유 — 드리프트 없음. 한 번 YAML 에 들어간 수동필드는 import_handsos 가 재동기화 때도 보존한다.

매칭 안 되는(앱에서 새로 추가·아직 custno 없는) 고객은 clients/{slug}/app_added.yaml 로
분리 저장 → 컨시어지가 검토 후 반영(자동 카드 생성으로 인한 중복 방지).

라운드트립:
  앱      : 고객 편집 → '내보내기'({slug}-customers.json) → 컨시어지에게 전달(카톡 등)
  컨시어지 : python import_app_edits.py clients/{slug} {slug}-customers.json → build_app → 배포

사용법:
    python import_app_edits.py clients/hayewoni hayewoni-customers.json
    python import_app_edits.py clients/hayewoni edits.json --dry
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from import_handsos import _MANUAL_FIELDS, _preserve_manual

_EMPTY = (None, "", [], {})


def load_app_export(path: str) -> list[dict]:
    """앱 내보내기 JSON → 고객 dict 리스트. 배열 또는 {customers|clients:[...]} 허용."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("customers") or data.get("clients") or []
    if not isinstance(data, list):
        raise ValueError("앱 내보내기 형식이 아닙니다(고객 배열이 필요합니다).")
    return [c for c in data if isinstance(c, dict)]


def apply_edits(client_dir: str | Path, app_custs: list[dict]) -> tuple[list, list]:
    """앱 고객 → 기존 YAML 에 수동필드 병합.

    반환: (updates, unmatched)
      updates   = [(path, merged_dict), …]  실제 변경이 있는 카르테만(불필요한 재기록 방지)
      unmatched = [app_cust, …]             매칭 YAML 없는(앱 추가) 고객

    거래 필드는 YAML(=new) 값 유지, 앱(=old)의 수동필드는 값 있을 때만 덮어씀
    (_preserve_manual 재사용 — 파이프라인과 동일 규칙)."""
    cdir = Path(client_dir) / "customers"
    updates, unmatched = [], []
    for ac in app_custs:
        cid = str(ac.get("id") or "").strip()
        p = cdir / f"{cid}.yaml"
        if not cid or not p.exists():
            unmatched.append(ac)
            continue
        old = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        merged = _preserve_manual(ac, old)      # old(거래) 유지 + ac(수동필드, 값 있을 때) 우선
        if merged != old:
            updates.append((p, merged))
    return updates, unmatched


def slim_for_review(app_custs: list[dict]) -> list[dict]:
    """검토 파일(app_added.yaml)용 — 이름·id·custno + 수동필드만(거래·PII 없음)."""
    keep = ("id", "name", "custno") + tuple(_MANUAL_FIELDS)
    return [{k: c[k] for k in keep if c.get(k) not in _EMPTY} for c in app_custs]


def _write_updates(updates: list) -> None:
    for p, merged in updates:
        p.write_text(yaml.safe_dump(merged, allow_unicode=True, sort_keys=False), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="앱 편집 JSON → 카르테 역동기화(수동필드)")
    ap.add_argument("client_dir", help="clients/{slug} 경로")
    ap.add_argument("export", help="앱 '내보내기' JSON 파일")
    ap.add_argument("--dry", action="store_true", help="저장하지 않고 미리보기")
    args = ap.parse_args()

    try:
        app_custs = load_app_export(args.export)
    except Exception as exc:
        print(f"✗ {exc}")
        return 1

    updates, unmatched = apply_edits(args.client_dir, app_custs)
    print(f"앱 고객 {len(app_custs)} · 갱신 대상 {len(updates)} · 미매칭(앱 추가) {len(unmatched)}")
    for p, merged in updates[:8]:
        fields = [f for f in _MANUAL_FIELDS if merged.get(f) not in _EMPTY]
        print(f"  · {merged.get('name', '?')} ({p.stem}) ← {', '.join(fields) or '수동필드'}")

    if args.dry:
        print("(--dry: 저장 안 함)")
        return 0

    _write_updates(updates)
    print(f"✓ 카르테 {len(updates)}개 수동필드 갱신")
    if unmatched:
        ap2 = Path(args.client_dir) / "app_added.yaml"
        ap2.write_text(yaml.safe_dump(slim_for_review(unmatched), allow_unicode=True, sort_keys=False),
                       encoding="utf-8")
        print(f"  · 미매칭 {len(unmatched)}명 → {ap2} (검토 후 반영 — 자동 카드 생성 안 함)")
    print("  다음 build_app 실행 시 앱에 반영. HandSOS 재동기화에도 유지(_MANUAL_FIELDS).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
