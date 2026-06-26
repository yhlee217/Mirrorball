/* 핸드SOS 매출상세목록 → CSV 자동 다운로드 (설치 0 · 브라우저 콘솔용)  v2: iframe 대응
 *
 * 사용:
 *  1) 핸드SOS 웹 로그인 → 매출분석 > 매출상세목록 → 기간 전체 → '검색' → 표가 보이게.
 *  2) F12 → 'Console(콘솔)' 탭.  (컨텍스트 드롭다운은 'top' 그대로 두면 됨 — 이 버전이 iframe 까지 찾음)
 *  3) 이 코드를 통째로 복사해 붙여넣고 Enter.
 *  4) 자동으로 페이지를 넘기며 수집 → handsos_매출상세.csv 다운로드.
 *
 * 표가 cross-origin iframe 이라 접근이 막히면: 콘솔 좌상단 컨텍스트 드롭다운('top ▾')을
 * 핸드SOS 내용 프레임으로 바꾼 뒤 다시 붙여넣어 실행.
 */
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  // top 문서 + 접근 가능한 모든 (중첩) iframe 문서 수집
  const allDocs = () => {
    const out = [document];
    const scan = (d) => {
      let frames = [];
      try { frames = [...d.querySelectorAll('iframe,frame')]; } catch (e) { return; }
      for (const f of frames) {
        let cd = null;
        try { cd = f.contentDocument; } catch (e) { cd = null; }
        if (cd && !out.includes(cd)) { out.push(cd); scan(cd); }
      }
    };
    scan(document);
    return out;
  };

  const findTable = () => {
    for (const d of allDocs()) {
      let t = null;
      try {
        t = [...d.querySelectorAll('table')]
          .find((tb) => /고객명/.test(tb.innerText) && /날짜/.test(tb.innerText));
      } catch (e) { t = null; }
      if (t) return { doc: d, t };
    }
    return null;
  };

  const bodyText = () => allDocs().map((d) => {
    try { return d.body ? d.body.innerText : ''; } catch (e) { return ''; }
  }).join('\n');

  const totalCount = (() => {
    const m = bodyText().match(/총\s*([\d,]+)\s*개/);
    return m ? parseInt(m[1].replace(/,/g, ''), 10) : 0;
  })();

  const clickText = (doc, t) => {
    let els = [];
    try { els = [...doc.querySelectorAll('a,button,li,span,div')]; } catch (e) { return false; }
    const el = els.find((e) => e.textContent.trim() === t && e.offsetParent !== null);
    if (el) { (el.closest('a,button,li') || el).click(); return true; }
    return false;
  };

  const isDataRow = (c) => /\d{2,4}\D\d{1,2}\D\d{1,2}/.test(c[0] || '');

  const seen = new Set();
  const rows = [];
  let header = null;

  for (let p = 1; p <= 400; p++) {
    const f = findTable();
    if (!f) {
      console.warn("'고객명/날짜' 표를 못 찾음 — 매출상세목록이 보이는지 확인. "
        + "여전히 안 되면 콘솔 컨텍스트 드롭다운을 핸드SOS 프레임으로 바꿔 재실행.");
      break;
    }
    const trs = [...f.t.querySelectorAll('tr')].map((tr) =>
      [...tr.querySelectorAll('th,td')].map((td) => (td.innerText || '').replace(/\s+/g, ' ').trim()));
    if (!header) header = trs.find((r) => r.includes('고객명')) || trs[0];

    const before = seen.size;
    for (const r of trs) {
      if (isDataRow(r)) { const k = r.join('|'); if (!seen.has(k)) { seen.add(k); rows.push(r); } }
    }
    console.log(`${p}p · 누적 ${rows.length}${totalCount ? ' / ' + totalCount : ''}`);
    if (totalCount && rows.length >= totalCount) break;

    let moved = clickText(f.doc, String(p + 1));
    if (!moved) { for (const a of ['›', '▶', '>', '다음', 'Next']) { if (clickText(f.doc, a)) { moved = true; break; } } }
    if (!moved) { console.log('다음 페이지 없음 — 마지막'); break; }
    await sleep(900);
    if (seen.size === before && p > 1) break;
  }

  if (!rows.length) { console.warn('수집된 행 없음'); return; }
  const esc = (c) => '"' + String(c || '').replace(/"/g, '""') + '"';
  const csv = [header, ...rows].map((r) => r.map(esc).join(',')).join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'handsos_매출상세.csv';
  document.body.appendChild(a); a.click(); a.remove();
  console.log('✓ 완료 — ' + rows.length + '건 CSV 다운로드');
})();
