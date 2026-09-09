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

사용량:
    고객 1명당 호출 1번이면 1,300명에 1,300번이라 구독 사용량이 순식간에 녹는다.
    BATCH 명씩 한 프롬프트에 묶어 호출 수를 그만큼 줄인다(기본 6 → 약 1/6).

속도:
    claude CLI 한 번이 기동+응답에 십수 초~1분이라 순차로 돌리면 몇십 명만 돼도 하염없다.
    모델은 판단 품질 때문에 낮추지 않고, 대신 여러 명을 동시에 돌려 벽시계 시간을 줄인다.
    JOBS 를 올리면 그만큼 빨라진다(맥 사양·요금제에 맞춰 4~8 권장).

사용:
    .venv/bin/python worker/summarize_memos.py            # 바뀐 고객만
    FORCE=1 .venv/bin/python worker/summarize_memos.py    # 전부 다시
    LIMIT=5 .venv/bin/python worker/summarize_memos.py    # 5명만(시험)
    CHECK=1 .venv/bin/python worker/summarize_memos.py    # CLI 가 되는지만 점검
    USE_API_KEY=1 .venv/bin/python ...                    # 구독 대신 ANTHROPIC_API_KEY 로 청구
    JOBS=8 .venv/bin/python worker/summarize_memos.py     # 동시 실행 수(기본 4)
    BATCH=20 .venv/bin/python worker/summarize_memos.py   # 1회 호출에 묶을 고객 수(기본 12)
    ACTIVE_MONTHS=12 .venv/bin/python ...                 # 최근 12개월 방문 고객만(기본: 전체)
    MODEL=opus .venv/bin/python ...                       # 모델 변경(기본 sonnet), MODEL= 로 지정 해제
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone

from env import load_env

load_env()




import supa  # noqa: E402

MAX_MEMOS = 40          # 한 고객당 최근 메모 상한(프롬프트 길이 방어)
# 단순 요약이 아니다 — "지난번엔 밝게, 최근엔 어둡게"처럼 시간에 따라 뒤집히는 걸 정리하고,
# 지속되는 선호와 한 번뿐인 잡담을 갈라내야 한다. 판단이 필요한 일이라 작은 모델은 쓰지 않는다.
# 프롬프트가 바뀌면 기존 요약은 형식이 달라 못 쓴다. 해시에 섞어 자동으로 다시 만들게 한다.
# claude -p 는 단순 모델 호출이 아니라 Claude Code 에이전트를 띄운다. 실측 결과 프롬프트가
# 10토큰이어도 시스템 프롬프트·툴 정의로 호출당 약 3만 토큰이 붙는다(대부분 캐시 읽기).
# 즉 비용은 '메모 길이'가 아니라 '호출 횟수'가 정한다 — 1,300명을 1명씩 부르면 4천만 토큰,
# 20명씩 묶으면 200만 토큰. 그래서 최대한 크게 묶는다.
#
# 참고: --system-prompt 로 껍데기를 줄이려 하면 오히려 손해다. 기본 시스템 프롬프트는
# 호출 간 캐시로 재사용(1/10 가격)되는데, 직접 지정하면 캐시가 깨져 매번 새로 쓴다.
BATCH = max(1, int(os.environ.get("BATCH") or 12))
# 2년 전 한 번 오고 안 오는 고객까지 정리해봐야 그 카르테는 열릴 일이 없다.
# 최근 N개월 안에 다녀간 고객만 대상으로 잡아 일 자체를 줄인다(0 이면 전체).
ACTIVE_MONTHS = int(os.environ.get("ACTIVE_MONTHS") or 0)


from claude_cli import MODEL, check_cli, print_usage  # noqa: E402
from memo_prompt import PROMPT_VERSION, summarize_batch  # noqa: E402

def preflight_columns() -> None:
    """쓸 컬럼이 실제로 있는지 먼저 확인한다.

    없으면 AI 를 다 부른 뒤 저장 단계에서 400 이 나 그때까지의 호출이 통째로 버려진다
    (1,300명 배치에서는 한 시간을 날린다). 그래서 호출 전에 한 번 찔러보고 멈춘다.
    """
    need = "id,memo_ai,memo_ai_recent,memo_ai_at,memo_ai_src"
    try:
        supa._get("/customers", {"select": need, "limit": "1"})
    except RuntimeError as exc:
        msg = str(exc)
        if "memo_ai" not in msg and "PGRST204" not in msg:
            raise
        print("❌ customers 에 필요한 컬럼이 없습니다(마이그레이션 미적용).", file=sys.stderr)
        print("   Supabase SQL Editor 에서 아래를 실행한 뒤 다시 돌리세요:\n", file=sys.stderr)
        print("   alter table customers add column if not exists memo_ai        text;", file=sys.stderr)
        print("   alter table customers add column if not exists memo_ai_at     timestamptz;", file=sys.stderr)
        print("   alter table customers add column if not exists memo_ai_src    text;", file=sys.stderr)
        print("   alter table customers add column if not exists memo_ai_recent text;", file=sys.stderr)
        print("\n   이미 실행했는데도 이 메시지가 나오면 스키마 캐시가 덜 갱신된 것:", file=sys.stderr)
        print("   notify pgrst, 'reload schema';", file=sys.stderr)
        raise SystemExit(1)


def main() -> int:
    if os.environ.get("CHECK"):
        return check_cli()

    preflight_columns()          # 컬럼부터 확인 — AI 호출을 낭비하지 않게
    cutoff = ""
    if ACTIVE_MONTHS:
        cutoff = str(date.today() - timedelta(days=30 * ACTIVE_MONTHS))
        print(f"최근 {ACTIVE_MONTHS}개월({cutoff} 이후) 방문 고객만 대상")
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
            if cutoff and rows[-1][0] < cutoff:   # 오래 안 온 고객은 건너뛴다
                skipped += 1
                continue
            src = hashlib.sha256(
                (PROMPT_VERSION + "\n" + "\n".join(f"{d} {m}" for d, m in rows)).encode("utf-8")
            ).hexdigest()
            if not force and existing.get(cid) == src:
                skipped += 1
                continue
            todo.append({"cid": cid, "src": src, "slug": slug,
                         "last": rows[-1][0],                     # 최근 메모 날짜 — 처리 순서용
                         "memos": [f"{d} {m}" for d, m in rows]})  # 날짜 포함 — 모순 해소용
            picked += 1
        print(f"  [{slug}] 대상 {picked}명 · 변경 없어 건너뜀 {skipped}명")

    if not todo:
        print("정리할 고객 없음 — 이미 최신입니다")
        return 0

    # 최근에 다녀간 고객부터. 중간에 멈춰도 지금 만날 사람들이 먼저 끝나 있게.
    todo.sort(key=lambda j: j["last"], reverse=True)
    if limit:
        todo = todo[:limit]
    total = len(todo)
    batches = [todo[i:i + BATCH] for i in range(0, total, BATCH)]
    print(f"\n{total}명 정리 시작 · {len(batches)}회 호출(1회당 {BATCH}명) · 동시 {jobs_n} · 모델 {MODEL or '기본'}",
          flush=True)

    done = failed = 0
    by_id = {j["cid"]: j for j in todo}
    with ThreadPoolExecutor(max_workers=jobs_n) as pool:
        futs = [pool.submit(summarize_batch, b) for b in batches]
        for fut in as_completed(futs):
            for cid, summary, recent, why in fut.result():
                if not summary:
                    failed += 1
                    print(f"  [{done + failed}/{total}] {cid[:8]} 실패 — {why}", flush=True)
                    continue
                supa.patch("customers", {"id": f"eq.{cid}"}, {
                    "memo_ai": summary,
                    "memo_ai_recent": recent,      # 없으면 null 로 덮어 옛 근황이 남지 않게
                    "memo_ai_at": datetime.now(timezone.utc).isoformat(),
                    "memo_ai_src": by_id[cid]["src"],
                })
                done += 1
                first = summary.splitlines()[0][:30]
                print(f"  [{done + failed}/{total}] {cid[:8]} ✓{' +근황' if recent else ''} {first}", flush=True)

    print_usage()
    took = int(time.time() - t0)
    print(f"\n완료: {done}명 갱신" + (f" · 실패 {failed}명" if failed else "") + f" · {took//60}분 {took%60}초")
    if limit and total == limit:
        print("LIMIT 로 잘린 상태 — 전체는 LIMIT 없이 다시 실행하세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
