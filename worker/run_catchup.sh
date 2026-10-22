#!/bin/bash
# 맥을 켤 때 밀린 수집 — launchd(com.mirrorball.catchup)가 로그인할 때 부른다(2026-10-21).
# 판단은 worker/catchup.py: 지난 일요일 수집 차례(일 14:00) 뒤로 성공이 없을 때만 평소 수집(run_mac.sh — 백업까지)을 한 번 돌린다.
# 다른 맥 작업처럼 /bin/bash 로 띄운다(scripts/mac/*.plist — TCC 보호 폴더 밖 저장소 전제).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1
exec "$ROOT/.venv/bin/python" worker/catchup.py
