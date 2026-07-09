#!/usr/bin/env bash
# HandSOS 동기화 러너 (macOS). launchd/cron 이 호출. 한글 출력 위해 UTF-8 고정.
# 예: scripts/mac/run_sync.sh --all-designers   /   scripts/mac/run_sync.sh --only hayewoni
set -uo pipefail
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
export LANG="${LANG:-ko_KR.UTF-8}"

cd "$(dirname "$0")/../.."                 # 저장소 루트(이 스크립트는 scripts/mac 안)

PY="python3"
[ -x ".venv/bin/python" ] && PY=".venv/bin/python"   # venv 있으면 우선

echo "[$(date '+%F %T')] sync start $*" >> sync.log
"$PY" scripts/handsos_sync.py "$@" >> sync.log 2>&1
RC=$?
echo "[$(date '+%F %T')] sync end (exit $RC)" >> sync.log
exit $RC
