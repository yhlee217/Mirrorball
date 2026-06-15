"""data 검증 + placeholder 경고.

- 필수 필드 누락 시 ValueError (빌드 중단)
- 값에 '[' / ']' 가 남아있으면 "미입력 추정" 경고 (발행 사고 방지)
- booking_url / photo_url 비면 경고만 (플레이스홀더 동작)
"""

from __future__ import annotations

# 비어 있으면 안 되는 문자열 필드
REQUIRED_STR = ["slug", "display_name", "korean_name", "role", "salon", "instagram"]
# 최소 1개 이상이어야 하는 리스트 필드
REQUIRED_LIST = ["specialties", "faq", "knows_about"]


def _walk_placeholders(value, path: str, out: list[str]) -> None:
    """문자열에 '[' 또는 ']' 가 있으면 미입력 추정 경고를 모은다."""
    if isinstance(value, str):
        if "[" in value or "]" in value:
            shown = value if len(value) <= 40 else value[:40] + "…"
            out.append(f"미입력 추정: {path} = \"{shown}\"")
    elif isinstance(value, dict):
        for k, v in value.items():
            _walk_placeholders(v, f"{path}.{k}" if path else str(k), out)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _walk_placeholders(v, f"{path}[{i}]", out)


def validate(data: dict) -> list[str]:
    """경고 리스트를 반환. 필수 누락이면 ValueError 를 올린다."""
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_STR:
        if not (data.get(key) or "").strip() if isinstance(data.get(key), str) else not data.get(key):
            errors.append(f"필수 항목 누락: {key}")

    for key in REQUIRED_LIST:
        val = data.get(key)
        if not isinstance(val, list) or len(val) == 0:
            errors.append(f"필수 리스트 누락(최소 1개): {key}")

    # specialties 각 항목은 name/desc 필요
    for i, s in enumerate(data.get("specialties") or []):
        if not isinstance(s, dict) or not s.get("name"):
            errors.append(f"specialties[{i}].name 누락")
    # faq 각 항목은 q/a 필요
    for i, f in enumerate(data.get("faq") or []):
        if not isinstance(f, dict) or not f.get("q") or not f.get("a"):
            errors.append(f"faq[{i}] 의 q/a 누락")

    # (선택) portfolio 가 있으면 before/after 사진이 둘 다 필요
    for i, item in enumerate(data.get("portfolio") or []):
        if not isinstance(item, dict) or not item.get("before") or not item.get("after"):
            errors.append(f"portfolio[{i}] 는 before/after 사진이 모두 필요합니다")
    # (선택) menu 가 있으면 name/price 필요
    for i, m in enumerate(data.get("menu") or []):
        if not isinstance(m, dict) or not m.get("name") or not m.get("price"):
            errors.append(f"menu[{i}] 는 name/price 가 필요합니다")

    if errors:
        raise ValueError("입력 검증 실패:\n  - " + "\n  - ".join(errors))

    # --- 경고 (빌드는 계속) ---
    if not (data.get("photo_url") or "").strip():
        warnings.append("photo_url 비어 있음 → 이니셜 플레이스홀더로 출력")
    if not (data.get("booking_url") or "").strip():
        warnings.append("booking_url 비어 있음 → 예약 링크가 플레이스홀더로 출력")

    _walk_placeholders(data, "", warnings)
    return warnings
