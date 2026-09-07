"""매장 메모 AI 정리 — 고객별 메모를 한 번에 읽어 몇 줄로 요약하고 DB 에 박아둔다.

왜 배치인가:
    HandSOS 매장 메모는 방문마다 한 줄씩 쌓여 중구난방이다("컬 약하게", "두피 예민", ...).
    화면을 열 때마다 AI 를 부르면 느리고 비싸므로, 맥에서 수집 직후 한 번 정리해 저장한다.
    앱은 customers.memo_ai 를 읽기만 한다.

개인정보:
    고객 이름·연락처는 테넌트 키로 암호화돼 있고, 이 스크립트는 **복호화하지 않는다**.
    AI 에 넘기는 것은 날짜와 메모 문장뿐이다(누구인지 모르는 상태로 요약).

재실행:
    메모 원본의 해시를 memo_ai_src 에 함께 저장해, 메모가 그대로면 건너뛴다.
    주 1회 배치에서 대부분은 호출 없이 지나간다. 전부 다시 만들려면 FORCE=1.

속도:
    claude CLI 한 번이 기동+응답에 십수 초~1분이라 순차로 돌리면 몇십 명만 돼도 하염없다.
    모델은 판단 품질 때문에 낮추지 않고, 대신 여러 명을 동시에 돌려 벽시계 시간을 줄인다.
    JOBS 를 올리면 그만큼 빨라진다(맥 사양·요금제에 맞춰 4~8 권장).

사용:
    .venv/bin/python worker/summarize_memos.py            # 바뀐 고객만
    FORCE=1 .venv/bin/python worker/summarize_memos.py    # 전부 다시
    LIMIT=5 .venv/bin/python worker/summarize_memos.py    # 5명만(시험)
    JOBS=8 .venv/bin/python worker/summarize_memos.py     # 동시 실행 수(기본 4)
    MODEL=opus .venv/bin/python ...                       # 모델 변경(기본 sonnet), MODEL= 로 지정 해제
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env() -> None:
    p = ROOT / "web" / ".env.local"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    if not os.environ.get("SUPABASE_URL") and os.environ.get("NEXT_PUBLIC_SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = os.environ["NEXT_PUBLIC_SUPABASE_URL"]


_load_env()

import supa  # noqa: E402

MAX_MEMOS = 40          # 한 고객당 최근 메모 상한(프롬프트 길이 방어)
CLI_TIMEOUT = 180
# 단순 요약이 아니다 — "지난번엔 밝게, 최근엔 어둡게"처럼 시간에 따라 뒤집히는 걸 정리하고,
# 지속되는 선호와 한 번뿐인 잡담을 갈라내야 한다. 판단이 필요한 일이라 작은 모델은 쓰지 않는다.
MODEL = os.environ.get("MODEL", "sonnet")


def run_claude(prompt: str) -> str | None:
    """Claude CLI(`claude -p`) 호출. 설치/로그인 안 돼 있으면 None."""
    cmd = ["claude", "-p", prompt] + (["--model", MODEL] if MODEL else [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=CLI_TIMEOUT)
        out = (r.stdout or "").strip()
        if not out and MODEL and "--model" in (r.stderr or ""):
            # 이 CLI 버전이 --model 을 모르면 한 번은 빼고 재시도
            r = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=CLI_TIMEOUT)
            out = (r.stdout or "").strip()
        return out or None
    except FileNotFoundError:
        print("❌ claude CLI 가 없습니다. 설치 후 로그인하세요: https://claude.com/claude-code", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"  (claude 호출 실패, 건너뜀): {exc}", file=sys.stderr)
        return None


def summarize_one(job: dict) -> tuple[str, str | None]:
    """한 고객 요약 — 스레드에서 실행. (customer_id, 요약문|None)"""
    out = run_claude(build_prompt(job["memos"]))
    return job["cid"], (clean_output(out) if out else None)


def build_prompt(lines: list[str]) -> str:
    """lines: '2026-06-01 컬 약하게' 처럼 날짜가 붙은 메모들(오래된 순).
    날짜가 있어야 '최근에는 ~' 같은 시간 판단이 가능하다."""
    joined = "\n".join(lines)
    return (
        "너는 미용실 디자이너를 돕는 조수다. 아래는 한 고객에 대해 매장에서 방문마다 적어둔 메모들이다.\n"
        "디자이너가 이 고객을 다시 맞을 때 3초 안에 파악할 수 있게 정리해라.\n\n"
        "규칙:\n"
        "- 한국어. 불릿 2~4개. 각 줄 25자 내외.\n"
        "- 메모에 실제로 있는 내용만. 없는 사실을 지어내지 마라.\n"
        "- 반복되는 선호·주의사항을 우선(예: 밝기 선호, 두피 예민, 컬 세기).\n"
        "- 시간에 따라 내용이 뒤집히면 날짜를 보고 최근 것을 따르되 '최근에는 ~' 으로 적어라.\n"
        "- 여러 번 반복되는 것은 지속 선호, 한 번뿐인 것은 그날 사정으로 보고 구분해라.\n"
        "- 한 번뿐인 잡담성 메모는 빼라.\n"
        "- 인사말·머리말·설명 없이 불릿만 출력. 각 줄은 '- ' 로 시작.\n\n"
        f"메모(오래된 순):\n{joined}\n"
    )


def clean_output(text: str) -> str | None:
    """불릿만 남긴다 — 모델이 붙이는 서두·코드펜스 제거."""
    out = []
    for raw in text.splitlines():
        line = raw.strip().strip("`").strip()
        if not line or line.startswith("```"):
            continue
        if line.startswith(("- ", "• ", "* ")):
            out.append("- " + line[2:].strip())
        elif out:
            break  # 불릿이 끝나면 뒤 설명은 버린다
    return "\n".join(out[:4]) if out else None


def main() -> int:
    force = bool(os.environ.get("FORCE"))
    limit = int(os.environ.get("LIMIT") or 0)
    jobs_n = max(1, int(os.environ.get("JOBS") or 4))
    t0 = time.time()

    # ── 1) 대상 선별 (AI 호출 전) ─────────────────────────────
    print("대상 고르는 중…", flush=True)
    tenants = supa._get("/tenants", {"select": "id,slug", "order": "slug"})
    todo: list[dict] = []

    for t in tenants:
        tid, slug = t["id"], t.get("slug") or t["id"][:8]

        # 메모가 달린 거래만. 이름은 읽지 않는다(복호화 안 함).
        txs = supa.select_all("transactions", tid, "customer_id,date,memo")
        by_cust: dict[str, list[tuple[str, str]]] = {}
        for r in txs:
            memo = (r.get("memo") or "").strip()
            if not r.get("customer_id") or not memo:
                continue
            by_cust.setdefault(r["customer_id"], []).append((r.get("date") or "", memo))

        if not by_cust:
            print(f"  [{slug}] 메모 있는 고객 없음")
            continue

        existing = {c["id"]: c.get("memo_ai_src") for c in supa.select_all("customers", tid, "id,memo_ai_src")}

        picked = skipped = 0
        for cid, rows in by_cust.items():
            rows.sort(key=lambda x: x[0])                 # 오래된 순
            rows = rows[-MAX_MEMOS:]
            # 메모가 한 줄뿐이면 요약할 게 없다 — AI 를 부르지 않는다.
            if len(rows) < 2:
                skipped += 1
                continue
            src = hashlib.sha256("\n".join(f"{d} {m}" for d, m in rows).encode("utf-8")).hexdigest()
            if not force and existing.get(cid) == src:
                skipped += 1
                continue
            todo.append({"cid": cid, "src": src,
                         "memos": [f"{d} {m}" for d, m in rows],  # 날짜 포함 — 모순 해소용
                         "slug": slug})
            picked += 1
        print(f"  [{slug}] 대상 {picked}명 · 변경 없어 건너뜀 {skipped}명")

    if not todo:
        print("정리할 고객 없음 — 이미 최신입니다")
        return 0

    if limit:
        todo = todo[:limit]
    total = len(todo)
    print(f"\n{total}명 정리 시작 · 동시 {jobs_n}개 · 모델 {MODEL or '기본'}", flush=True)
    print("(claude CLI 한 번에 10~40초 걸립니다)", flush=True)

    # ── 2) 병렬 요약 ──────────────────────────────────────────
    done = failed = 0
    by_id = {j["cid"]: j for j in todo}
    with ThreadPoolExecutor(max_workers=jobs_n) as pool:
        futs = {pool.submit(summarize_one, j): j["cid"] for j in todo}
        for fut in as_completed(futs):
            cid, summary = fut.result()
            if not summary:
                failed += 1
                print(f"  [{done + failed}/{total}] {cid[:8]} 실패", flush=True)
                continue
            supa.patch("customers", {"id": f"eq.{cid}"}, {
                "memo_ai": summary,
                "memo_ai_at": datetime.now(timezone.utc).isoformat(),
                "memo_ai_src": by_id[cid]["src"],
            })
            done += 1
            first = summary.splitlines()[0][:34] if summary else ""
            print(f"  [{done + failed}/{total}] {cid[:8]} ✓ {first}", flush=True)

    took = int(time.time() - t0)
    print(f"\n완료: {done}명 갱신" + (f" · 실패 {failed}명" if failed else "") + f" · {took//60}분 {took%60}초")
    if limit and total == limit:
        print("LIMIT 로 잘린 상태 — 전체는 LIMIT 없이 다시 실행하세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
