#!/usr/bin/env python3
"""핸드SOS 스크래퍼 자가 치유 — 실패 DOM 을 Claude(CLI)에 보여 바뀐 셀렉터를 다시 찾게 한다.

핸드SOS UI 가 바뀌어 수집이 깨지면, 사람이 F12 로 셀렉터를 뒤지는 대신 Claude 가 진단·수리:
  python scripts/handsos_heal.py --slug hayewoni           # 최신 실패 진단 → 셀렉터 제안 출력
  python scripts/handsos_heal.py --slug hayewoni --apply   # 제안을 secrets/{slug}.selectors.yaml 로 적용
  python scripts/handsos_heal.py --slug hayewoni --fail <dir>   # 특정 실패 폴더 지정

Claude CLI(`claude -p`, API키 불필요·구독 사용)를 호출한다. CLI 가 없으면 프롬프트를
clients/{slug}/_raw/heal_prompt.txt 로 떨궈 사람이 직접 Claude 에 붙여넣게 한다.

적용 후 반드시 검증:  python scripts/handsos_sync.py --only {slug} --headed
오버라이드는 secrets/{slug}.selectors.yaml(자동 git 제외)이며, sync 가 코드 수정 없이 읽는다.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

# 현재(기본) 셀렉터 — 단일 진실(scripts/handsos_selectors.yaml)에서 읽는다. sync 와 항상 동일.
def _load_sel() -> dict:
    p = ROOT / "scripts" / "handsos_selectors.yaml"
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


_SEL = _load_sel()
CURRENT = {"login": _SEL.get("login") or {}, "report": _SEL.get("report") or {}}
ANCHORS = tuple(_SEL.get("anchors") or
                ("strDateS", "list_tbl", "고객명", "companyID", "DBProc", "icogSearch"))


def find_latest_fail(slug: str, fail: str | None = None) -> Path | None:
    if fail:
        p = Path(fail)
        return p if p.exists() else None
    base = ROOT / "clients" / slug / "_raw"
    fails = sorted(base.glob("fail_*"), reverse=True) if base.exists() else []
    return fails[0] if fails else None


def pick_relevant_html(fail_dir: Path, budget: int = 14000) -> str:
    """실패 폴더의 page*.html 중 폼/표가 든 구간을 앵커 기준으로 잘라낸다(프롬프트 절약)."""
    htmls = sorted(fail_dir.glob("page*.html"))
    best = ""
    for h in htmls:
        txt = h.read_text(encoding="utf-8", errors="replace")
        score = sum(txt.count(a) for a in ANCHORS)
        if score > sum(best.count(a) for a in ANCHORS):
            best = txt
    if not best:
        return ""
    pos = min((best.find(a) for a in ANCHORS if best.find(a) >= 0), default=0)
    start = max(0, pos - budget // 3)
    return best[start:start + budget]


def build_prompt(slug: str, html: str, error: str) -> str:
    cur = yaml.safe_dump(CURRENT, allow_unicode=True, sort_keys=False)
    return (
        "핸드SOS '매출상세목록' 페이지를 자동 스크래핑하는데 셀렉터가 안 먹어 실패했어.\n"
        f"실패 사유: {error}\n\n"
        "아래는 현재 쓰는 셀렉터(이게 더 이상 안 맞을 수 있음):\n"
        f"```yaml\n{cur}```\n\n"
        "아래는 실패 시점 페이지 HTML 일부야. 이걸 보고 다음 요소의 '현재' CSS 셀렉터/함수를 찾아줘:\n"
        "- 회사코드/아이디/비번 input, 로그인 버튼\n"
        "- 시작일/종료일 input, 검색 실행(버튼 셀렉터 또는 JS 함수), 결과 표(고객명·날짜 든 table)\n\n"
        "반드시 아래 형식의 YAML 만(설명 없이, 코드펜스로) 출력해. 안 바뀐 항목은 빼도 됨:\n"
        "```yaml\n"
        "login:\n  fields:\n    company_code: \"...\"\n  submit: \"...\"\n"
        "report:\n  date_from_sel: \"...\"\n  date_to_sel: \"...\"\n"
        "  search_sel: \"...\"\n  search_js: \"...\"\n  result_table: \"...\"\n"
        "```\n\n"
        f"--- HTML ---\n{html}\n"
    )


def run_claude(prompt: str, timeout: int = 180) -> str | None:
    """Claude CLI(`claude -p`) 호출. 없으면 None."""
    try:
        r = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or None
    except FileNotFoundError:
        return None
    except Exception as exc:
        print(f"[claude 호출 실패] {exc}", file=sys.stderr)
        return None


def parse_selectors(output: str) -> dict:
    """Claude 출력에서 yaml 코드펜스(또는 평문 yaml) 추출."""
    m = re.search(r"```(?:yaml)?\s*(.+?)```", output, re.S)
    block = m.group(1) if m else output
    try:
        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser(description="핸드SOS 스크래퍼 자가 치유(Claude)")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--fail", help="특정 실패 폴더 경로(기본: 최신)")
    ap.add_argument("--apply", action="store_true", help="제안을 secrets/{slug}.selectors.yaml 로 저장")
    args = ap.parse_args()

    fail_dir = find_latest_fail(args.slug, args.fail)
    if not fail_dir:
        print(f"✗ 실패 폴더 없음: clients/{args.slug}/_raw/fail_*  (먼저 동기화가 실패해야 생김)")
        return 2
    err = ""
    ep = fail_dir / "error.txt"
    if ep.exists():
        err = ep.read_text(encoding="utf-8", errors="replace").strip()[:300]
    html = pick_relevant_html(fail_dir)
    if not html:
        print(f"✗ DOM(page*.html) 없음: {fail_dir}")
        return 2

    prompt = build_prompt(args.slug, html, err)
    print(f"▶ 실패 폴더: {fail_dir}\n▶ Claude 로 셀렉터 진단 중…")
    out = run_claude(prompt)
    if out is None:
        pf = fail_dir / "heal_prompt.txt"
        pf.write_text(prompt, encoding="utf-8")
        print(f"ℹ Claude CLI 미설치 → 프롬프트 저장: {pf}\n  이 파일을 Claude 에 붙여넣고, 받은 yaml 을\n"
              f"  secrets/{args.slug}.selectors.yaml 로 저장하세요.")
        return 0

    sel = parse_selectors(out)
    if not sel:
        print("✗ 제안 파싱 실패. Claude 원문:\n" + out[:1500])
        return 1

    text = yaml.safe_dump(sel, allow_unicode=True, sort_keys=False)
    print("\n── 제안된 셀렉터 ──\n" + text)
    if args.apply:
        outp = ROOT / "secrets" / f"{args.slug}.selectors.yaml"
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(text, encoding="utf-8")
        print(f"✓ 적용: {outp}\n  검증:  python scripts/handsos_sync.py --only {args.slug} --headed")
    else:
        print("적용하려면 --apply 를 붙이세요(또는 위 yaml 을 직접 저장).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
