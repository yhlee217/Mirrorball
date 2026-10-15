import { careFor, soonestCare, type Care } from './care-cycle';
import { draftFor, whenWord } from './drafts';
import { friendlyService } from './service-name';
import { txKind } from './tx';
import { daysBetween } from './week';

/**
 * 챙길 고객 문구 — 챙길 고객 탭과 상세보기가 같은 함수로 만든다(개선 계획 v12 P1). 전에는 챙길 고객 탭에서만 문구를 채웠고
 * 상세보기 💬 는 빈 문자였다 — 이력을 보다 연락하려면 탭으로 돌아가야 했다.
 */

/**
 * 문구를 정하는 시술 — 기준 방문일(첫 방문 손님은 첫 방문, 그 밖엔 마지막 방문)에 받은 시술(원본 메뉴명) 가운데 표준 주기가
 * 가장 짧은 것. 같은 날 둘을 받았을 때 전에는 2회 이상 손님만 받아 온 순서(DB)로 갈렸다 — 이제 첫 방문 손님과 같은 규칙.
 */
export function careService(services: (string | null | undefined)[]): { raw: string | null; svc: string | null; care: Care | null } {
  const pick = soonestCare(services);
  const raw = pick?.service ?? services.find((s): s is string => !!s) ?? null;
  return { raw, svc: friendlyService(raw) || null, care: pick?.care ?? careFor(raw) };
}

/** 시술을 받은 가장 늦은 날의 시술들 — 손님 거래(원본)에서. 충전 · 제품은 빼고 센다. */
export function lastServiceDay(
  txs: { date: string | null; service: string | null; kind: string | null }[],
): { day: string | null; services: string[] } {
  let day: string | null = null;
  for (const t of txs) {
    if (!t.date || !t.service || txKind(t.kind, t.service) !== 'service') continue;
    const d = t.date.slice(0, 10);
    if (!day || d > day) day = d;
  }
  const services: string[] = [];
  for (const t of txs) {
    if (day && t.date?.slice(0, 10) === day && t.service && txKind(t.kind, t.service) === 'service' && !services.includes(t.service)) {
      services.push(t.service);
    }
  }
  return { day, services };
}

/** state = 챙길 고객 상태(hello · back · due · overdue). services = 위 기준 방문일의 시술. */
export function careDraft(o: {
  state: string;
  name: string;
  designer: string | null;
  lastVisit: string | null;
  today: string;
  services: (string | null | undefined)[];
  visitCount: number;
  vipVisits: number;
  cycleDays: number | null;
}): string {
  const last = o.lastVisit ? o.lastVisit.slice(0, 10) : null;
  const days = last ? daysBetween(last, o.today) : null;
  const { svc, care } = careService(o.services);
  const base = { name: o.name, designer: o.designer, svc, care, days };
  if (o.state === 'hello') return draftFor({ kind: 'hello', ...base, when: last ? whenWord(last, o.today) : undefined });
  if (o.state === 'back') return draftFor({ kind: 'back', ...base });
  return draftFor({
    kind: o.state === 'overdue' ? 'overdue' : 'due', ...base,
    loyal: o.visitCount >= o.vipVisits, cycleDays: o.cycleDays,
  });
}
