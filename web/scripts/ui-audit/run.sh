#!/bin/sh
# UI 측정 — 컴파일 → 견본으로 그리기 → 폰 크기로 재기(UX 계획 v3 §6).
# 사용: sh web/scripts/ui-audit/run.sh [--check] [--shots] [--json 파일]
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
WEB=$(cd "$HERE/../.." && pwd)
OUT="$HERE/out"
rm -rf "$OUT/js"
"$WEB/node_modules/.bin/tsc" -p "$HERE/tsconfig.json" --outDir "$OUT/js"
node "$HERE/render.cjs" "$OUT"
python3 "$HERE/measure.py" "$OUT" "$@"
