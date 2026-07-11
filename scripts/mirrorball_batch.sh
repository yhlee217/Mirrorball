#!/bin/bash
# Mirrorball 10분 배치 — 하루치 결제(+정시 예약) 수집·병합·빌드·Netlify 자동배포.
# launchd(com.mirrorball.batch)가 스케줄대로 호출한다. 실데이터·자격증명은 로컬 전용.
#   자격증명: secrets/deploy.env (gitignore) — NETLIFY_AUTH_TOKEN, NETLIFY_SITE_ID.
#   수동 실행(스모크 테스트): bash scripts/mirrorball_batch.sh
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
export PATH="$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
PY="$ROOT/.venv/bin/python"
SLUG="${MIRRORBALL_SLUG:-hayewoni}"
ts() { date '+%F %T'; }

# 배포 자격증명(있으면 로드) — 없으면 데이터만 갱신하고 배포는 스킵.
if [ -f "$ROOT/secrets/deploy.env" ]; then
  set -a; . "$ROOT/secrets/deploy.env"; set +a
fi

# 예약(다가오는 예약)은 매시 정시(00분)에만 수집 → 결제는 매 10분, 예약은 시간당(로그인 절약).
RESERVE="--no-reserve"
[ "$(date +%M)" = "00" ] && RESERVE=""

# 1) 하루치 결제 + (정시)예약 수집 → records.yaml 누적 병합 → 데이터 빌드
if ! "$PY" scripts/handsos_sync.py --only "$SLUG" --days 1 $RESERVE; then
  echo "[$(ts)] X 수집 실패 — 이번 사이클 배포 건너뜀"
  exit 1
fi

# 2) 배포 번들(dist_app_site/{slug}) 재생성
if ! "$PY" build_app_site.py "clients/$SLUG"; then
  echo "[$(ts)] X 빌드 실패"
  exit 1
fi

# 3) 자동 배포 — NETLIFY_AUTH_TOKEN 은 netlify-cli 가 환경변수에서 읽는다.
if [ -n "${NETLIFY_AUTH_TOKEN:-}" ] && [ -n "${NETLIFY_SITE_ID:-}" ]; then
  echo "[$(ts)] deploy 시작 · netlify=$(command -v netlify || echo NOT_FOUND) · PATH=$PATH" >> "$ROOT/_raw/deploy.log"
  if netlify deploy --dir "dist_app_site/$SLUG" --prod --site "$NETLIFY_SITE_ID" \
       --message "batch $(ts)" >> "$ROOT/_raw/deploy.log" 2>&1; then
    echo "[$(ts)] OK 배포 완료 (site=$NETLIFY_SITE_ID)"
  else
    echo "[$(ts)] X 배포 실패 — 자세한 원인은 _raw/deploy.log 참고"
    exit 1
  fi
else
  echo "[$(ts)] . 배포 스킵(secrets/deploy.env 미설정) — 데이터만 갱신됨"
fi
