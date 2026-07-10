"""build_app_site — 앱 배포 번들 빌더 계약 테스트.

  · 슬러그별 매니페스트에 start_url=?d={slug} 를 굽는다(설치 시 그 디자이너로 열림).
  · 번들에 앱 셸(index.html·sw.js·icon·manifest) + data/{slug}.json 이 모두 담긴다.
  · data 는 실제 앱 데이터 형태(build_app 산출).
데모 데이터 clients/minji 로 결정적 검증(PII 아님).
"""

import json
from pathlib import Path

import build_app_site as bas


def test_slug_manifest_bakes_slug():
    base = {"name": "살롱 컨시어지", "start_url": "./index.html", "scope": "./", "display": "standalone"}
    m = bas.slug_manifest("hayewoni", base)
    assert m["start_url"] == "./?d=hayewoni"
    assert m["scope"] == "./"
    assert m["name"] == "살롱 컨시어지"                 # 나머지 키 보존
    assert base["start_url"] == "./index.html"        # 원본 불변(복사본만 수정)


def test_build_site_structure(tmp_path):
    site, da = tmp_path / "site", tmp_path / "da"
    r = bas.build_site("clients/minji", str(site), str(da))
    assert r["slug"] == "minji"
    assert r["url"] == "/?d=minji"

    out = Path(r["out"])
    for f in ("index.html", "sw.js", "icon.svg", "manifest.webmanifest"):
        assert (out / f).exists(), f"번들에 {f} 없음"
    assert (out / "data" / "minji.json").exists(), "data/minji.json 없음"

    man = json.loads((out / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert man["start_url"] == "./?d=minji"

    data = json.loads((out / "data" / "minji.json").read_text(encoding="utf-8"))
    assert data["slug"] == "minji" and "clients" in data and "seed" in data
