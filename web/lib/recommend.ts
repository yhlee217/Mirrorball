import { careFor, CYCLE_BY_CAT } from './care-cycle';
import { txKind } from './tx';
import { addDays, daysBetween } from './week';
import { awayDays, type OffDays } from './offdays';
import { spanWords } from './briefing';

/**
 * 다음 시술 추천(UX 계획 B3) — '다음엔 뭘 권하면 좋을까'. 추정이라 화면은 '추천 시술'로, 옅게 쓴다(판단은 디자이너 몫).
 *
 * (가) 때가 된 시술 — 최근 1년 받아온 시술 종류마다 마지막으로 받은 날과 주기를 견준다. 주기는 그 손님이
 *     같은 종류를 두 번 이상 받았으면 본인 간격(중앙값), 아니면 표준표(lib/care-cycle). 휴가는 빼고 센다
 *     (챙길 고객과 같은 기준). 주기의 1~3배 사이만 — 3배를 넘겼으면 그 시술을 그만두신 쪽에 가깝다.
 *     늘 받던 시술(본인 간격이 있는 것)을 먼저, 그다음 많이 지난 순.
 * (나) 함께 권할 것 — 손님이 최근 1년 한 번도 안 받은 갈래(염색·펌·클리닉) 중, 이 매장에서 같은 시술을
 *     받는 손님들이 많이 함께 받는 것. 근거가 일반론이 아니라 이 디자이너의 기록이다.
 * 많아야 2개 — (가) 1순위, (나) 1순위(없으면 (가) 2순위). 이번에 예약한 시술의 갈래는 뺀다.
 *
 * 워크인 집계('손님')도 한 명으로 섞이지만, 1년 손님 수백 명 중 한둘이라 비율에 거의 영향이 없다.
 */

/** 최근 이만큼의 기록만 본다 — 메뉴와 손님 취향이 바뀌므로. */
export const LOOKBACK = 365;
/** 주기의 이 배수를 넘기면 '때가 됐다'보다 '그만두셨다'에 가깝다. */
const MAX_RATIO = 3;
/** '종류 A 손님'이 이만큼은 있어야 함께 받는 비율을 믿는다. */
export const MIN_SUPPORT = 20;
/** 함께 받는 비율이 이 아래면 권할 근거가 약하다. */
export const MIN_SHARE = 0.15;

/** 시술 갈래 — 같은 갈래 안의 다른 메뉴는 '새로 권할 것'이 아니다(뿌리염색 손님에게 염색은 새롭지 않다). */
export const FAMILY: Record<string, string> = {
  커트: '커트', 남자커트: '커트', 여자커트: '커트', 주니어커트: '커트', 앞머리컷: '커트',
  염색: '염색', 뿌리염색: '염색',
  펌: '펌', 다운펌: '펌', 뿌리펌: '펌',
  클리닉: '클리닉',
};
/** 함께 권할 수 있는 갈래 — 커트는 누구나 받아 '함께 권할 것'이 아니다. */
const CROSS = ['염색', '펌', '클리닉'];

/** 메뉴 이름 → 시술 종류들(lib/care-cycle). '남자컷+다운펌'처럼 한 거래에 묶여 있으면 나눠서 본다. */
export function catsOf(service: string | null | undefined): string[] {
  const out = new Set<string>();
  for (const part of (service ?? '').split(/[+,·]/)) {
    const c = careFor(part.trim());
    if (c) out.add(c.cat);
  }
  return [...out];
}

export type Visit = { date: string; cats: string[] };

/** 손님별 방문(날짜순) — 시술 거래만, 같은 날은 한 방문으로 합친다. 종류를 알 수 없는 메뉴는 빠진다. */
export function visitsByCustomer(
  tx: { customer_id: string | null; date: string | null; service: string | null; kind: string | null }[],
): Map<string, Visit[]> {
  const days = new Map<string, Map<string, Set<string>>>();
  // 메뉴 이름은 몇십 가지가 수천 번 되풀이된다 — 정규식 판정은 이름마다 한 번만
  const memo = new Map<string, string[]>();
  const catsMemo = (s: string | null) => {
    const k = s ?? '';
    let v = memo.get(k);
    if (!v) memo.set(k, (v = catsOf(k)));
    return v;
  };
  for (const t of tx) {
    if (!t.customer_id || !t.date || txKind(t.kind, t.service) !== 'service') continue;
    const cats = catsMemo(t.service);
    if (!cats.length) continue;
    const byDay = days.get(t.customer_id) ?? new Map<string, Set<string>>();
    const set = byDay.get(t.date) ?? new Set<string>();
    for (const c of cats) set.add(c);
    byDay.set(t.date, set);
    days.set(t.customer_id, byDay);
  }
  const out = new Map<string, Visit[]>();
  for (const [id, byDay] of days) {
    out.set(id, [...byDay].map(([date, s]) => ({ date, cats: [...s] })).sort((a, b) => (a.date < b.date ? -1 : 1)));
  }
  return out;
}

/** ref 바로 전 1년의 방문 — 추천은 그 시점까지 알 수 있었던 것만 본다. */
const lastYear = (vs: Visit[], ref: string) => {
  const from = addDays(ref, -LOOKBACK);
  return vs.filter((v) => v.date < ref && v.date >= from);
};

export type Due = { cat: string; last: string; cycle: number; personal: boolean; ratio: number };

/** (가) 때가 된 시술 — ref(그날) 기준. */
export function dueServices(vs: Visit[], ref: string, off: OffDays): Due[] {
  const dates = new Map<string, string[]>();
  for (const v of lastYear(vs, ref)) {
    for (const c of v.cats) {
      const a = dates.get(c);
      if (a) a.push(v.date);
      else dates.set(c, [v.date]);
    }
  }
  const out: Due[] = [];
  for (const [cat, ds] of dates) {
    ds.sort();
    const last = ds[ds.length - 1];
    let cycle = CYCLE_BY_CAT[cat] ?? 42;
    let personal = false;
    if (ds.length >= 2) {
      const gaps = ds.slice(1).map((d, i) => daysBetween(ds[i], d)).sort((a, b) => a - b);
      const m = gaps[Math.floor(gaps.length / 2)];
      if (m > 0) {
        cycle = m;
        personal = true;
      }
    }
    const ratio = awayDays(last, ref, off) / cycle;
    if (ratio >= 1 && ratio <= MAX_RATIO) out.push({ cat, last, cycle, personal, ratio });
  }
  return out.sort((a, b) => Number(b.personal) - Number(a.personal) || b.ratio - a.ratio);
}

/** 매장 데이터 — 종류 A 를 받은 손님 수(n)와, 그중 갈래 F 도 받은 비율·그 갈래에서 가장 흔한 종류. */
export type PairStats = Record<string, { n: number; fam: Record<string, { share: number; label: string }> }>;

/** ref 전 1년, 손님별 시술 종류 집합으로 센다. */
export function pairStats(byCust: Map<string, Visit[]>, ref: string): PairStats {
  const n: Record<string, number> = {};
  const both: Record<string, Record<string, number>> = {};
  const kinds: Record<string, Record<string, Record<string, number>>> = {};
  for (const vs of byCust.values()) {
    const cats = new Set(lastYear(vs, ref).flatMap((v) => v.cats));
    if (!cats.size) continue;
    const fams = new Map<string, string[]>();
    for (const c of cats) {
      const f = FAMILY[c];
      if (f) fams.set(f, [...(fams.get(f) ?? []), c]);
    }
    for (const a of cats) {
      n[a] = (n[a] ?? 0) + 1;
      for (const [f, cs] of fams) {
        if (f === FAMILY[a]) continue;
        both[a] ??= {};
        both[a][f] = (both[a][f] ?? 0) + 1;
        kinds[a] ??= {};
        kinds[a][f] ??= {};
        for (const c of cs) kinds[a][f][c] = (kinds[a][f][c] ?? 0) + 1;
      }
    }
  }
  const out: PairStats = {};
  for (const a of Object.keys(n)) {
    const fam: Record<string, { share: number; label: string }> = {};
    for (const [f, k] of Object.entries(both[a] ?? {})) {
      const top = Object.entries(kinds[a][f]).sort((x, y) => y[1] - x[1] || (x[0] < y[0] ? -1 : 1))[0][0];
      fam[f] = { share: k / n[a], label: top };
    }
    out[a] = { n: n[a], fam };
  }
  return out;
}

export type Cross = { fam: string; label: string; from: string; share: number };

/** (나) 함께 권할 것 — 손님이 받은 종류들(cats) 중 근거가 가장 강한 하나. */
export function crossSell(cats: string[], pairs: PairStats): Cross | null {
  const has = new Set(cats.map((c) => FAMILY[c]).filter(Boolean));
  let best: Cross | null = null;
  for (const a of cats) {
    const p = pairs[a];
    if (!p || p.n < MIN_SUPPORT) continue;
    for (const f of CROSS) {
      const e = p.fam[f];
      if (has.has(f) || !e || e.share < MIN_SHARE) continue;
      if (!best || e.share > best.share) best = { fam: f, label: e.label, from: a, share: e.share };
    }
  }
  return best;
}

/** reason 은 카르테용 한 줄, short 는 예약 브리핑처럼 자리가 좁은 곳용. */
export type Rec = { kind: 'due' | 'cross'; label: string; reason: string; short: string };

const dueRec = (d: Due, ref: string): Rec => ({
  kind: 'due',
  label: d.cat,
  reason: `마지막 ${spanWords(daysBetween(d.last, ref))} 전 · ${
    d.personal ? `보통 ${spanWords(d.cycle)}마다` : `표준 ${spanWords(d.cycle)}`
  }`,
  short: `마지막 ${spanWords(daysBetween(d.last, ref))} 전`,
});

const crossRec = (c: Cross): Rec => ({
  kind: 'cross',
  label: c.label,
  reason: `${c.from} 손님 ${Math.round(c.share * 100)}%가 ${c.fam}도 받아요${c.label !== c.fam ? ` · 주로 ${c.label}` : ''}`,
  short: `${c.from} 손님 ${Math.round(c.share * 100)}%가 함께`,
});

/**
 * 권해볼 것(많아야 2개). ref = 권하는 날(카르테는 오늘, 예약 브리핑은 예약일).
 * exclude = 이번에 이미 예약한 시술의 종류들 — 그 갈래는 빼고 권한다.
 */
export function recommend(vs: Visit[], pairs: PairStats | null, ref: string, off: OffDays, exclude: string[] = []): Rec[] {
  const exFam = new Set(exclude.map((c) => FAMILY[c]).filter(Boolean));
  const dues = dueServices(vs, ref, off).filter((d) => !exFam.has(FAMILY[d.cat]));
  const cats = [...new Set(lastYear(vs, ref).flatMap((v) => v.cats))];
  const cross = pairs ? crossSell(cats, pairs) : null;
  const out: Rec[] = [];
  if (dues[0]) out.push(dueRec(dues[0], ref));
  if (cross && !exFam.has(cross.fam)) out.push(crossRec(cross));
  else if (dues[1]) out.push(dueRec(dues[1], ref));
  return out;
}

export type Hit = { n: number; hit: number; base: number };

/** 적중률은 비율이라 방문 1,000번이면 충분하다(오차 ±1.5%p 안팎) — 큰 매장도 화면이 느려지지 않게 고르게 뽑아 센다. */
const MAX_EVAL = 1000;

/**
 * 추천이 맞았나 — since~asOf 의 실고객 방문마다, 그 전 기록만으로 추천했다면 그 방문 시술에 들어 있었나.
 * base 는 아무 근거 없이 같은 것을 찍었을 때 맞을 확률(그 종류·갈래가 방문에 나오는 비율)의 평균.
 * 추천이 쓸모 있으려면 hit/n 이 base 보다 높아야 한다. (함께 권할 것의 비율표는 같은 1년 기록으로 만들어
 * 살짝 유리하다 — 근사치다.) 방문이 MAX_EVAL 보다 많으면 고르게 건너뛰며 센다.
 */
export function backtest(
  byCust: Map<string, Visit[]>,
  pairs: PairStats,
  realIds: Set<string>,
  since: string,
  asOf: string,
  off: OffDays,
): { due: Hit; cross: Hit } {
  const evals: { vs: Visit[]; v: Visit }[] = [];
  const catN: Record<string, number> = {};
  const famN: Record<string, number> = {};
  for (const [id, vs] of byCust) {
    if (!realIds.has(id)) continue;
    for (const v of vs) {
      if (v.date < since || v.date > asOf) continue;
      evals.push({ vs, v });
      for (const c of v.cats) catN[c] = (catN[c] ?? 0) + 1;
      for (const f of new Set(v.cats.map((c) => FAMILY[c]))) famN[f] = (famN[f] ?? 0) + 1;
    }
  }
  const due: Hit = { n: 0, hit: 0, base: 0 };
  const cross: Hit = { n: 0, hit: 0, base: 0 };
  const total = evals.length || 1;
  const step = Math.max(1, Math.ceil(evals.length / MAX_EVAL));
  for (let i = 0; i < evals.length; i += step) {
    const { vs, v } = evals[i];
    const d = dueServices(vs, v.date, off)[0];
    if (d) {
      due.n++;
      if (v.cats.includes(d.cat)) due.hit++;
      due.base += (catN[d.cat] ?? 0) / total;
    }
    const c = crossSell([...new Set(lastYear(vs, v.date).flatMap((x) => x.cats))], pairs);
    if (c) {
      cross.n++;
      if (v.cats.some((x) => FAMILY[x] === c.fam)) cross.hit++;
      cross.base += (famN[c.fam] ?? 0) / total;
    }
  }
  if (due.n) due.base /= due.n;
  if (cross.n) cross.base /= cross.n;
  return { due, cross };
}
