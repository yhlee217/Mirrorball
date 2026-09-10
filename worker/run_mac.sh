#!/bin/bash
# ⚠ 2026-08-26 저빈도 재개(리스크 인지) — HandSOS 약관 19조1항17호(스크래핑 금지)는
#    빈도·목적과 무관한 금지라 위반 리스크는 남아 있음(계정 해지 시 잃는 쪽은 매장).
#    운영자 판단으로 '고객 관리용·주 1회'로만 재개. 탐지 확률은 낮지만 저확률·고피해 꼬리
#    리스크로 관리. 근본 해소는 '매장이 직접 내보낸 파일 읽기'로 전환 — LAUNCH.md 최상단 참조.
#
# Mirrorball v2 수집 — HandSOS 스크레이프 → Supabase 업서트. 국내 IP(이 맥)에서 실행.
# launchd(com.mirrorball.collect)가 주 1회(일요일 14:00 KST) 호출. 수동 테스트: FORCE=1 bash worker/run_mac.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
# claude CLI(메모 정리용)는 보통 ~/.local/bin 이나 npm 전역에 깔린다 — launchd 는 PATH 가 빈약해 명시.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
PY="$ROOT/.venv/bin/python"
ts() { date '+%F %T'; }

# ⚠ 영업시간(KST 10~21시) 밖이면 조용히 종료하던 가드를 뺐다(2026-09-10).
#    30분마다 돌던 시절엔 밤에 한 번 거르는 게 공짜였다. 주 1회로 바뀐 뒤로는 정반대다:
#    launchd 는 예약 시각에 맥이 자고 있으면 '깨어난 뒤'에 밀린 잡을 실행하는데,
#    그 시각이 밤 10시거나 아침 9시면 여기서 exit 0 으로 끝났다. 로그 한 줄 없이
#    일주일치가 통째로 사라지고, 앱에는 '8일 전' 같은 숫자만 남는다.
#    예약 시각(일 14:00)은 어차피 영업시간 안이라, 이 가드가 실제로 걸리는 경우는
#    '밀린 실행' 뿐이었다 — 즉 절대 걸러선 안 되는 바로 그 경우.

# 시크릿: web/.env.local 재사용(SUPABASE_SERVICE_ROLE_KEY, MIRRORBALL_KEK, NEXT_PUBLIC_SUPABASE_URL)
if [ -f "$ROOT/web/.env.local" ]; then
  set -a; . "$ROOT/web/.env.local"; set +a
else
  echo "[$(ts)] X web/.env.local 없음 — 시크릿 미로드"; exit 1
fi
export SUPABASE_URL="${SUPABASE_URL:-${NEXT_PUBLIC_SUPABASE_URL:-}}"

# Playwright 크로미움 확인 — 주 1회 배치라 한 번 실패하면 일주일을 통째로 놓친다.
# 브라우저가 없으면(플레이라이트 업데이트 후 흔함) 트레이스백 대신 고치는 법 한 줄로 끝낸다.
if ! "$PY" - >/dev/null 2>&1 <<'PYCHK'
import os, sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    sys.exit(0 if os.path.exists(p.chromium.executable_path) else 1)
PYCHK
then
  echo "[$(ts)] X Playwright 크로미움 없음 → 설치 후 재시도:  $PY -m playwright install chromium"
  exit 1
fi

echo "[$(ts)] collect 시작"
# 주 1회 실행이라 한 번 걸러도 누락 없게 14일 겹침 창으로 수집(증분·과거 백필분은 보존).
SYNC_ALL=1 SYNC_DAYS="${SYNC_DAYS:-14}" "$PY" worker/run.py; rc=$?
echo "[$(ts)] collect 종료(exit=$rc)"

# 매장 메모 AI 정리 — 수집으로 메모가 늘었을 수 있으니 이어서 한 번 돌린다.
# 메모가 그대로인 고객은 건너뛰므로 보통 몇 명만 처리된다. 실패해도 수집 결과는 유효하다.
if [ "$rc" -eq 0 ]; then
  echo "[$(ts)] 메모 정리 시작"
  # 한 번에 다 돌리면 구독 사용량이 크게 빠진다. 매주 조금씩 채우게 상한을 둔다
  # (최근 방문자부터 처리하므로 지금 만날 고객이 먼저 정리된다).
  LIMIT="${MEMO_LIMIT:-120}" "$PY" worker/summarize_memos.py || echo "[$(ts)] ! 메모 정리 건너뜀(claude CLI 미설치·로그인 필요 등) — 수집은 정상"
  echo "[$(ts)] 메모 정리 종료"
fi

exit $rc
