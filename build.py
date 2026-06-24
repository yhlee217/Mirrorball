#!/usr/bin/env python3
"""미용사 프로필 정적 사이트 생성기 — CLI 빌드 엔트리.

사용법:
    python build.py designers/hayewoni.yaml   # 한 명
    python build.py --all                      # designers/*.yaml 전부

YAML 로드 → 검증 → core.render → dist/{slug}/index.html.
배포는 dist/ 를 Netlify drop / GitHub Pages 에 수동 업로드.
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

import yaml

import core
import validate

_JSONLD_RE = re.compile(
    r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL
)


def load_yaml(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def check_jsonld(html: str) -> int:
    """렌더된 HTML 의 JSON-LD 블록이 유효한 JSON 인지 파싱 검증. 개수 반환."""
    blocks = _JSONLD_RE.findall(html)
    if not blocks:
        raise ValueError("JSON-LD 스크립트가 없습니다")
    for i, block in enumerate(blocks):
        try:
            json.loads(block)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON-LD[{i}] 파싱 실패: {e}") from e
    return len(blocks)


def build_one(path: str, dist: str = "dist") -> dict:
    """한 명 빌드. {slug, out_path, warnings} 반환. 실패 시 예외."""
    data = load_yaml(path)
    if not data or not data.get("slug"):
        raise ValueError(f"{path}: slug 가 없습니다")

    warnings = validate.validate(data)  # 필수 누락이면 ValueError
    html = core.render(data)
    check_jsonld(html)

    out = Path(dist) / data["slug"] / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    # 상대경로 photo_url(예: assets/x.jpg)이면 designers/ 의 원본을 dist 로 복사.
    warnings = list(warnings)
    photo = (data.get("photo_url") or "").strip()
    if photo and not photo.startswith(("http://", "https://", "data:")):
        src = Path("designers") / photo
        if src.exists():
            dst = out.parent / photo
            dst.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy(src, dst)
        else:
            warnings.append(f"photo_url 파일 없음: {src} (사진을 넣어주세요)")

    # 영어 버전: 'en' 블록이 있으면 dist/{slug}/en/index.html 추가 생성.
    site_url = (data.get("site_url") or "").strip()
    en_url = ""
    if data.get("en"):
        html_en = core.render(data, lang="en")
        check_jsonld(html_en)
        out_en = out.parent / "en" / "index.html"
        out_en.parent.mkdir(parents=True, exist_ok=True)
        out_en.write_text(html_en, encoding="utf-8")
        if site_url:
            en_url = site_url.rstrip("/") + "/en/"

    # 예약·프로필 QR (segno 설치 시). 인쇄·인스타·거울용.
    try:
        import qr as _qr
        _qr.for_designer(path, dist)
    except Exception as exc:
        warnings.append(f"QR 생성 건너뜀: {type(exc).__name__}: {exc}")

    return {
        "slug": data["slug"],
        "out_path": out,
        "warnings": warnings,
        "site_url": site_url,
        "en_url": en_url,
    }


def write_site_files(built: list[dict], dist: str = "dist") -> list[Path]:
    """robots.txt 항상 + site_url 있는 프로필로 sitemap.xml 생성."""
    from urllib.parse import urlparse

    dist_p = Path(dist)
    dist_p.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    urls = [b["site_url"] for b in built if b.get("site_url")]
    urls += [b["en_url"] for b in built if b.get("en_url")]
    if urls:
        body = "\n".join(f"  <url><loc>{u}</loc></url>" for u in urls)
        sitemap = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{body}\n</urlset>\n"
        )
        p = dist_p / "sitemap.xml"
        p.write_text(sitemap, encoding="utf-8")
        written.append(p)

    robots = "User-agent: *\nAllow: /\n"
    if urls:
        o = urlparse(urls[0])
        robots += f"Sitemap: {o.scheme}://{o.netloc}/sitemap.xml\n"
    p = dist_p / "robots.txt"
    p.write_text(robots, encoding="utf-8")
    written.append(p)
    return written


def main() -> None:
    args = sys.argv[1:]
    if not args:
        raise SystemExit("사용법: python build.py designers/{slug}.yaml | --all")

    if args[0] == "--all":
        paths = sorted(glob.glob("designers/*.yaml"))
        if not paths:
            raise SystemExit("designers/*.yaml 이 없습니다")
    else:
        paths = [args[0]]

    built: list[dict] = []
    failed: list[tuple[str, str]] = []
    for p in paths:
        try:
            r = build_one(p)
            built.append(r)
            print(f"✓ {r['slug']:<14} → {r['out_path']}")
            for w in r["warnings"]:
                print(f"    ⚠ {w}")
        except Exception as exc:
            failed.append((p, str(exc)))
            print(f"✗ {p}\n    {exc}")

    site_files = write_site_files(built) if built else []
    for p in site_files:
        print(f"✓ {p}")

    print("\n" + "=" * 52)
    print(f"빌드 성공: {len(built)}  /  실패: {len(failed)}")
    for r in built:
        n = len(r["warnings"])
        print(f"  - {r['slug']}: {r['out_path']}" + (f"  (경고 {n})" if n else ""))
    if failed:
        print("실패 목록:")
        for p, e in failed:
            print(f"  - {p}: {e.splitlines()[0]}")
    print("=" * 52)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
