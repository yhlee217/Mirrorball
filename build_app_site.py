#!/usr/bin/env python3
"""디자이너 앱 배포 번들 빌더 — app/ 셸 + build_app 데이터 → dist_app_site/{slug}/.

앱(app/index.html)은 ?d={slug} 로 ./data/{slug}.json 을 불러온다. 이 스크립트는 앱 셸과
빌드된 데이터를 한 폴더로 묶어 정적 호스팅(무료 Cloudflare Pages / Netlify Drop)에 그대로
올릴 수 있게 한다. 매니페스트 start_url 을 ?d={slug} 로 구워, PWA 설치 시 그 디자이너
데이터로 열리게 한다.

사용법:
    python build_app_site.py clients/minji        # → dist_app_site/minji/
    python build_app_site.py --all                 # clients/*/ 전부(각자 폴더)

배포(무료):
    · Netlify Drop    : dist_app_site/{slug} 폴더를 app.netlify.com/drop 에 드래그(계정 없이 즉시)
    · Cloudflare Pages: wrangler pages deploy dist_app_site/{slug}
앱 URL: https://<host>/?d={slug}   (설치하면 그 슬러그로 열림)

주의(PII): 배포물엔 이름·생일이 포함됨(전화는 build_app 이 제외). 실데이터는 게이트(비공개 접근)
뒤에만. 데모(minji)는 PII 아님 → 무료로 바로 올려 확인해도 됨.
"""

from __future__ import annotations

import argparse
import glob
import json
import shutil
from pathlib import Path

import build_app

ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
SHELL = ("index.html", "sw.js", "icon.svg")   # 매니페스트는 슬러그별로 새로 씀


def slug_manifest(slug: str, base: dict) -> dict:
    """앱 매니페스트에 슬러그를 구움 — 설치 시 ?d={slug} 로 열리게."""
    m = dict(base)
    m["start_url"] = f"./?d={slug}"
    m["scope"] = "./"
    return m


def build_site(client_dir: str, out_root: str = "dist_app_site", dist_app: str = "dist_app") -> dict:
    """한 디자이너의 배포 번들 생성 → out_root/{slug}/ (index.html·sw.js·icon·manifest·data/{slug}.json)."""
    info = build_app.build_one(client_dir, dist=dist_app)     # dist_app/{slug}.json 생성
    slug = info["slug"]
    src_json = Path(dist_app) / f"{slug}.json"
    out = Path(out_root) / slug
    (out / "data").mkdir(parents=True, exist_ok=True)
    for f in SHELL:
        shutil.copyfile(APP / f, out / f)
    base = json.loads((APP / "manifest.webmanifest").read_text(encoding="utf-8"))
    (out / "manifest.webmanifest").write_text(
        json.dumps(slug_manifest(slug, base), ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copyfile(src_json, out / "data" / f"{slug}.json")
    return {"slug": slug, "out": str(out), "url": f"/?d={slug}",
            "clients": info["clients"], "care": info["care"]}


def main() -> int:
    ap = argparse.ArgumentParser(description="앱 배포 번들 빌더(정적 호스팅용)")
    ap.add_argument("client_dir", nargs="?", help="clients/{slug}")
    ap.add_argument("--all", action="store_true", help="clients/*/ 전부")
    ap.add_argument("--out", default="dist_app_site")
    args = ap.parse_args()

    if args.all:
        dirs = sorted(d for d in glob.glob("clients/*") if Path(d).is_dir())
    else:
        dirs = [args.client_dir] if args.client_dir else []
    if not dirs:
        print("사용법: python build_app_site.py clients/{slug} | --all")
        return 2

    rc = 0
    for d in dirs:
        try:
            r = build_site(d, args.out)
            print(f"✓ {r['slug']:<12} → {r['out']}/  (고객 {r['clients']} · 챙길 {r['care']})  URL {r['url']}")
        except Exception as exc:
            print(f"✗ {d}: {exc}")
            rc = 1
    if rc == 0:
        print("배포(무료): Netlify Drop 에 dist_app_site/{slug} 폴더 드래그, 또는 wrangler pages deploy dist_app_site/{slug}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
