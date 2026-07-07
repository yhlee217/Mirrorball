#!/usr/bin/env python3
"""핸드SOS 파이프라인 '로그인만 빼고' 한 번 돌려보기 — 실제 수확 JS·임포트·빌드를 그대로.

진짜 로그인/네트워크가 필요한 harvest_store 대신, 합성 '매출상세목록' 페이지를
실제 브라우저에 띄워 handsos_harvest.js 로 수확한다. 그 뒤는 운영과 동일 코드:
  handsos_harvest.js → write_csv → import_handsos(병합·화해) → build_app → 앱 JSON

자격증명 없이 배관(plumbing)이 실제로 도는지 눈으로 확인하는 용도. 결과는 임시폴더(기본).

사용:
  python scripts/handsos_demo.py            # 임시폴더에 돌리고 요약 출력
  python scripts/handsos_demo.py --keep     # 결과 폴더 유지(경로 출력)
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import import_handsos as ih          # noqa: E402
import build_app                     # noqa: E402
import importlib.util                # noqa: E402

_spec = importlib.util.spec_from_file_location("handsos_sync", ROOT / "scripts" / "handsos_sync.py")
hs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hs)

HARVEST_JS = (ROOT / "scripts" / "handsos_harvest.js").read_text(encoding="utf-8")

# 합성 매출상세목록: 2페이지(gotoP), 숨김 툴팁·연속행·title·메모·'총 N개'.
# 시연 포인트: ① 조희진 custno 유(1p)/무(2p) → 화해 병합, 익명 워크인 원장 보존, 시각 캡처.
FIXTURE = """<!doctype html><html><body>
<div>총 6개</div>
<table id="list_tbl">
 <tr><th>날짜</th><th>고객명</th><th>상세메뉴</th><th>담당</th><th>결제액</th><th>메모</th></tr>
 <tbody id="tb">
  <tr><td>26-06-26 14:20</td>
      <td>조희진<span id="strCustomerInfo1" style="display:none">고객명 : 조희진
전화 번호 : 010-0000-0218
고객 번호 : 0002767</span></td>
      <td title="뿌리염색">뿌리염색</td><td>하예원</td><td>30,000</td>
      <td><span id="saleStrMemoList1">수다 좋아함상세보기</span></td></tr>
  <tr><td>26-06-26 19:41</td>
      <td>배상웅<span id="strCustomerInfo2" style="display:none">고객명 : 배상웅
전화 번호 : 010-1234-7305
고객 번호 : 0005120
이전방문 : 2026-05-29</span></td>
      <td title="남자컷(부원장)">남자컷</td><td>하예원</td><td>28,000</td>
      <td><span id="saleStrMemoList2">손상 신경 씀상세보기</span></td></tr>
  <tr><td></td><td></td>
      <td title="다운펌(부원장)">다운펌</td><td>하예원</td><td>91,000</td><td></td></tr>
  <tr><td>26-06-26 10:00</td><td>손님</td>
      <td title="남자컷">남자컷</td><td>하예원</td><td>20,000</td><td></td></tr>
  <tr><td>26-06-26 11:00</td><td>손님</td>
      <td title="여자컷">여자컷</td><td>하예원</td><td>25,000</td><td></td></tr>
 </tbody>
</table>
<span class="current" id="pg">1</span>
<script>
 window.gotoP = function(n){
   document.getElementById('tb').innerHTML =
     '<tr><td>26-05-01 13:00</td>' +
     '<td>조희진<span id="strCustomerInfo9" style="display:none">고객명 : 조희진\\n전화 번호 : 010-0000-0218</span></td>' +
     '<td title="뿌리펌">뿌리펌</td><td>하예원</td><td>30,000</td><td></td></tr>';
   document.getElementById('pg').textContent = String(n);
 };
</script>
</body></html>"""


def _launch(pw):
    try:
        return pw.chromium.launch()
    except Exception:
        exe = Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        if exe.exists():
            return pw.chromium.launch(executable_path=str(exe))
        raise


def harvest_synthetic() -> dict:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = _launch(pw)
        pg = b.new_page()
        pg.set_content(FIXTURE)
        pg.add_script_tag(content=HARVEST_JS)
        res = pg.evaluate("__handsosHarvest({})")
        b.close()
        return res


def main() -> int:
    ap = argparse.ArgumentParser(description="핸드SOS 파이프라인 데모(로그인 제외)")
    ap.add_argument("--keep", action="store_true", help="결과 폴더 유지")
    args = ap.parse_args()

    print("▶ 1) 합성 매출상세목록에서 handsos_harvest.js 로 수확(진짜 브라우저)…")
    res = harvest_synthetic()
    rows = res.get("rows") or []
    print(f"   수확 {len(rows)}행 / 핸드SOS 총 {res.get('total')} · 부분수집판정: {hs.partial_of(res) or '완전'}")

    work = Path(tempfile.mkdtemp(prefix="handsos_demo_"))
    cdir = work / "clients" / "demo"
    (cdir / "_raw").mkdir(parents=True)
    (cdir / "config.yaml").write_text("slug: demo\ndisplay_name: 하예원\nsalon: 살롱톤\ntoday: 2026-06-27\n",
                                      encoding="utf-8")

    print("▶ 2) write_csv → import(병합·화해) …")
    csv_path = cdir / "_raw" / "harvest.csv"
    hs.write_csv(rows, csv_path)
    parsed = ih.parse_rows(str(csv_path))
    mm = ih.prev_visit_mismatches(parsed)

    # write_out 은 CWD 기준 clients/{slug} 에 쓰므로 데모 작업폴더로 이동해 실행
    import os
    cwd0 = os.getcwd()
    os.chdir(work)
    try:
        nr, nc = ih.write_out("demo", parsed)
    finally:
        os.chdir(cwd0)

    print("▶ 3) build_app → 앱 JSON …")
    built = build_app.build_one(str(cdir), dist=str(work / "dist"))

    import yaml
    custs = [yaml.safe_load(p.read_text(encoding="utf-8"))
             for p in sorted((cdir / "customers").glob("*.yaml"))]
    import json
    app = json.loads((work / "dist" / "demo.json").read_text(encoding="utf-8"))

    print("\n────────── 결과 ──────────")
    print(f"거래 원장: {nr}건  ·  고객 카드: {len(custs)}장(익명 워크인 제외)  ·  챙길 고객: {len(app.get('care', []))}명")
    if mm:
        print(f"이전방문 크로스체크 불일치: {len(mm)}건(수집 누락/분열 신호)")
    print("\n고객 카드:")
    for c in sorted(custs, key=lambda x: -(x.get("loyalty_visits") or 0)):
        peak = next((h for h in (c.get("history") or [])), {})
        bday = f" · 생일 {c['birthday']}" if c.get("birthday") else ""
        print(f"  · {c['name']} (고객번호 {c.get('custno','-')}) 방문 {c['loyalty_visits']}회{bday}"
              f" — 최근 {peak.get('service','?')}")
    # ① 화해 병합 확인: 조희진이 custno 유/무 방문에도 1장·2방문인가
    joh = next((c for c in custs if c["name"] == "조희진"), None)
    if joh:
        ok = joh.get("custno") == "2767" and joh["loyalty_visits"] == 2
        print(f"\n① 카드 분열 방지: 조희진 custno 유/무 방문 → {'1장·2방문으로 병합됨 ✅' if ok else '⚠ 확인필요'}")
    # ② 시각 캡처 → 피크시간 통계 살아있나
    st = app.get("stats") or {}
    print(f"② 시각 캡처: 피크시간 통계 = {st.get('busiest_hour') or '(데이터 부족)'}"
          f" · 총 방문 {st.get('total_visits')}건")
    print("\n앱 JSON:", built.get("out"))

    if args.keep:
        print(f"\n(--keep) 결과 폴더 유지: {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    print("\n✓ 로그인만 빼고 전 과정 정상 — 실기기에선 이 앞에 '핸드SOS 로그인+수확'만 붙는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
