"""업종별 카피 데이터 단일 로더 — kb/copy.yaml.

drafts.py·aftercare.py·build_app.py 가 공통으로 읽는다. 복제 시 yaml 만 교체.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

_PATH = Path(__file__).parent / "kb" / "copy.yaml"


@lru_cache(maxsize=1)
def load() -> dict:
    return yaml.safe_load(_PATH.read_text(encoding="utf-8")) or {}


def benefit() -> dict:
    return load().get("benefit", {}) or {}


def aftercare() -> dict:
    return load().get("aftercare", {}) or {}


def service_noun() -> str:
    return load().get("service_noun", "시술")


def business_type() -> str:
    return load().get("business_type", "HairSalon")
