#!/usr/bin/env python3
"""핸드SOS 자동 동기화 — 매장별 로그인→매출상세목록 수확→import→build.

API 가 없어 '항상 동기화'는 로그인된 헤드리스 브라우저를 스케줄로 돌리는 배치다.
매 실행마다 매장 자격증명으로 새로 로그인(세션 유지 X) → 여러 매장 깔끔히 관리.

흐름(매장당):
  1) Playwright 로 로그인(회사코드+아이디+비번)
  2) 매출상세목록 화면으로 이동(직접 URL 또는 메뉴 클릭, 기간 설정)
  3) handsos_harvest.js 주입 → 행 배열 수확(검증된 콘솔 로직 재사용)
  4) CSV 저장(감사용) → import_handsos(카르테·관계 보존) → build_app
  5) 0행/로그인 실패 가드 + 로그 + (선택)알림

설정: secrets/stores.yaml (gitignore). 템플릿: secrets/stores.example.yaml

사용:
  python scripts/handsos_sync.py                 # 모든 매장
  python scripts/handsos_sync.py --only hayewoni # 한 매장
  python scripts/handsos_sync.py --headed        # 화면 띄워 셀렉터 확인(최초 1회)
  python scripts/handsos_sync.py --no-build      # 수확·CSV 까지만
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HARVEST_JS = Path(__file__).resolve().parent / "handsos_harvest.js"
COLS = ["날짜", "고객명", "전화번호", "고객번호", "이전방문", "상세메뉴", "담당", "결제액", "메모"]


# ───────────────────────── 브라우저 없는 순수 헬퍼(테스트 가능) ─────────────────────────
def load_stores(path: str) -> list[dict]:
    """secrets/stores.yaml → 매장 리스트. enabled=false 는 제외."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    stores = data.get("stores", data) if isinstance(data, dict) else data
    out = [s for s in (stores or []) if s.get("enabled", True)]
    for s in out:
        if not s.get("slug"):
            raise ValueError(f"slug 누락: {s}")
    return out


def write_csv(rows: list[dict], path: Path) -> int:
    """수확 행(한글 키) → import_handsos 가 읽는 CSV(utf-8-sig)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLS})
    return len(rows)


def date_range_value(days: int, today: date | None = None) -> tuple[str, str]:
    """기간 입력용 (시작, 끝) YYYY-MM-DD. days<=0 이면 ('', '')=전체."""
    today = today or date.today()
    if days and days > 0:
        return str(today - timedelta(days=days)), str(today)
    return "", ""


def notify(cfg: dict, text: str) -> None:
    """실패/요약 알림(선택). webhook_url 있으면 POST, 없으면 stderr."""
    url = (cfg or {}).get("notify_url")
    if not url:
        print(text, file=sys.stderr)
        return
    try:
        body = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as exc:  # 알림 실패가 동기화를 막지 않도록
        print(f"[notify 실패] {exc} :: {text}", file=sys.stderr)


# ───────────────────────── Playwright 수확(브라우저) ─────────────────────────
def _fill(page, sel: str, value: str) -> None:
    if sel and value is not None:
        page.fill(sel, str(value))


# 핸드SOS 로그인 셀렉터는 모든 매장 공통 → 코드 기본값. 사용자는 설정에서 건드릴 필요 없음.
DEFAULT_LOGIN = {
    "url": "https://www.handsos.com/login/login.asp?p=pc",
    "fields": {"company_code": "#companyID", "username": "#userID", "password": "#userPWD"},
    "submit": "#sendLogin",
}


def harvest_store(store: dict, headed: bool = False, debug: bool = False) -> dict:
    """한 매장 로그인→매출상세목록→수확. 반환 {rows, total, error}."""
    from playwright.sync_api import sync_playwright  # 지연 import (테스트 시 불필요)

    login = {**DEFAULT_LOGIN, **(store.get("login") or {})}
    fields = {**DEFAULT_LOGIN["fields"], **(login.get("fields") or {})}
    report = store.get("report") or {}
    js = HARVEST_JS.read_text(encoding="utf-8")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headed)
        ctx = browser.new_context()
        page = ctx.new_page()
        # 핸드SOS 공지/확인 팝업(alert·confirm) 자동 수락. 페이지가 먼저 닫아버린 경우의
        # 'No dialog is showing' 레이스는 무시(비치명적) — 드라이버 크래시·노이즈 방지.
        def _accept_dialog(d):
            try:
                d.accept()
            except Exception:
                pass
        page.on("dialog", _accept_dialog)
        page.set_default_timeout(int(store.get("timeout_ms", 30000)))
        try:
            # 1) 로그인
            page.goto(login["url"], wait_until="domcontentloaded")
            _fill(page, fields.get("company_code"), store.get("company_code", ""))
            _fill(page, fields.get("username"), store.get("username", ""))
            _fill(page, fields.get("password"), store.get("password", ""))
            if login.get("submit"):
                page.click(login["submit"])
            if login.get("success_wait"):
                page.wait_for_selector(login["success_wait"])
            else:
                page.wait_for_load_state("networkidle")

            # 2) 매출상세목록(saleList.asp) 직접 이동 → 기간 채우고 → 검색(DBProc) 실행
            if report.get("url"):
                page.goto(report["url"], wait_until="domcontentloaded")
                page.wait_for_timeout(int(report.get("settle_ms", 1200)))
                if debug:
                    print("  saleList 이동 후 URL:", page.url)   # default.asp 로 튕기면 직접접근 차단된 것
                days = int(report.get("date_range_days", 0))
                if days > 0:                                   # 최근 N일로 기간 설정(증분·가벼움)
                    start, end = date_range_value(days)
                    _fill(page, report.get("date_from_sel", "#strDateS"), start)
                    _fill(page, report.get("date_to_sel", "#strDateE"), end)
                if report.get("staff_label"):                 # (선택) 담당자 드롭다운 직접 선택
                    try:
                        page.select_option(report.get("staff_sel", "#pkStaff"),
                                           label=report["staff_label"])
                    except Exception:
                        pass
                # 검색 실행 — 버튼 클릭(네비게이션 추적) 우선, 안 되면 함수 직접 호출
                try:
                    page.click(report.get("search_sel", "a.icogSearch"), timeout=4000)
                except Exception:
                    try:
                        page.evaluate(report.get("search_js", "DBProc()"))
                    except Exception:
                        pass
                # 결과 표(고객명·날짜)가 실제로 그려질 때까지 대기 — POST 리로드/AJAX 모두 대응
                try:
                    page.wait_for_function(
                        "()=>{var t=[...document.querySelectorAll('table')]"
                        ".find(x=>/고객명/.test(x.innerText)&&/날짜/.test(x.innerText));"
                        "return t&&t.querySelectorAll('tr').length>2;}",
                        timeout=int(report.get("result_timeout_ms", 15000)))
                except Exception:
                    pass
                page.wait_for_timeout(int(report.get("settle_ms", 1200)))
            for step in report.get("nav", []) or []:           # (대안) 메뉴 클릭 시퀀스
                if step.get("click"):
                    page.click(step["click"])
                if step.get("wait_ms"):
                    page.wait_for_timeout(int(step["wait_ms"]))

            if debug:
                input("‹디버그› 표가 보이면 Enter… (자동조회됐으면 그대로 Enter)")
                for i, pg in enumerate(ctx.pages):           # 열린 창/탭 전체(팝업 포함) + 프레임 URL
                    print(f"  [page {i}] {pg.url}")
                    for fr in pg.frames:
                        if fr.url and "about:blank" not in fr.url:
                            print(f"     frame: {fr.url}")
                _DIAG = ("()=>{var out=[];[...document.querySelectorAll('table')].forEach((t,i)=>{"
                         "var x=t.innerText||'';out.push(i+': rows='+t.querySelectorAll('tr').length"
                         "+' 고객명='+/고객명/.test(x)+' 날짜='+/날짜/.test(x)+' | '+x.slice(0,45).replace(/\\n/g,' '));});"
                         "var m=document.body.innerText.match(/총\\s*([\\d,]+)\\s*개/);"
                         "return {tables:out, total:(m?m[1]:'?')};}")
                for pg in ctx.pages:                          # 표 진단 — 어느 table 에 고객명/날짜 가 있나
                    try:
                        d = pg.evaluate(_DIAG)
                        print(f"  표 진단(총건수={d['total']}):")
                        for line in d["tables"][:14]:
                            print("    table#" + line)
                    except Exception as e:
                        print("  표 진단 실패:", e)

            # 3) 열린 창/탭을 최신순으로 모두 시도 → 표가 가장 많이 잡힌 곳을 채택(매출상세목록 팝업 대응)
            best = {"rows": [], "total": 0, "error": "no-table"}
            for pg in reversed(ctx.pages):
                try:
                    pg.add_script_tag(content=js)
                    r = pg.evaluate("__handsosHarvest({})")
                except Exception:
                    continue
                if r and len(r.get("rows") or []) > len(best.get("rows") or []):
                    best = r
                if r and r.get("total") and len(r.get("rows") or []) >= r["total"]:
                    return r                                 # 전체 페이지 다 받음 → 확정
            return best
        finally:
            if not debug:
                ctx.close()
                browser.close()


# ───────────────────────── 매장 1곳 전체 파이프라인 ─────────────────────────
def sync_one(store: dict, *, do_build: bool, do_deploy: bool,
             headed: bool, debug: bool, cfg: dict) -> dict:
    slug = store["slug"]
    staff = store.get("staff")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S") if not debug else "debug"
    raw_dir = ROOT / "clients" / slug / "_raw"

    try:
        res = harvest_store(store, headed=headed, debug=debug)
    except Exception as exc:
        return {"slug": slug, "ok": False, "stage": "harvest", "error": str(exc)}

    rows = res.get("rows") or []
    if not rows:
        return {"slug": slug, "ok": False, "stage": "harvest",
                "error": res.get("error") or "0행", "total": res.get("total")}

    csv_path = raw_dir / f"handsos_{stamp}.csv"
    write_csv(rows, csv_path)

    # 4) import → build (모듈 직접 호출, 카르테·관계 보존)
    sys.path.insert(0, str(ROOT))
    import import_handsos as ih
    parsed = ih.parse_rows(str(csv_path), staff=staff)
    nr, nc = ih.write_out(slug, parsed)        # records 누적 병합 + 고객 재구성(수동필드 보존)

    # 최초 동기화면 config.yaml 부트스트랩(디자이너 이름·살롱·기준일). 이후 사람이 보강 가능.
    cfg_path = ROOT / "clients" / slug / "config.yaml"
    if not cfg_path.exists():
        cfg_path.write_text(yaml.safe_dump(
            {"slug": slug, "display_name": staff or slug, "salon": store.get("salon", ""),
             "today": str(date.today())}, allow_unicode=True, sort_keys=False), encoding="utf-8")

    built = None
    if do_build:
        import build_app
        built = build_app.build_one(str(ROOT / "clients" / slug))

    return {"slug": slug, "ok": True, "rows": len(rows), "txns": nr,
            "new_customers": nc, "csv": str(csv_path), "total": res.get("total"),
            "built": built and built.get("out"), "partial": res.get("error")}


def main() -> int:
    ap = argparse.ArgumentParser(description="핸드SOS 자동 동기화")
    ap.add_argument("--stores", default=str(ROOT / "secrets" / "stores.yaml"))
    ap.add_argument("--only", help="이 slug 만")
    ap.add_argument("--headed", action="store_true", help="브라우저 창 표시")
    ap.add_argument("--debug", action="store_true", help="표 확인용 일시정지(셀렉터 점검)")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--deploy", action="store_true")
    args = ap.parse_args()

    if not Path(args.stores).exists():
        print(f"✗ 설정 없음: {args.stores}\n  secrets/stores.example.yaml 복사해서 채우세요.")
        return 2

    cfg = yaml.safe_load(Path(args.stores).read_text(encoding="utf-8")) or {}
    stores = load_stores(args.stores)
    if args.only:
        stores = [s for s in stores if s["slug"] == args.only]
    if not stores:
        print("대상 매장 없음")
        return 1

    results, failed = [], []
    for s in stores:
        print(f"▶ {s['slug']} 동기화…")
        r = sync_one(s, do_build=not args.no_build, do_deploy=args.deploy,
                     headed=args.headed, debug=args.debug, cfg=cfg)
        results.append(r)
        if r["ok"]:
            cov = f" / 핸드SOS 총 {r['total']}" if r.get("total") else ""
            extra = f" (부분수집: {r['partial']})" if r.get("partial") else ""
            print(f"  ✓ 거래 {r['txns']}{cov} · 신규 {r['new_customers']}명{extra}")
        else:
            failed.append(r)
            print(f"  ✗ [{r['stage']}] {r['error']}")

    if failed:
        notify(cfg, "핸드SOS 동기화 실패: " + ", ".join(f"{f['slug']}({f['error']})" for f in failed))
    print(f"\n완료: 성공 {len(results)-len(failed)} / 실패 {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
