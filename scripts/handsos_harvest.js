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
      if (ownName === '고객명' || ownName === '성함') continue;   // 페이지마다 반복되는 헤더행 제외

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
  // 페이지 이동 함수 후보(핸드SOS 버전차) + '다음(블록)' 화살표 글리프
  const PAGE_FNS = ['gotoP', 'goPage', 'fnPaging', 'fn_paging', 'goPaging', 'page_move', 'fnPage'];
  const NEXT_RE = /^(›|»|▶|＞|>|다음|다음\s*페이지|next)$/i;
  const goNext = (ctx, target, cur) => {
    const win = ctx.doc.defaultView;
    // 1) 전역 페이지 함수(있으면 블록 경계도 통과) — 이름 변형 대응
    for (const fn of PAGE_FNS) {
      if (win && typeof win[fn] === 'function') { try { win[fn](target); return 'fn:' + fn; } catch (e) {} }
    }
    const cand = [...ctx.doc.querySelectorAll('a,td,span,li,button,input,area')];
    // 2) 목표 페이지 번호 링크(onclick 의 숫자 == target, 또는 보이는 텍스트 == target)
    const reN = new RegExp('(?:gotoP|goPage|page|paging)\\D*(' + target + ')\\b');
    let el = cand.find((e) => reN.test((e.getAttribute && e.getAttribute('onclick')) || '')
      || norm(e.textContent) === String(target));
    if (el) { el.click(); return 'num'; }
    // 3) 블록 경계: '다음(›/»/다음)' 화살표(텍스트·alt·title·onclick)
    el = cand.find((e) => {
      const t = norm(e.textContent);
      const a = (e.getAttribute && (e.getAttribute('alt') || e.getAttribute('title') || e.value || '')) || '';
      const oc = (e.getAttribute && e.getAttribute('onclick')) || '';
      return NEXT_RE.test(t) || NEXT_RE.test(norm(a)) || /(다음|next)/i.test(oc);
    });
    if (el) { el.click(); return 'arrow'; }
    // 4) onclick 페이지번호가 현재보다 큰 컨트롤(블록 이동 링크 등) 중 가장 작은 것
    let best = null, bestN = 1e9;
    cand.forEach((e) => {
      const m = ((e.getAttribute && e.getAttribute('onclick')) || '').match(/(?:gotoP|goPage|page|paging)\D*(\d+)/);
      if (m) { const n = parseInt(m[1], 10); if (n > (cur || 0) && n < bestN) { best = e; bestN = n; } }
    });
    if (best) { best.click(); return 'jump:' + bestN; }
    return false;
  };

  // 블록형 페이저 탈출: '다음 블록(›/»/다음)' 컨트롤을 눌러 gotoP 이 다음 페이지를 인식하게.
  const nextBlock = (ctx) => {
    const cand = [...ctx.doc.querySelectorAll('a,td,span,li,button,input,img,area')];
    const el = cand.find((e) => {
      const t = norm(e.textContent);
      const a = norm((e.getAttribute && (e.getAttribute('alt') || e.getAttribute('title') || e.value || '')) || '');
      const oc = (e.getAttribute && e.getAttribute('onclick')) || '';
      const hrefj = (e.getAttribute && e.getAttribute('href')) || '';
      return NEXT_RE.test(t) || NEXT_RE.test(a)
        || /(next|다음|block|nextBlock|goBlock|movePage)/i.test(oc)
        || /(next|다음)/i.test(hrefj);
    });
    if (el) { try { el.click(); return true; } catch (e) {} }
    return false;
  };

  // 멈춤 진단용: 페이지 컨트롤을 '하나씩' 나열(컨테이너 추측 없이). onclick/href 에 페이지함수가
  // 있거나, 텍스트/alt 가 화살표(›»다음)인 요소만. → 실제 <a onclick="gotoP(38)">38</a> 와 '다음' 컨트롤이 보인다.
  const pagerDump = (doc) => {
    try {
      const out = [];
      [...doc.querySelectorAll('[onclick],[href]')].forEach((e) => {
        const oc = ((e.getAttribute('onclick') || '') + ' ' + (e.getAttribute('href') || ''));
        if (/gotoP|goPage|goBlock|movePage|nextBlock|paging|fnPage/i.test(oc)) out.push(norm(e.outerHTML).slice(0, 160));
      });
      [...doc.querySelectorAll('a,button,span,td,img,area,input,li')].forEach((e) => {
        const t = norm(e.textContent);
        const a = norm((e.getAttribute('alt') || e.getAttribute('title') || e.value || ''));
        if (NEXT_RE.test(t) || NEXT_RE.test(a) || (a && /(다음|next)/i.test(a))) out.push('[arrow] ' + norm(e.outerHTML).slice(0, 160));
      });
      const uniq = [...new Set(out)];
      return uniq.length ? uniq.slice(0, 60).join('\n') : '(gotoP/화살표 컨트롤 못 찾음 — 이미지/플러그인 페이저일 수 있음)';
    } catch (e) { return String(e); }
  };

  let stallRetries = 0;
  for (let p = 1; p <= maxPage; p++) {
    const ctx = findCtx(); if (!ctx) break;
    harvestPage(ctx.t);
    log(`${p}p · 누적 ${recs.length}${totalN ? ' / ' + totalN : ''}`);
    if (totalN && recs.length >= totalN) break;

    const target = p + 1;
    const sigBefore = firstSig(ctx.t);
    const beforeCount = recs.length;
    const how = goNext(ctx, target, p);
    if (!how) {   // 다음 컨트롤 자체가 없음 — 마지막 페이지거나 페이저 구조 미상
      return { rows: recs, total: totalN, stoppedAt: p,
               error: (totalN && recs.length < totalN) ? 'no-next-control' : null,
               pager: pagerDump(ctx.doc) };
    }

    let changed = false;
    for (let i = 0; i < 40; i++) {                 // 최대 ~24s (느린 프레임·서버 대비 여유)
      await sleep(600);
      const c2 = findCtx(); if (!c2) continue;
      const cp = curPage(c2.doc);
      if ((cp && cp >= target) || (firstSig(c2.t) && firstSig(c2.t) !== sigBefore)) { changed = true; break; }
      // gotoP 이 안 먹으면(블록 경계) '다음 블록' 화살표를 누른 뒤 다시 gotoP — 이게 342/727 stall 핵심
      if (i === 6 || i === 16 || i === 28) { nextBlock(c2); await sleep(500); goNext(c2, target, p); }
    }
    if (!changed) {
      // 즉시 포기하지 않고, 다음블록 클릭 + 페이지 재산정 후 몇 번 더(블록 경계 흔들림 대비)
      if (stallRetries < 3) {
        stallRetries++;
        const c3 = findCtx(); if (c3) { nextBlock(c3); }
        p--; await sleep(1200); continue;
      }
      return { rows: recs, total: totalN, error: 'pagination-stalled', stoppedAt: p,
               how: how, harvestedNew: recs.length - beforeCount, pager: pagerDump(ctx.doc) };
    }
    stallRetries = 0;
  }

  return { rows: recs, total: totalN, error: null };
};
