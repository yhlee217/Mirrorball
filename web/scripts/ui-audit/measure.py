"""UI 측정 — render.cjs 가 그린 7개 화면을 폰 크기(390×844)로 열어 글자를 잰다(UX 계획 v3 §6).

재는 것
  · 보이는 글자 수(접힌 ?·더 보기 안은 빼고) · 설명글 비율 · 12px 미만 · 대비 4.5:1 미만 · 회색 글자
  · 화면 길이(몇 화면인지) · 첫 화면(아래 탭바 위 784px)에 다 들어오는 줄
'설명글'은 계산 방법·근거처럼 매번 읽을 필요 없는 글이 쓰던 자리(EXPL)다 — v3 전 측정과 같은 목록이라
전후를 견줄 수 있다.

사용: python3 measure.py <out> [--check] [--shots] [--json 파일]
  --check  계획의 목표(TARGETS)를 하나라도 못 넘으면 1로 끝난다
  --shots  <out>/shots 에 화면 전체와 첫 화면을 찍어 둔다
브라우저를 띄우지 못하면 2로 끝난다(테스트는 이때 건너뛴다).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCREENS = ["home", "alerts", "visits", "customers", "carte", "stats", "settings"]
VIEW = {"width": 390, "height": 844}
FOLD = 784  # 844 − 아래 탭바 60

# 설명글이 쓰던 자리 — v3 전 측정(playbook/UX_PLAN_v3.md §1)과 같은 목록
EXPL = ".note,.csub,.crit-hint,.crit-sub,.empty-h,.sweep-hint,.fc-s,.sig-w,.rec-w,.sub2,.coh-o,.wp,.dim,.sec-h,.hello .s,.tip,.k,.help-b"

# 화면마다 '첫 화면에 몇 줄'을 셀 자리
ROWS = {
    "home": "first-card .li",  # 오늘 예약 카드(첫 .card.bf)의 줄
    "alerts": ".crow",
    "visits": ".visit",
    "customers": ".card .li",
}

JS = r"""
([fold, expl, rowSel]) => {
  const probe = document.createElement('span');
  probe.style.color = 'var(--muted)';
  document.body.appendChild(probe);
  const muted = getComputedStyle(probe).color;
  probe.remove();
  const lum = (c) => {
    const m = c.match(/\d+(\.\d+)?/g).map(Number);
    const f = (v) => { v /= 255; return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(m[0]) + 0.7152 * f(m[1]) + 0.0722 * f(m[2]);
  };
  const bgOf = (el) => {
    for (let e = el; e; e = e.parentElement) {
      const b = getComputedStyle(e).backgroundColor;
      if (b && !b.startsWith('rgba(0, 0, 0, 0)') && b !== 'transparent') return b;
    }
    return getComputedStyle(document.body).backgroundColor;
  };
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const m = { total: 0, expl: 0, small: 0, low: 0, gray: 0, lowSamples: [] };
  while (w.nextNode()) {
    const t = w.currentNode;
    const el = t.parentElement;
    const n = (t.textContent || '').replace(/\s+/g, '').length;
    if (!n || !el || el.closest('.tabbar,style,script') || !el.checkVisibility()) continue;
    const cs = getComputedStyle(el);
    m.total += n;
    if (el.closest(expl)) m.expl += n;
    if (parseFloat(cs.fontSize) < 12) m.small += n;
    if (cs.color === muted) m.gray += n;
    const L1 = lum(cs.color), L2 = lum(bgOf(el));
    if ((Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05) < 4.5) {
      m.low += n;
      if (m.lowSamples.length < 5) m.lowSamples.push(t.textContent.trim().slice(0, 20));
    }
  }
  const seen = (e) => e && e.checkVisibility() && e.getBoundingClientRect().bottom <= fold;
  let rows = null;
  if (rowSel === 'first-card .li') {
    const card = document.querySelector('.card.bf');
    rows = card ? [...card.querySelectorAll('.li')].filter(seen).length : 0;
  } else if (rowSel) {
    rows = [...document.querySelectorAll(rowSel)].filter(seen).length;
  }
  m.rows = rows;
  m.height = document.documentElement.scrollHeight;
  // 카르테 — 이름·상태 뱃지·한 줄 띠·메모·권할 것이 다 첫 화면에 들어오나
  m.carteTop = ['.chd h2', '.chd .ctag', '.facts', '.memo-ai', '.rec'].map((s) => seen(document.querySelector(s)));
  // 통계 — 첫 화면에 다 보이는 숫자 · 할 일 손잡이
  m.nums = [...document.querySelectorAll('.num')].filter(seen).length;
  m.pills = [...document.querySelectorAll('.pill')].filter(seen).length;
  return m;
}
"""


def pct(a: int, b: int) -> float:
    return a * 100 / b if b else 0.0


# 목표 — UX 계획 v3 §4 · §6. (이름, 통과 여부를 내는 함수, 지금 값을 보여줄 함수)
TARGETS = [
    ("설명글 10% 이하", lambda r, t: pct(t["expl"], t["total"]) <= 10, lambda r, t: f"{pct(t['expl'], t['total']):.0f}%"),
    ("12px 미만 5% 이하", lambda r, t: pct(t["small"], t["total"]) <= 5, lambda r, t: f"{pct(t['small'], t['total']):.0f}%"),
    ("대비 4.5:1 미만 0자", lambda r, t: t["low"] == 0, lambda r, t: f"{t['low']}자"),
    ("회색 글자 1,200자 이하", lambda r, t: t["gray"] <= 1200, lambda r, t: f"{t['gray']:,}자"),
    ("홈: 첫 화면 예약 3줄 이상", lambda r, t: r["home"]["rows"] >= 3, lambda r, t: f"{r['home']['rows']}줄"),
    ("챙길 고객: 첫 화면 6명 이상", lambda r, t: r["alerts"]["rows"] >= 6, lambda r, t: f"{r['alerts']['rows']}명"),
    ("고객 목록: 첫 화면 10줄 이상", lambda r, t: r["customers"]["rows"] >= 10, lambda r, t: f"{r['customers']['rows']}줄"),
    ("방문: 첫 화면 8줄 이상", lambda r, t: r["visits"]["rows"] >= 8, lambda r, t: f"{r['visits']['rows']}줄"),
    ("카르테: 이름·상태·띠·메모·권할 것 첫 화면", lambda r, t: all(r["carte"]["carteTop"]),
     lambda r, t: f"{sum(r['carte']['carteTop'])}/5"),
    ("통계: 숫자 4개 + 할 일 첫 화면", lambda r, t: r["stats"]["nums"] >= 4 and r["stats"]["pills"] >= 1,
     lambda r, t: f"숫자 {r['stats']['nums']} · 할 일 {r['stats']['pills']}"),
]


def launch(p):
    exe = os.environ.get("UI_AUDIT_CHROMIUM") or next(
        (x for x in ["/opt/pw-browsers/chromium"] if os.path.exists(x)), None)
    return p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    html = Path(a.out) / "html"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright 가 없어 잴 수 없어요(pip install playwright).", file=sys.stderr)
        return 2

    res: dict[str, dict] = {}
    with sync_playwright() as p:
        try:
            b = launch(p)
        except Exception as e:  # 브라우저가 없는 환경
            print(f"브라우저를 띄우지 못했어요: {e}", file=sys.stderr)
            return 2
        pg = b.new_page(viewport=VIEW)
        for s in SCREENS:
            pg.goto((html / f"{s}.html").resolve().as_uri())
            res[s] = pg.evaluate(JS, [FOLD, EXPL, ROWS.get(s)])
            if a.shots:
                shots = Path(a.out) / "shots"
                shots.mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(shots / f"{s}.png"), full_page=True)
                pg.screenshot(path=str(shots / f"{s}-first.png"))
        b.close()

    keys = ("total", "expl", "small", "low", "gray")
    tot = {k: sum(m[k] for m in res.values()) for k in keys}
    if a.json:
        Path(a.json).write_text(json.dumps({"screens": res, "total": tot}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{'화면':<10}{'글자':>6}{'설명글':>7}{'12px미만':>9}{'대비<4.5':>9}{'회색':>6}{'길이(화면)':>11}{'첫 화면 줄':>10}")
    for s, m in res.items():
        rows = "-" if m["rows"] is None else str(m["rows"])
        print(f"{s:<10}{m['total']:>6}{pct(m['expl'], m['total']):>6.0f}%{pct(m['small'], m['total']):>8.0f}%"
              f"{pct(m['low'], m['total']):>8.0f}%{m['gray']:>6}{m['height'] / VIEW['height']:>10.1f}{rows:>10}")
    print(f"{'합계':<10}{tot['total']:>6}{pct(tot['expl'], tot['total']):>6.0f}%{pct(tot['small'], tot['total']):>8.0f}%"
          f"{pct(tot['low'], tot['total']):>8.0f}%{tot['gray']:>6}")
    for s, m in res.items():
        if m["lowSamples"]:
            print(f"  대비 미달 {s}: {' | '.join(m['lowSamples'])}")

    print("\n목표(UX 계획 v3)")
    failed = 0
    for name, ok, now in TARGETS:
        good = ok(res, tot)
        failed += not good
        print(f"  {'✓' if good else '✗'} {name} — {now(res, tot)}")
    return 1 if a.check and failed else 0


if __name__ == "__main__":
    sys.exit(main())
