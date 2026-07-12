#!/bin/bash
# Mirrorball v2 수집 — HandSOS 스크레이프 → Supabase 업서트. 국내 IP(이 맥)에서 실행.
# launchd(com.mirrorball.collect)가 30분마다 호출. 수동 테스트: FORCE=1 bash worker/run_mac.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
PY="$ROOT/.venv/bin/python"
ts() { date '+%F %T'; }

# 영업시간(KST 10~21시)만 수집 — 그 외엔 조용히 종료(로그인 절약). FORCE=1 이면 무시.
H=$(date +%H)
if [ "${FORCE:-0}" != "1" ] && { [ "$H" -lt 10 ] || [ "$H" -gt 21 ]; }; then
  exit 0
fi

# 시크릿: web/.env.local 재사용(SUPABASE_SERVICE_ROLE_KEY, MIRRORBALL_KEK, NEXT_PUBLIC_SUPABASE_URL)
if [ -f "$ROOT/web/.env.local" ]; then
  set -a; . "$ROOT/web/.env.local"; set +a
else
  echo "[$(ts)] X web/.env.local 없음 — 시크릿 미로드"; exit 1
fi
export SUPABASE_URL="${SUPABASE_URL:-${NEXT_PUBLIC_SUPABASE_URL:-}}"

echo "[$(ts)] collect 시작"
SYNC_ALL=1 "$PY" worker/run.py; rc=$?
echo "[$(ts)] collect 종료(exit=$rc)"
exit $rc
