#!/usr/bin/env bash
# 발견케어(노출) 주간 측정 러너 (macOS, headless). launchd/cron 이 호출.
# 예: scripts/mac/run_expose_auto.sh hayewoni
set -uo pipefail
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
export LANG="${LANG:-ko_KR.UTF-8}"

cd "$(dirname "$0")/../.."
PY="python3"
[ -x ".venv/bin/python" ] && PY=".venv/bin/python"

SLUG="${1:-hayewoni}"
echo "[$(date '+%F %T')] expose start ($SLUG)" >> expose.log
"$PY" expose.py "clients/$SLUG" --measure --place --rank >> expose.log 2>&1
RC=$?
"$PY" build_app.py "clients/$SLUG" >> expose.log 2>&1
echo "[$(date '+%F %T')] expose end (exit $RC)" >> expose.log
exit $RC
