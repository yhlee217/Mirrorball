#!/usr/bin/env bash
# 저장소를 macOS 보호 폴더(~/Desktop · ~/Documents · ~/Downloads) 밖으로 옮긴다.
#
# 왜 — 2026-08~10, 저장소가 ~/Desktop 에 있어서 주간 수집이 1392번 연속 실패했다.
#      macOS 는 이 세 폴더를 TCC 로 보호하고, launchd(xpcproxy)는 그 안으로 chdir 하거나
#      로그를 열 수 없어 posix_spawn(/bin/bash) 이 EPERM 으로 죽는다. 11ms 만에.
#      스크립트가 한 줄도 안 돌으니 로그도, 알림도, 사람이 볼 흔적도 남지 않는다.
#      터미널에서 직접 돌리면 Terminal 의 권한을 쓰므로 잘 된다 — 그래서 더 안 보였다.
#
# 하는 일 — 옮기기 → .venv 재생성(절대 경로가 박혀 있어 이동만으로는 깨진다)
#           → 크로미움 설치 → launchd 재등록 → 실제로 띄워지는지 확인.
#
# 안전 — 지우는 동작이 없다. mv 와 새 .venv 생성뿐이다. 추적되지 않는 파일
#        (web/.env.local · secrets/ · runs/ 등)도 함께 따라간다.
#
# 사용:
#     bash scripts/mac/relocate.sh                 # → ~/Dev/Mirrorball
#     bash scripts/mac/relocate.sh ~/work/Mirrorball
#     YES=1 bash scripts/mac/relocate.sh           # 확인 질문 생략
set -uo pipefail

# 이 스크립트는 옮겨지는 디렉토리 안에 있다 → /tmp 로 복사해 거기서 다시 실행한다.
# (실행 중에 제 발밑이 사라지는 상황을 아예 만들지 않는다)
if [ "${MB_RELOCATED_SELF:-0}" != "1" ]; then
  SELF_SRC="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  # -t 는 BSD/GNU 동작이 달라 템플릿을 직접 준다(둘 다 동작)
  SELF_TMP="$(mktemp "${TMPDIR:-/tmp}/mb_relocate.XXXXXX")" || exit 1
  cp "$SELF_SRC" "$SELF_TMP" || exit 1
  SRC_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
  MB_RELOCATED_SELF=1 MB_SRC="$SRC_ROOT" exec /bin/bash "$SELF_TMP" "$@"
fi

SRC="${MB_SRC:?}"
DST="${1:-$HOME/Dev/Mirrorball}"
DST="${DST/#\~/$HOME}"
LOGS="$HOME/Library/Logs/Mirrorball"
AGENTS="com.mirrorball.collect com.mirrorball.expose com.mirrorball.handsos"

say() { echo "[$(date '+%H:%M:%S')] $*"; }
die() { echo "X $*" >&2; exit 1; }

[ -d "$SRC" ]        || die "원본이 없습니다: $SRC"
[ "$SRC" != "$DST" ] || die "원본과 대상이 같습니다: $SRC"
[ -e "$DST" ]        && die "대상이 이미 있습니다: $DST  (다른 경로를 주세요)"
case "$DST/" in
  "$HOME/Desktop/"*|"$HOME/Documents/"*|"$HOME/Downloads/"*)
    die "대상도 보호 폴더입니다: $DST — 옮기는 의미가 없습니다" ;;
esac
command -v python3 >/dev/null || die "python3 가 없습니다"

echo
echo "  옮김:  $SRC"
echo "    →    $DST"
echo "  이후:  .venv 재생성 · 크로미움 설치 · launchd 재등록"
echo
if [ "${YES:-0}" != "1" ]; then
  printf "진행할까요? (yes 입력): "
  read -r ans
  [ "$ans" = "yes" ] || die "취소했습니다(아무것도 바뀌지 않았습니다)"
fi

say "launchd 에이전트 해제"
for a in $AGENTS; do
  launchctl unload "$HOME/Library/LaunchAgents/$a.plist" 2>/dev/null || true
done

say "이동"
mkdir -p "$(dirname "$DST")" || die "대상 상위 폴더를 만들 수 없습니다"
mv "$SRC" "$DST" || die "이동 실패 — 아무것도 바뀌지 않았습니다"
cd "$DST" || die "이동 후 진입 실패: $DST"

say ".venv 재생성 (옛 .venv 는 경로가 박혀 있어 못 씁니다)"
[ -d .venv ] && mv .venv ".venv.old-$(date +%Y%m%d%H%M%S)"
python3 -m venv .venv            || die "venv 생성 실패"
./.venv/bin/pip -q install --upgrade pip >/dev/null 2>&1 || true
./.venv/bin/pip -q install -r worker/requirements.txt \
  || die "의존성 설치 실패 — 네트워크를 확인하고 다시: ./.venv/bin/pip install -r worker/requirements.txt"

say "Playwright 크로미움"
./.venv/bin/python -m playwright install chromium \
  || echo "  ! 크로미움 설치 실패 — run_mac.sh 가 다음 실행 때 다시 시도합니다"

say "launchd 재등록"
mkdir -p "$LOGS"
bash scripts/mac/install_schedule.sh collect || die "등록 실패"

say "실제로 띄워지는지 확인 (이게 이번 문제의 핵심)"
launchctl start com.mirrorball.collect 2>/dev/null || true
sleep 4
code="$(launchctl print "gui/$(id -u)/com.mirrorball.collect" 2>/dev/null \
        | sed -n 's/.*last exit code = \([0-9]*\).*/\1/p' | head -1)"
echo
if [ -z "$code" ]; then
  echo "? 종료코드를 읽지 못했습니다 — 직접:  launchctl print gui/\$(id -u)/com.mirrorball.collect | grep 'last exit'"
elif [ "$code" = "78" ]; then
  echo "X 여전히 78(EX_CONFIG) — launchd 가 아직 /bin/bash 를 못 띄웁니다."
  echo "  시스템 설정 → 일반 → 로그인 항목 및 확장 → '백그라운드에서 허용' 에서"
  echo "  Mirrorball 항목이 켜져 있는지 확인하세요."
  echo "  사유:  log show --predicate 'process == \"launchd\"' --last 5m --info | grep -i mirrorball"
else
  echo "OK 띄워졌습니다 (last exit code = $code)."
  echo "   0 이 아니면 스크립트 '안에서' 난 실패입니다 → $LOGS/collect.out.log 확인"
fi

cat <<EOS

다음:
  cd $DST                                  (현재 셸은 사라진 경로에 있습니다)
  .venv/bin/python worker/gap_check.py     어디까지 모았는지
  .venv/bin/python worker/sync_log.py      예정된 일요일이 돌았는지
  launchctl list | grep mirrorball         2번째 칸이 0 이어야 정상

로그 위치가 바뀌었습니다: $LOGS/collect.out.log
문제 없으면 옛 .venv 를 지우세요:  rm -rf $DST/.venv.old-*
EOS
