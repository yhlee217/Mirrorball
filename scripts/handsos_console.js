/* 핸드SOS 매출상세목록 → CSV 자동 다운로드 (설치 0 · 브라우저 콘솔용)
 *
 * 사용:
 *  1) 핸드SOS 웹(s.handsos.com) 로그인 → 매출분석 > 매출상세목록 → 기간 전체 → '검색'
 *     → 표(1페이지)가 보이게 한다.
 *  2) 키보드 F12 (또는 우클릭 > 검사) → 'Console(콘솔)' 탭
 *  3) 아래 코드를 통째로 복사해 콘솔에 붙여넣고 Enter.
 *  4) 페이지를 자동으로 넘기며 수집 → 끝나면 handsos_매출상세.csv 가 다운로드됨.
 *  5) 그 CSV 를 컨시어지에게 전달 → import_handsos.py 로 흡수.
 *
 * 멈추면(표 못 찾음/페이지 안 넘어감) 콘솔 로그를 캡처해 공유하면 보정 가능.
 */
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const findTable = () => [...document.querySelectorAll('table')]
    .find((t) => /고객명/.test(t.innerText) && /날짜/.test(t.innerText));
  const totalCount = (() => {
    const m = document.body.innerText.match(/총\s*([\d,]+)\s*개/);
    return m ? parseInt(m[1].replace(/,/g, ''), 10) : 0;
  })();
  const clickText = (t) => {
    const el = [...document.querySelectorAll('a,button,li,span,div')]
      .find((e) => e.textContent.trim() === t && e.offsetParent !== null);
    if (el) { (el.closest('a,button,li') || el).click(); return true; }
    return false;
  };
  const isDataRow = (c) => /\d{2,4}\D\d{1,2}\D\d{1,2}/.test(c[0] || '');

  const seen = new Set();
  const rows = [];
  let header = null;

  for (let p = 1; p <= 400; p++) {
    const t = findTable();
    if (!t) { console.warn("'고객명/날짜' 표를 못 찾음 — 매출상세목록이 보이는지 확인"); break; }
    const trs = [...t.querySelectorAll('tr')].map((tr) =>
      [...tr.querySelectorAll('th,td')].map((td) => (td.innerText || '').replace(/\s+/g, ' ').trim()));
    if (!header) header = trs.find((r) => r.includes('고객명')) || trs[0];
    const before = seen.size;
    for (const r of trs) {
      if (isDataRow(r)) { const k = r.join('|'); if (!seen.has(k)) { seen.add(k); rows.push(r); } }
    }
    console.log(`${p}p · 누적 ${rows.length}${totalCount ? ' / ' + totalCount : ''}`);
    if (totalCount && rows.length >= totalCount) break;

    let moved = clickText(String(p + 1));
    if (!moved) { for (const a of ['›', '▶', '>', '다음', 'Next']) { if (clickText(a)) { moved = true; break; } } }
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
