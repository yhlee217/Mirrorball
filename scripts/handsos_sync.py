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


# ── 셀렉터 오버라이드: AI(자가치유)/사람이 secrets/{slug}.selectors.yaml 만 고치면 코드 수정 없이 반영 ──
def load_overrides(slug: str) -> dict:
    p = ROOT / "secrets" / f"{slug}.selectors.yaml"
    if p.exists():
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


def merge_selector_overrides(store: dict, ov: dict) -> dict:
    """셀렉터 오버라이드(login/report)를 store 에 병합 — 파일/자가치유 공용."""
    if ov.get("login"):
        login = {**store.get("login", {}), **{k: v for k, v in ov["login"].items() if k != "fields"}}
        if ov["login"].get("fields"):
            login["fields"] = {**(store.get("login", {}).get("fields") or {}), **ov["login"]["fields"]}
        store["login"] = login
    if ov.get("report"):
        store["report"] = {**store.get("report", {}), **ov["report"]}
    return store


def apply_overrides(store: dict) -> dict:
    return merge_selector_overrides(store, load_overrides(store.get("slug", "")))


def partial_of(res: dict) -> str | None:
    """부분수집 판정 — 페이지네이션 에러(멈춤·구조미상)일 때만.

    핸드SOS '총 N개'는 '건수(시술 라인)'라 목록 '행수'와 다르다(건수 727 vs 목록행 342 등).
    그래서 총계-행수 대조는 오판이므로 안 한다. 마지막 페이지까지 정상 도달(error 없음)이면 완전 수집."""
    err = res.get("error")
    return str(err) if err else None


# ── 상태/하트비트: 매 실행 기록 → 오래 미성공이면 점검 알림(조용한 고장 방지) ──
def write_status(slug: str, result: dict) -> dict:
    p = ROOT / "clients" / slug / "_status.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    prev = {}
    if p.exists():
        try:
            prev = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
    now = datetime.now().isoformat(timespec="seconds")
    st = {"slug": slug, "last_run": now, "ok": bool(result.get("ok")),
          "rows": result.get("rows"), "txns": result.get("txns"), "total": result.get("total"),
          "error": result.get("error"), "partial": result.get("partial"),
          "fail_dir": result.get("fail_dir"),
          "last_success": now if result.get("ok") else prev.get("last_success")}
    p.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    return st


def healthcheck(cfg: dict, max_hours: int = 48) -> int:
    """모든 매장의 _status.json 점검 → 오래 미성공이면 알림. cron 으로 따로 돌려도 됨."""
    stale = []
    for p in (ROOT / "clients").glob("*/_status.json"):
        try:
            st = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        ls = st.get("last_success")
        if not ls:
            stale.append(f"{st.get('slug')}(성공 기록 없음)")
            continue
        try:
            age = (datetime.now() - datetime.fromisoformat(ls)).total_seconds() / 3600
        except Exception:
            continue
        if age > max_hours:
            stale.append(f"{st.get('slug')}({int(age)}시간째 미성공)")
    if stale:
        notify(cfg, "핸드SOS 동기화 점검 필요: " + ", ".join(stale))
        return 1
    print("점검: 모든 매장 정상")
    return 0


# ───────────────────────── Playwright 수확(브라우저) ─────────────────────────
def _capture_failure(ctx, slug: str, err) -> str:
    """실패 시 화면+DOM 저장 — AI(handsos_heal)나 사람이 바로 진단·수리하게."""
    d = ROOT / "clients" / slug / "_raw" / ("fail_" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    d.mkdir(parents=True, exist_ok=True)
    try:
        for i, pg in enumerate(ctx.pages):
            try:
                pg.screenshot(path=str(d / f"page{i}.png"))
            except Exception:
                pass
            chunks = []
            for fr in pg.frames:
                try:
                    chunks.append(f"<!-- frame: {fr.url} -->\n" + fr.content())
                except Exception:
                    pass
            try:
                (d / f"page{i}.html").write_text("\n\n".join(chunks), encoding="utf-8")
            except Exception:
                pass
    except Exception:
        pass
    (d / "error.txt").write_text(str(err), encoding="utf-8")
    return str(d)


def _fill(page, sel: str, value: str) -> None:
    if sel and value is not None:
        page.fill(sel, str(value))


# 셀렉터 단일 진실: scripts/handsos_selectors.yaml (sync·heal 공용). 여기 상수는 파일 유실 시 폴백.
SELECTORS_PATH = Path(__file__).resolve().parent / "handsos_selectors.yaml"


def load_selectors() -> dict:
    try:
        return yaml.safe_load(SELECTORS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


_SEL = load_selectors()
DEFAULT_LOGIN = _SEL.get("login") or {
    "url": "https://www.handsos.com/login/login.asp?p=pc",
    "fields": {"company_code": "#companyID", "username": "#userID", "password": "#userPWD"},
    "submit": "#sendLogin",
}
DEFAULT_REPORT = _SEL.get("report") or {}


def harvest_store(store: dict, headed: bool = False, debug: bool = False) -> dict:
    """한 매장 로그인→매출상세목록→수확. 반환 {rows, total, error}."""
    from playwright.sync_api import sync_playwright  # 지연 import (테스트 시 불필요)

    login = {**DEFAULT_LOGIN, **(store.get("login") or {})}
    fields = {**DEFAULT_LOGIN["fields"], **(login.get("fields") or {})}
    report = {**DEFAULT_REPORT, **(store.get("report") or {})}
    js = HARVEST_JS.read_text(encoding="utf-8")

    with sync_playwright() as pw:
        # 헤드리스 탐지 회피 — 기본 UA('HeadlessChrome')를 일반 크롬으로 위장 + 자동화 플래그 숨김
        browser = pw.chromium.launch(headless=not headed,
                                     args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            user_agent=store.get("user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 900})
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
            # 로그인 성공 단언 — 비번 필드가 여전히 보이면 자격증명 오류.
            # (없으면 비번 오류도 '0행 실패'로 보여 원인 구분이 안 됨)
            try:
                login_failed = page.is_visible(fields.get("password") or "#userPWD")
            except Exception:
                login_failed = False
            if login_failed:
                return {"rows": [], "total": 0, "error": "login-failed",
                        "fail_dir": _capture_failure(ctx, store["slug"], "login-failed: 비밀번호/아이디 확인")}

            # 2) 매출상세목록을 mainFrame(자식 프레임) 안에 로드 = 메뉴 클릭과 동일 구조.
            #    top-level 로 직접 열면 페이지넘김(gotoP)이 페이지 전체를 리로드해 수확이 끊김 →
            #    프레임 안에 두면 페이지넘김 때 프레임만 리로드되고 top(수확)은 유지된다.
            if report.get("url"):
                home = report.get("home_url", "https://www1.handsos.com/work/default.asp")
                page.goto(home, wait_until="domcontentloaded")
                page.wait_for_timeout(int(report.get("settle_ms", 1500)))
                fname = report.get("frame_name", "mainFrame")
                page.evaluate(
                    "a=>{var f=document.querySelector('frame[name=\"'+a.n+'\"],iframe[name=\"'+a.n+'\"],#'+a.n);"
                    "if(f){f.src=a.u;}}", {"n": fname, "u": report["url"]})
                fr = None                                      # saleList 가 뜬 프레임 잡기
                for _ in range(24):
                    page.wait_for_timeout(500)
                    fr = next((f for f in page.frames if "saleList" in (f.url or "")), None)
                    if fr:
                        break
                if debug:
                    print("  saleList 프레임:", fr.url if fr else "(못 찾음)")
                if fr:
                    days = int(report.get("date_range_days", 0))
                    if days > 0:                               # 최근 N일로 기간 설정
                        start, end = date_range_value(days)
                        for sel, val in ((report.get("date_from_sel", "#strDateS"), start),
                                         (report.get("date_to_sel", "#strDateE"), end)):
                            try:
                                fr.fill(sel, val)
                            except Exception:
                                pass
                    if report.get("staff_label"):
                        try:
                            fr.select_option(report.get("staff_sel", "#pkStaff"), label=report["staff_label"])
                        except Exception:
                            pass
                    try:                                       # 검색 실행(프레임 컨텍스트에서)
                        fr.click(report.get("search_sel", "a.icogSearch"), timeout=4000)
                    except Exception:
                        try:
                            fr.evaluate(report.get("search_js", "DBProc()"))
                        except Exception:
                            pass
                    try:                                       # 결과 표(#list_tbl) 그려질 때까지
                        fr.wait_for_function(
                            "()=>{var t=document.querySelector('#list_tbl')||"
                            "[...document.querySelectorAll('table')].find(x=>/고객명/.test(x.innerText)&&/날짜/.test(x.innerText));"
                            "return t&&t.querySelectorAll('tr').length>2;}",
                            timeout=int(report.get("result_timeout_ms", 15000)))
                    except Exception:
                        pass
                page.wait_for_timeout(int(report.get("settle_ms", 1200)))

            if debug:
                # Enter 대기 대신: 표가 실제로 채워질 때까지 폴링(이미 됐으면 즉시) — 고정 대기보다 빠르고 안전.
                # 화면 이동 직후 렌더가 덜 됐어도, 준비되는 순간 진행. 최대 wait_s초까지만 기다린다.
                wait_s = int(store.get("debug_wait_s", report.get("debug_wait_s", 10)))
                print(f"‹디버그› 표 준비되면 자동 수집(최대 {wait_s}초 대기, Enter 불필요)…")
                _READY = ("()=>{var t=document.querySelector('#list_tbl')||"
                          "[...document.querySelectorAll('table')].find(x=>/고객명/.test(x.innerText)&&/날짜/.test(x.innerText));"
                          "return !!(t&&t.querySelectorAll('tr').length>2);}")
                for _ in range(max(1, wait_s * 2)):
                    ready = False
                    for fr in page.frames:
                        try:
                            if fr.evaluate(_READY):
                                ready = True
                                break
                        except Exception:
                            pass
                    if ready:
                        break
                    page.wait_for_timeout(500)
                print("‹디버그› 표 " + ("확인 — 수집 시작" if ready else "미확인 — 그래도 수집 시도"))
                for i, pg in enumerate(ctx.pages):           # 열린 창/탭 전체(팝업 포함) + 프레임 URL
                    print(f"  [page {i}] {pg.url}")
                    for fr in pg.frames:
                        if fr.url and "about:blank" not in fr.url:
                            print(f"     frame: {fr.url}")
                _DIAG = ("()=>{var out=[];[...document.querySelectorAll('table')].forEach((t,i)=>{"
                         "var x=t.innerText||'';"
                         "if(/고객명|날짜|01[016]\\d/.test(x)){"
                         "out.push(i+': rows='+t.querySelectorAll('tr').length+' 고객명='+/고객명/.test(x)"
                         "+' 날짜='+/날짜/.test(x)+' 폰='+/01[016]\\d/.test(x)+' id='+(t.id||t.className||'-')"
                         "+' | '+x.slice(0,55).replace(/\\s+/g,' '));}});"
                         "var tv=document.querySelector('#TableView1');"
                         "var m=document.body.innerText.match(/총\\s*([\\d,]+)\\s*개/);"
                         "return {tables:out, total:(m?m[1]:'?'),"
                         "tv1:tv?(tv.innerText||'').slice(0,90).replace(/\\s+/g,' '):'(#TableView1 없음)'};}")
                for pg in ctx.pages:                          # 데이터 후보 표만(고객명·날짜·전화) + TableView1
                    try:
                        d = pg.evaluate(_DIAG)
                        print(f"  표 진단(총건수={d['total']}): 데이터후보 {len(d['tables'])}개")
                        for line in d["tables"][:20]:
                            print("    table#" + line)
                        print("    #TableView1:", d["tv1"])
                    except Exception as e:
                        print("  표 진단 실패:", e)

            # 3) 열린 창/탭을 최신순으로 모두 시도 → 표가 가장 많이 잡힌 곳을 채택(매출상세목록 팝업 대응)
            best = {"rows": [], "total": 0, "error": "no-table"}
            for pg in reversed(ctx.pages):
                try:
                    pg.add_script_tag(content=js)
                    r = pg.evaluate("__handsosHarvest({})")
                except Exception as exc:
                    if debug:
                        print("  harvest 예외:", str(exc).splitlines()[0][:160])
                    continue
                if r and len(r.get("rows") or []) > len(best.get("rows") or []):
                    best = r
                if r and r.get("total") and len(r.get("rows") or []) >= r["total"]:
                    return r                                 # 전체 페이지 다 받음 → 확정
            if not (best.get("rows")):                       # 실패면 화면·DOM 저장(자가치유용)
                best["fail_dir"] = _capture_failure(ctx, store["slug"], best.get("error"))
            elif best.get("error"):                          # 부분수집(멈춤)이면 프레임 DOM 백업 저장(페이저 정밀진단)
                best["fail_dir"] = _capture_failure(ctx, store["slug"], "partial:" + str(best.get("error")))
            return best
        except Exception as exc:                             # 예외에도 DOM 캡처(치유 입력 확보)
            fail_dir = None
            try:
                fail_dir = _capture_failure(ctx, store["slug"], f"exception: {exc}")
            except Exception:
                pass
            return {"rows": [], "total": 0,
                    "error": "exception: " + str(exc).splitlines()[0][:160],
                    "fail_dir": fail_dir}
        finally:
            if not debug:
                ctx.close()
                browser.close()


def _load_heal():
    """handsos_heal 모듈 로드(같은 scripts/ 폴더)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "handsos_heal", Path(__file__).resolve().parent / "handsos_heal.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def auto_heal(store: dict, res: dict, *, headed: bool, cfg: dict) -> dict | None:
    """실패 직후 자가치유 자동 루프: 진단(Claude) → 제안 셀렉터로 **검증 재수확** →
    행이 실제로 나올 때만 영구 적용(secrets/{slug}.selectors.yaml) + 알림.

    사람 개입 4단계(실패 확인→heal→--apply→재실행)를 1루프로. 검증 실패 제안은 버린다."""
    import copy
    slug = store["slug"]
    try:
        heal = _load_heal()
        fail_dir = Path(res.get("fail_dir") or "")
        html = heal.pick_relevant_html(fail_dir) if fail_dir.exists() else ""
        if not html:
            return None
        out = heal.run_claude(heal.build_prompt(slug, html, str(res.get("error"))))
        sel = heal.parse_selectors(out or "")
        if not sel:
            return None
        trial = merge_selector_overrides(copy.deepcopy(store), sel)
        print("  ↻ 자가치유 제안 수신 — 검증 재수확 중…")
        res2 = harvest_store(trial, headed=headed)
        if not (res2.get("rows")):
            print("  ✗ 치유 제안 검증 실패(여전히 0행) — 적용 안 함")
            return None
        outp = ROOT / "secrets" / f"{slug}.selectors.yaml"       # 검증 통과 → 영구 적용
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(yaml.safe_dump(sel, allow_unicode=True, sort_keys=False), encoding="utf-8")
        merge_selector_overrides(store, sel)
        notify(cfg, f"핸드SOS 자가치유 성공: {slug} — 셀렉터 자동 갱신, {len(res2['rows'])}행 수확")
        print(f"  ✓ 자가치유 성공 — 셀렉터 갱신: {outp}")
        return res2
    except Exception as exc:                                     # 치유 실패가 동기화를 더 망치지 않게
        print(f"  [자가치유 오류] {exc}")
        return None


# ───────────────────────── 매장 1곳 전체 파이프라인 ─────────────────────────
def sync_one(store: dict, *, do_build: bool, do_deploy: bool,
             headed: bool, debug: bool, cfg: dict) -> dict:
    slug = store["slug"]
    staff = store.get("staff")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S") if not debug else "debug"
    raw_dir = ROOT / "clients" / slug / "_raw"

    apply_overrides(store)                      # AI/사람이 고친 셀렉터 오버라이드 반영
    try:
        res = harvest_store(store, headed=headed, debug=debug)
    except Exception as exc:
        return {"slug": slug, "ok": False, "stage": "harvest", "error": str(exc)}

    rows = res.get("rows") or []
    if not rows and res.get("fail_dir") and not debug \
            and (store.get("auto_heal", cfg.get("auto_heal", True))):
        healed = auto_heal(store, res, headed=headed, cfg=cfg)   # 실패 → 자동 치유 루프
        if healed:
            res, rows = healed, healed.get("rows") or []
    if not rows:
        return {"slug": slug, "ok": False, "stage": "harvest",
                "error": res.get("error") or "0행", "total": res.get("total"),
                "fail_dir": res.get("fail_dir")}

    csv_path = raw_dir / f"handsos_{stamp}.csv"
    write_csv(rows, csv_path)

    # 4) import → build. 매장 전체 수확 → 담당(디자이너)별로 분리해 각자 client 로.
    sys.path.insert(0, str(ROOT))
    import import_handsos as ih
    all_parsed = ih.parse_rows(str(csv_path))          # 필터 없이 전체(담당별 집계용)
    breakdown = ih.staff_breakdown(all_parsed)
    print("  · 담당별 수집: " + ", ".join(f"{k} {v}건" for k, v in breakdown[:10]))

    # 대상 결정:
    #  · all_designers: 데이터의 '모든 담당'을 자동 분리(담당명 안 적어도 전원 추출)
    #  · designers: 명시한 담당만(+slug 지정)
    #  · 둘 다 없으면: 단일(staff+slug, 기존 호환)
    designers = store.get("designers") or []
    mapping = {d["staff"]: d["slug"] for d in designers if d.get("staff") and d.get("slug")}
    if store.get("staff") and store.get("slug"):      # 이 store 자체 담당→slug 도 매핑에 포함
        mapping.setdefault(store["staff"], store["slug"])   # (하예원→hayewoni 연속성 자동 유지)
    if store.get("all_designers"):
        targets = []
        for st_name, _cnt in breakdown:
            if st_name == "(담당 미지정)":            # 담당 없는 워크인 등은 개별 client 안 만듦
                continue
            sl = mapping.get(st_name) or _slug_for(st_name)
            if sl:
                targets.append({"slug": sl, "staff": st_name})
    elif designers:
        targets = designers
    else:
        targets = [{"slug": slug, "staff": staff}]
    dresults = []
    for d in targets:
        dresults.append(_import_build_one(
            csv_path, d["slug"], d.get("staff"), store.get("salon", ""), do_build=do_build))

    partial = partial_of(res)
    if partial and res.get("pager"):        # 멈춤 시 페이저 DOM 저장 → 정밀 진단
        pf = raw_dir / f"pager_{stamp}.txt"
        pf.write_text(f"error={res.get('error')} stoppedAt={res.get('stoppedAt')} "
                      f"how={res.get('how')}\n\n{res['pager']}", encoding="utf-8")
        print(f"  ↳ 멈춘 지점 페이저 DOM 저장: {pf}")

    if not debug:                           # 오래된 수확 CSV·덤프 정리(무한 누적 방지)
        n_pruned = prune_raw(raw_dir, keep=int(store.get("keep_raw", 5)))
        if n_pruned:
            print(f"  · _raw 정리: 오래된 파일 {n_pruned}개 삭제(최근 {store.get('keep_raw', 5)}개 유지)")

    return {"slug": slug, "ok": True, "rows": len(rows), "total": res.get("total"),
            "txns": sum(d["txns"] for d in dresults),
            "new_customers": sum(d["new"] for d in dresults),
            "designers": dresults, "csv": str(csv_path),
            "partial": partial, "pager": res.get("pager"), "stopped_at": res.get("stoppedAt")}


import re as _re
_ROLE_RE = _re.compile(r"\s*(부원장|원장|실장|디자이너|점장|대표|팀장|수석|인턴|매니저|메니저)\s*")


def _slug_for(staff: str) -> str | None:
    """담당명 → 파일/URL 안전 slug(명시 매핑 없을 때). 직함 제거 후 한글/영숫자만.

    한글 slug 도 파일·URL 에서 동작(윈도우 파일명·URL 인코딩 OK). 예: '하예원 부원장'→'하예원'."""
    s = _ROLE_RE.sub("", staff or "").strip()
    s = _re.sub(r"[^\w가-힣]", "", s)
    return s or None


def prune_raw(raw_dir: Path, keep: int = 5) -> int:
    """오래된 수확물을 최근 keep 개만 남기고 정리(_raw 무한 누적 방지).

    타입별(수확 CSV·페이저 덤프·실패 폴더)로 각각 최근 keep 개 유지. 이름 다른 옛
    CSV(*.csv 전반)도 대상 — 단 최근 keep 개는 항상 보존(감사용)."""
    import shutil
    removed = 0

    def _prune_files(paths):
        nonlocal removed
        for p in sorted(paths, key=lambda x: x.name, reverse=True)[keep:]:
            try:
                p.unlink()
                removed += 1
            except Exception:
                pass

    _prune_files(list(raw_dir.glob("*.csv")))          # 모든 수확 CSV(옛 이름 포함)
    _prune_files(list(raw_dir.glob("pager_*.txt")))
    for d in sorted([x for x in raw_dir.glob("fail_*") if x.is_dir()],
                    key=lambda x: x.name, reverse=True)[keep:]:
        shutil.rmtree(d, ignore_errors=True)
        removed += 1
    return removed


def _import_build_one(csv_path, slug: str, staff, salon: str, *, do_build: bool) -> dict:
    """CSV → (담당 필터) → 한 디자이너의 client 로 import+build. 담당별 분리의 최소 단위."""
    import import_handsos as ih
    parsed = ih.parse_rows(str(csv_path), staff=staff)
    if not parsed:
        print(f"    · [{slug}] '{staff}' 담당 행 없음 — 건너뜀")
        return {"slug": slug, "staff": staff, "txns": 0, "new": 0}
    mm = ih.prev_visit_mismatches(parsed)             # 범위 내 구멍만
    nr, nc = ih.write_out(slug, parsed, base_dir=ROOT / "clients")   # 실행 폴더 무관, 항상 루트 기준

    cfg_path = ROOT / "clients" / slug / "config.yaml"   # 최초 1회 config 부트스트랩
    if not cfg_path.exists():
        cfg_path.write_text(yaml.safe_dump(
            {"slug": slug, "display_name": staff or slug, "salon": salon,
             "today": str(date.today())}, allow_unicode=True, sort_keys=False), encoding="utf-8")

    built = None
    if do_build:
        import build_app
        built = build_app.build_one(str(ROOT / "clients" / slug))
    tag = f" · 방문누락의심 {len(mm)}" if mm else ""
    print(f"    · [{slug}] {staff or '전체'}: 거래 {nr} · 신규 {nc}명{tag}")
    return {"slug": slug, "staff": staff, "txns": nr, "new": nc,
            "mismatches": len(mm), "built": built and built.get("out")}


def main() -> int:
    ap = argparse.ArgumentParser(description="핸드SOS 자동 동기화")
    ap.add_argument("--stores", default=str(ROOT / "secrets" / "stores.yaml"))
    ap.add_argument("--only", help="이 slug 만")
    ap.add_argument("--headed", action="store_true", help="브라우저 창 표시")
    ap.add_argument("--debug", action="store_true", help="표 확인용 일시정지(셀렉터 점검)")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--deploy", action="store_true")
    ap.add_argument("--all-designers", action="store_true",
                    help="stores.yaml 편집 없이 매장 전체를 담당별로 분리 저장(하예원=hayewoni 유지)")
    ap.add_argument("--healthcheck", action="store_true",
                    help="동기화 안 하고, 오래 미성공인 매장만 점검·알림")
    args = ap.parse_args()

    if not Path(args.stores).exists():
        print(f"✗ 설정 없음: {args.stores}\n  secrets/stores.example.yaml 복사해서 채우세요.")
        return 2

    cfg = yaml.safe_load(Path(args.stores).read_text(encoding="utf-8")) or {}
    if args.healthcheck:
        return healthcheck(cfg)
    stores = load_stores(args.stores)
    if args.only:
        stores = [s for s in stores if s["slug"] == args.only]
    if not stores:
        print("대상 매장 없음")
        return 1
    if args.all_designers:                     # 편집 없이 전원 추출(런타임 토글)
        for s in stores:
            s["all_designers"] = True

    results, failed = [], []
    for s in stores:
        print(f"▶ {s['slug']} 동기화…")
        r = sync_one(s, do_build=not args.no_build, do_deploy=args.deploy,
                     headed=args.headed, debug=args.debug, cfg=cfg)
        results.append(r)
        if not args.debug:
            write_status(s["slug"], r)             # 하트비트 기록
        if r["ok"]:
            cov = f" / 핸드SOS 총 {r['total']}" if r.get("total") else ""
            extra = f" (부분수집: {r['partial']})" if r.get("partial") else ""
            print(f"  ✓ 거래 {r['txns']}{cov} · 신규 {r['new_customers']}명{extra}")
        else:
            failed.append(r)
            heal = f" → 자가치유: python scripts/handsos_heal.py --slug {r['slug']}" if r.get("fail_dir") else ""
            print(f"  ✗ [{r['stage']}] {r['error']}{heal}")

    partials = [r for r in results if r.get("ok") and r.get("partial")]
    if failed:
        notify(cfg, "핸드SOS 동기화 실패: " + ", ".join(
            f"{f['slug']}({f['error']})" for f in failed)
            + " — 자가치유: python scripts/handsos_heal.py --slug <slug>")
    if partials:                                   # 부분수집도 조용히 넘기지 않는다(정직성)
        notify(cfg, "핸드SOS 부분수집: " + ", ".join(
            f"{p['slug']}({p['partial']})" for p in partials) + " — 다음 실행에서 재수확 권장")
    print(f"\n완료: 성공 {len(results)-len(failed)} / 실패 {len(failed)}"
          + (f" / 부분수집 {len(partials)}" if partials else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
