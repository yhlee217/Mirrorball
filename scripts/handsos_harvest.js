/* 핸드SOS 매출상세목록 수확 — 행 배열 반환(헤드리스/콘솔 공용).
 * handsos_console.js 의 검증된 로직(iframe 탐색 · gotoP 페이징 · 숨김 툴팁 추출)을
 * CSV·다운로드 없이 데이터만 돌려주도록 분리. Playwright 가 add_script_tag 로 주입 후
 *   await __handsosHarvest()  →  { rows:[...], total:N, error:null }
 * 콘솔에서 직접 쓰려면 이 파일 붙여넣고 `await __handsosHarvest()`.
 */
globalThis.__handsosHarvest = async function (opts) {
  opts = opts || {};
  const log = opts.log || function (m) { try { console.log(m); } catch (e) {} };
  const maxIdle = opts.maxPages || 0;            // 0 = 자동(총건수 기준)
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
  if (!ctx0) return { rows: [], total: 0, error: 'no-table' };  // 매출상세목록 표 못 찾음

  const bodyText = allDocs().map((d) => { try { return d.body ? d.body.innerText : ''; } catch (e) { return ''; } }).join('\n');
  const totalN = parseInt(((bodyText.match(/총\s*([\d,]+)\s*개/) || [])[1] || '0').replace(/,/g, ''), 10);
  const maxPage = maxIdle || (totalN ? Math.ceil(totalN / 20) + 3 : 400);

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
      if (tr.querySelector('th')) continue;
      const cells = [...tr.children];
      const cell = (i) => (i >= 0 && i < cells.length) ? norm(cells[i].innerText) : '';

      const dRaw = cell(HM.날짜);
      const date = (dRaw.match(/\d{2,4}\D\d{1,2}\D\d{1,2}/) || [''])[0];

      const ci = tr.querySelector('[id^="strCustomerInfo"]');
      let name = '', phone = '', custno = '', prev = '';
      if (ci) {
        const tt = ci.textContent;
        name = pick(tt, /고객명\s*[:：]\s*([^"\n+*]+)/);
        phone = pick(tt, /전화\s*번호\s*[:：]\s*([0-9\-]+)/);
        custno = pick(tt, /고객\s*번호\s*[:：]\s*([0-9]+)/);
        prev = pick(tt, /이전방문\s*[:：]\s*([0-9.\-]+)/);
      }
      const ownName = cell(HM.고객명) || name;

      let service = '';
      if (HM.상세메뉴 >= 0 && cells[HM.상세메뉴]) service = cells[HM.상세메뉴].getAttribute('title') || norm(cells[HM.상세메뉴].innerText);
      if (!service) service = cell(HM.메뉴);
      const price = cell(HM.결제액).replace(/[^\d]/g, '');

      if (!date && !ownName && !service && !price) continue;
      if (ownName) { last = { name: ownName, phone, custno }; }
      else { name = last.name; phone = phone || last.phone; custno = custno || last.custno; }
      const finalName = ownName || last.name;

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

  const curPage = (doc) => {
    try {
      const el = [...doc.querySelectorAll('.current,td,span,li,strong,b,em')].find((e) =>
        /(^|\s)(current|on|active|sel)(\s|$)/.test(' ' + (e.className || '') + ' ') && /^\d+$/.test(norm(e.textContent)));
      return el ? parseInt(norm(el.textContent), 10) : null;
    } catch (e) { return null; }
  };
  const firstSig = (t) => {
    try { const r = [...t.querySelectorAll('tr')].find((tr) => !tr.querySelector('th') && norm(tr.innerText)); return r ? norm(r.innerText).slice(0, 50) : ''; } catch (e) { return ''; }
  };
  const goNext = (ctx, target) => {
    const win = ctx.doc.defaultView;
    if (win && typeof win.gotoP === 'function') { try { win.gotoP(target); return true; } catch (e) {} }
    const re = new RegExp('gotoP\\(\\s*' + target + '\\b');
    const el = [...ctx.doc.querySelectorAll('td,a,span,li')].find((e) => {
      const oc = (e.getAttribute && e.getAttribute('onclick')) || '';
      return re.test(oc) || norm(e.textContent) === String(target);
    });
    if (el) { el.click(); return true; }
    return false;
  };

  for (let p = 1; p <= maxPage; p++) {
    const ctx = findCtx(); if (!ctx) break;
    harvestPage(ctx.t);
    log(`${p}p · 누적 ${recs.length}${totalN ? ' / ' + totalN : ''}`);
    if (totalN && recs.length >= totalN) break;

    const target = p + 1;
    const sigBefore = firstSig(ctx.t);
    if (!goNext(ctx, target)) break;

    let changed = false;
    for (let i = 0; i < 50; i++) {
      await sleep(300);
      const c2 = findCtx(); if (!c2) continue;
      const cp = curPage(c2.doc);
      if ((cp && cp >= target) || (firstSig(c2.t) && firstSig(c2.t) !== sigBefore)) { changed = true; break; }
      if (i === 14) goNext(c2, target);
    }
    if (!changed) return { rows: recs, total: totalN, error: 'pagination-stalled', stoppedAt: p };
  }

  return { rows: recs, total: totalN, error: null };
};
