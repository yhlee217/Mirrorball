"""운영 의존성 취약점 주간 점검(개선 계획 v14 P2) — GitHub Actions deps-audit 가 매주 월요일 돌린다.

web/ 의 `npm audit --omit=dev --json` 을 읽어 '높음 · 심각'이 있으면 실패한다(GitHub 가 저장소 주인에게 메일).
2026-10-15 에 처음 돌려 보니 Next 14 에 심각 · 높음이 여럿 걸려 있었는데 아무도 몰랐다 — 이제 매주 본다.

알고 받아들인 것(ACCEPTED)은 실패로 치지 않고 따로 적는다 — 매주 같은 이유로 빨갛게 끝나면 새 알림을 놓친다.
새 알림은 이 목록에 넣지 말고 의존성을 올려서 푼다.

사용:
    python3 scripts/deps_audit.py                 # web/ 에서 npm audit 를 돌려 판정
    python3 scripts/deps_audit.py 파일.json       # 미리 받아 둔 npm audit --json 결과로
종료 코드: 0 정상 · 1 받아들이지 않은 높음 · 심각이 있다 · 2 점검 실패(npm audit 결과를 못 읽음)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ACCEPTED = {
    "postcss": "Next 안에 든 빌드 도구 — 빌드 때 우리 CSS 만 처리해 바깥 입력이 닿지 않는다. Next 16 에서 풀린다(v14 §6)",
}


def judge(audit: dict) -> tuple[list[str], list[str]]:
    """(실패 줄, 받아들인 줄). 높음 · 심각만 본다. 다른 패키지 때문에만 걸린 것(via)은 그 패키지가 받아들인 것이면 함께 받아들인다."""
    bad: list[str] = []
    ok: list[str] = []
    for name, v in sorted((audit.get("vulnerabilities") or {}).items()):
        sev = v.get("severity")
        if sev not in ("high", "critical"):
            continue
        own = [x for x in v.get("via", []) if isinstance(x, dict)]
        via = [x for x in v.get("via", []) if isinstance(x, str)]
        if name in ACCEPTED:
            ok.append(f"{name}({sev}) — {ACCEPTED[name]}")
            continue
        if not own and via and all(n in ACCEPTED for n in via):
            ok.append(f"{name}({sev}) — {', '.join(via)} 때문에만")
            continue
        titles = "; ".join(str(x.get("title")) for x in own[:3]) or f"{', '.join(via)} 때문에"
        bad.append(f"{name}({sev}) — {titles}")
    return bad, ok


def _audit() -> dict:
    r = subprocess.run(["npm", "audit", "--omit=dev", "--json"], cwd=ROOT / "web", capture_output=True, text=True, timeout=180)
    return json.loads(r.stdout or "{}")  # 취약점이 있으면 npm 은 1 로 끝나지만 JSON 은 그대로 준다


def main(argv: list[str]) -> int:
    try:
        audit = json.loads(Path(argv[1]).read_text(encoding="utf-8")) if len(argv) > 1 else _audit()
    except Exception as exc:  # noqa: BLE001
        print(f"! npm audit 결과를 읽지 못했어요: {exc}")
        return 2
    if "vulnerabilities" not in audit:
        print(f"! npm audit 결과가 이상해요: {str(audit)[:200]}")
        return 2
    counts = (audit.get("metadata") or {}).get("vulnerabilities") or {}
    print("운영 의존성 취약점 — " + " · ".join(f"{k} {counts.get(k, 0)}" for k in ("critical", "high", "moderate", "low")))
    bad, ok = judge(audit)
    if ok:
        print("\n알고 받아들인 것")
        print("\n".join("  " + x for x in ok))
    if bad:
        print("\n받아들이지 않은 높음 · 심각 — 의존성을 올려 주세요")
        print("\n".join("  " + x for x in bad))
        return 1
    print("\n정상 — 받아들이지 않은 높음 · 심각 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
