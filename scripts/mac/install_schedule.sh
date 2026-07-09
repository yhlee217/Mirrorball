#!/usr/bin/env bash
# macOS 스케줄 등록기 — plist 의 {PROJECT}/{SLUG} 를 실제 값으로 채워 LaunchAgents 에 설치·로드.
#   scripts/mac/install_schedule.sh              # 핸드SOS(매일) + 노출(매주) 둘 다
#   scripts/mac/install_schedule.sh handsos      # 핸드SOS만
#   scripts/mac/install_schedule.sh expose hayewoni
#   scripts/mac/install_schedule.sh uninstall    # 둘 다 해제
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LA="$HOME/Library/LaunchAgents"
SLUG="${2:-hayewoni}"
mkdir -p "$LA" "$ROOT/runs"
chmod +x "$ROOT/scripts/mac/"*.sh 2>/dev/null || true

_install() {   # $1=label  $2=src plist
  local label="$1" src="$2" dst="$LA/$1.plist"
  sed -e "s#{PROJECT}#$ROOT#g" -e "s#{SLUG}#$SLUG#g" "$src" > "$dst"
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
  handsos) _install com.mirrorball.handsos "$ROOT/scripts/mac/com.mirrorball.handsos.plist" ;;
  expose)  _install com.mirrorball.expose  "$ROOT/scripts/mac/com.mirrorball.expose.plist" ;;
  all)
    _install com.mirrorball.handsos "$ROOT/scripts/mac/com.mirrorball.handsos.plist"
    _install com.mirrorball.expose  "$ROOT/scripts/mac/com.mirrorball.expose.plist" ;;
  uninstall)
    _uninstall com.mirrorball.handsos; _uninstall com.mirrorball.expose ;;
  *) echo "사용: install_schedule.sh [all|handsos|expose|uninstall] [slug]"; exit 2 ;;
esac

echo
echo "확인:  launchctl list | grep mirrorball"
echo "즉시 1회 실행:  launchctl start com.mirrorball.handsos"
echo "로그:  $ROOT/sync.log  ·  $ROOT/runs/handsos.err.log"
echo "※ Mac 이 그 시각 깨어 있어야 함(잠자기면 깨어난 뒤 밀린 작업 실행). 완전 종료면 실행 안 됨."
