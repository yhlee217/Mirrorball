/* 핸드SOS 매출상세목록 → CSV (설치 0 · 콘솔용)  v3: iframe + gotoP 페이징 + 상세보기 툴팁 추출
 *
 * 사용: 매출상세목록(기간 전체) 검색 → 표 보이게 → F12 > Console > 이 코드 붙여넣고 Enter.
 * 결과 handsos_매출상세.csv (날짜·고객명·전화번호전체·고객번호·이전방문·상세메뉴·담당·결제액·메모)
 */
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();

  const allDocs = () => {
    const out = [document];
    const scan = (d) => {
      let fs = []; try { fs = [...d.querySelectorAll('iframe,frame')]; } catch (e) { return; }
      for (const f of fs) { let cd = null; try { cd = f.contentDocument; } catch (e) {} if (cd && !out.includes(cd)) { out.push(cd); scan(cd); } }
    };
    scan(document); return out;
  };
  const findCtx = () => {
    for (const d of allDocs()) {
      let t = null;
      try { t = [...d.querySelectorAll('table')].find((tb) => /고객명/.test(tb.innerText) && /날짜/.test(tb.innerText)); } catch (e) {}
      if (t) return { doc: d, t };
    }
    return null;
  };

  const ctx0 = findCtx();
  if (!ctx0) { console.warn("'고객명/날짜' 표 못 찾음 — 매출상세목록이 보이는지 확인"); return; }

  const bodyText = allDocs().map((d) => { try { return d.body ? d.body.innerText : ''; } catch (e) { return ''; } }).join('\n');
  const totalN = parseInt(((bodyText.match(/총\s*([\d,]+)\s*개/) || [])[1] || '0').replace(/,/g, ''), 10);
  const maxPage = totalN ? Math.ceil(totalN / 20) + 3 : 400;

  // 헤더 → 컬럼 인덱스
  const hrow = [...ctx0.t.querySelectorAll('tr')].find((r) => /고객명/.test(r.innerText));
  const heads = hrow ? [...hrow.children].map((c) => norm(c.innerText)) : [];
  const col = (name) => heads.findIndex((h) => h.includes(name));
  const HM = { 날짜: col('날짜'), 고객명: col('고객명'), 상세메뉴: col('상세메뉴'), 메뉴: col('메뉴'), 담당: col('담당'), 결제액: col('결제액') };

  const seen = new Set();
  const recs = [];
  let last = { name: '', phone: '', custno: '' };

  const pick = (txt, re) => norm((txt.match(re) || [])[1] || '');

  function harvestPage(t) {
    for (const tr of [...t.querySelectorAll('tr')]) {
      if (tr.querySelector('th')) continue;                 // 헤더행
      const cells = [...tr.children];
      const cell = (i) => (i >= 0 && i < cells.length) ? norm(cells[i].innerText) : '';

      const dRaw = cell(HM.날짜);
      const date = (dRaw.match(/\d{2,4}\D\d{1,2}\D\d{1,2}/) || [''])[0];

      // 고객정보 툴팁(숨김 → textContent)
      const ci = tr.querySelector('[id^="strCustomerInfo"]');
      let name = '', phone = '', custno = '', prev = '';
      if (ci) {
        const tt = ci.textContent;
        name = pick(tt, /고객명\s*[:：]\s*([^"\n+]+)/);
        phone = pick(tt, /전화\s*번호\s*[:：]\s*([0-9\-]+)/);
        custno = pick(tt, /고객\s*번호\s*[:：]\s*([0-9]+)/);
        prev = pick(tt, /이전방문\s*[:：]\s*([0-9.\-]+)/);
      }
      const ownName = name || cell(HM.고객명);

      // 상세메뉴: title 속성 우선
      let service = '';
      if (HM.상세메뉴 >= 0 && cells[HM.상세메뉴]) service = cells[HM.상세메뉴].getAttribute('title') || norm(cells[HM.상세메뉴].innerText);
      if (!service) service = cell(HM.메뉴);
      const price = cell(HM.결제액).replace(/[^\d]/g, '');

      if (!date && !ownName && !service && !price) continue;  // 빈 채움행
      if (ownName) { last = { name: ownName, phone, custno }; }
      else { name = last.name; phone = phone || last.phone; custno = custno || last.custno; }
      const finalName = ownName || last.name;

      // 시술 메모 툴팁
      const md = tr.querySelector('[id^="saleStrMemoList"]');
      const memo = md ? norm(md.textContent.replace(/상세보기/, '')) : '';

      const rec = {
        날짜: date, 고객명: finalName, 전화번호: phone || '', 고객번호: custno || '',
        이전방문: prev, 상세메뉴: service, 담당: cell(HM.담당), 결제액: price, 메모: memo,
      };
      const key = [date, finalName, service, price, memo].join('|');
      if (!seen.has(key)) { seen.add(key); recs.push(rec); }
    }
  }

  for (let p = 1; p <= maxPage; p++) {
    const ctx = findCtx(); if (!ctx) break;
    const before = recs.length;
    harvestPage(ctx.t);
    console.log(`${p}p · 누적 ${recs.length}${totalN ? ' / ' + totalN : ''}`);
    if (totalN && recs.length >= totalN) break;

    let moved = false;
    const win = ctx.doc.defaultView;
    if (win && typeof win.gotoP === 'function') { try { win.gotoP(p + 1); moved = true; } catch (e) {} }
    if (!moved) {
      const re = new RegExp('gotoP\\(\\s*' + (p + 1) + '\\b');
      const el = [...ctx.doc.querySelectorAll('td,a,span,li')].find((e) => {
        const oc = (e.getAttribute && e.getAttribute('onclick')) || '';
        return re.test(oc) || norm(e.textContent) === String(p + 1);
      });
      if (el) { el.click(); moved = true; }
    }
    if (!moved) { console.log('다음 페이지 없음 — 마지막'); break; }
    await sleep(1000);
    if (recs.length === before && p > 1) break;
  }

  if (!recs.length) { console.warn('수집된 행 없음'); return; }
  const cols = ['날짜', '고객명', '전화번호', '고객번호', '이전방문', '상세메뉴', '담당', '결제액', '메모'];
  const esc = (v) => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
  const csv = [cols.join(','), ...recs.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'handsos_매출상세.csv';
  document.body.appendChild(a); a.click(); a.remove();
  console.log('✓ 완료 — ' + recs.length + '건 CSV 다운로드 (전화번호·고객번호·이전방문·메모 포함)');
})();
