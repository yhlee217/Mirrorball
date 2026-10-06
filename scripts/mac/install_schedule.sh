#!/usr/bin/env bash
# macOS 스케줄 등록기 — plist 의 {PROJECT}/{LOGS}/{SLUG} 를 실제 값으로 채워 설치·로드.
#   scripts/mac/install_schedule.sh              # collect(주 1회) + expose(주 1회)
#   scripts/mac/install_schedule.sh collect      # v2 수집만 — 평소 이것
#   scripts/mac/install_schedule.sh expose hayewoni
#   scripts/mac/install_schedule.sh handsos      # ⚠ v1 레거시(매일 03:10) — 아래 주의
#   scripts/mac/install_schedule.sh uninstall    # collect + expose 해제
#
# ⚠ handsos(v1, 매일 03:10)는 'all' 에서 뺐다. 수집은 2026-08 부터 주 1회(collect)로
#   낮춘 상태이고, 레거시가 같이 깔리면 실제 접속이 주 7회가 되어 그 결정이 무의미해진다.
#   필요하면 이름을 명시해서만 깔린다. 배경은 LAUNCH.md 최상단.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LA="$HOME/Library/LaunchAgents"
# launchd 가 스크립트 실행 전에 열어야 하는 로그 → 저장소 위치와 무관한 곳에 둔다.
# ~/Desktop 에 뒀다가 TCC 로 막혀 2개월간 조용히 실패했다(com.mirrorball.collect.plist 주석).
LOGS="$HOME/Library/Logs/Mirrorball"
SLUG="${2:-hayewoni}"
mkdir -p "$LA" "$LOGS" "$ROOT/runs"
chmod +x "$ROOT/scripts/mac/"*.sh 2>/dev/null || true

# TCC 보호 폴더 안이면 launchd 가 아예 못 띄운다 — 설치 전에 막는다.
case "$ROOT/" in
  "$HOME/Desktop/"*|"$HOME/Documents/"*|"$HOME/Downloads/"*)
    echo "X 저장소가 macOS 보호 폴더 안에 있습니다: $ROOT"
    echo "  launchd 가 /bin/bash 를 띄우지 못해(EPERM) 등록해도 매번 실패합니다."
    echo "  먼저 옮기세요:  bash scripts/mac/relocate.sh"
    exit 1 ;;
esac

_install() {   # $1=label  $2=src plist
  local label="$1" src="$2" dst="$LA/$1.plist"
  sed -e "s#{PROJECT}#$ROOT#g" -e "s#{LOGS}#$LOGS#g" -e "s#{SLUG}#$SLUG#g" "$src" > "$dst"
  launchctl unload "$dst" 2>/dev/null || true
  launchctl load "$dst"
  echo "[OK] $label 등록 → $dst"
}
_uninstall() {
  local dst="$LA/$1.plist"
  launchctl unload "$dst" 2>/dev/null || true
  rm -f "$dst"
  echo "[OK] $1 해제"
}

case "${1:-all}" in
  collect) _install com.mirrorball.collect "$ROOT/scripts/mac/com.mirrorball.collect.plist" ;;
  expose)  _install com.mirrorball.expose  "$ROOT/scripts/mac/com.mirrorball.expose.plist" ;;
  handsos)
    echo "⚠ v1 레거시(매일 03:10)를 설치합니다. 지금 운영 기준은 주 1회(collect)입니다."
    _install com.mirrorball.handsos "$ROOT/scripts/mac/com.mirrorball.handsos.plist" ;;
  all)
    _install com.mirrorball.collect "$ROOT/scripts/mac/com.mirrorball.collect.plist"
    _install com.mirrorball.expose  "$ROOT/scripts/mac/com.mirrorball.expose.plist" ;;
  uninstall)
    _uninstall com.mirrorball.collect; _uninstall com.mirrorball.expose ;;
  *) echo "사용: install_schedule.sh [all|collect|expose|handsos|uninstall] [slug]"; exit 2 ;;
esac

echo
echo "확인:  launchctl list | grep mirrorball        # 2번째 칸이 종료코드(0 이어야 정상)"
echo "       launchctl print gui/\$(id -u)/com.mirrorball.collect | grep 'last exit code'"
echo "즉시 1회 실행:  launchctl start com.mirrorball.collect"
echo "로그:  $LOGS/collect.out.log  ·  $ROOT/runs/memoai.log"
echo "※ Mac 이 그 시각 깨어 있어야 함(잠자기면 깨어난 뒤 밀린 작업 실행). 완전 종료면 실행 안 됨."
