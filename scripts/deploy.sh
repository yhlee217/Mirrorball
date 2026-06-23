#!/usr/bin/env bash
# 손님용 프로필 빌드 + Cloudflare Pages 배포 (로컬 수동 배포용).
# 사전: npm i -g wrangler && wrangler login  (또는 CLOUDFLARE_API_TOKEN/ACCOUNT_ID 환경변수)
set -euo pipefail

cd "$(dirname "$0")/.."

echo "▶ 프로필 빌드…"
python build.py --all

if [ ! -d dist ]; then
  echo "✗ dist/ 생성 실패"; exit 1
fi

if command -v wrangler >/dev/null 2>&1; then
  echo "▶ Cloudflare Pages 배포…"
  wrangler pages deploy dist --project-name=mirrorball-profiles
else
  echo "ℹ wrangler 미설치 → 빌드만 완료. dist/ 를 수동 업로드하세요."
  echo "  설치: npm i -g wrangler"
fi
