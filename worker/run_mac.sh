#!/bin/bash
# ⚠ 2026-07-23 저빈도 재개(리스크 인지) — HandSOS 약관 19조1항17호(스크래핑 금지)는
#    빈도·목적과 무관한 금지라 위반 리스크는 남아 있음(계정 해지 시 잃는 쪽은 매장).
#    운영자 판단으로 '고객 관리용·주 1회'로만 재개. 탐지 확률은 낮지만 저확률·고피해 꼬리
#    리스크로 관리. 근본 해소는 '매장이 직접 내보낸 파일 읽기'로 전환 — LAUNCH.md 최상단 참조.
#
# Mirrorball v2 수집 — HandSOS 스크레이프 → Supabase 업서트. 국내 IP(이 맥)에서 실행.
# launchd(com.mirrorball.collect)가 주 1회(일요일 14:00 KST) 호출. 수동 테스트: FORCE=1 bash worker/run_mac.sh
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
# 주 1회 실행이라 한 번 걸러도 누락 없게 14일 겹침 창으로 수집(증분·과거 백필분은 보존).
SYNC_ALL=1 SYNC_DAYS="${SYNC_DAYS:-14}" "$PY" worker/run.py; rc=$?
echo "[$(ts)] collect 종료(exit=$rc)"
exit $rc
