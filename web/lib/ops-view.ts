/**
 * 운영자 화면(/ops, 개선 계획 v12 P2) 글줄 — 매일 감시(scripts/sync_health_check.py)와 같은 숫자 · 같은 모양.
 * 매장 단위 숫자만(손님 정보 없음). 0025 전(운영자 폰 · 앱 칸이 없음)이면 예전 모양.
 */
export type UsageRow = {
  slug: string | null;
  screens_7d: number | null;
  contacts_7d: number | null;
  last_seen: string | null;
  app_7d?: number | null;
  op_7d?: number | null;
  since?: string | null;
};
export type SpeedRow = { screen: string | null; opened: number | null; p50_ms: number | null; p90_ms: number | null; instant: number | null };

const KST = 9 * 3600000;

/** '10.15 15:01' — KST. */
export function kstStamp(iso: string): string {
  const d = new Date(Date.parse(iso) + KST);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getUTCMonth() + 1}.${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`;
}

export function seenWord(lastSeen: string | null, now: number): string {
  if (!lastSeen) return '기록 없음';
  const days = (now - Date.parse(lastSeen)) / 86400000;
  return days < 1 ? '오늘' : `${Math.floor(days)}일 전`;
}

/** 매장 한 줄 — '디자이너 화면 12번(앱 83%) · 연락 0명 · 마지막 사용 오늘 · 운영자 폰 35번'. */
export function usageLine(r: UsageRow, now: number): string {
  const screens = Number(r.screens_7d ?? 0);
  const contacts = Number(r.contacts_7d ?? 0);
  const seen = seenWord(r.last_seen, now);
  if (!('op_7d' in r)) return `화면 ${screens}번 · 연락 ${contacts}명 · 마지막 사용 ${seen}`;
  const app = Number(r.app_7d ?? 0);
  const op = Number(r.op_7d ?? 0);
  const share = screens ? `(앱 ${Math.round((app * 100) / screens)}%)` : '';
  return `디자이너 화면 ${screens}번${share} · 연락 ${contacts}명 · 마지막 사용 ${seen}` + (op ? ` · 운영자 폰 ${op}번` : '');
}

/** 맨 위 한 줄 — 기록 시작('0번'이 며칠 기준인지). 0025 전이면 null. */
export function sinceLine(rows: UsageRow[]): string | null {
  const since = rows.find((r) => r.since)?.since;
  if (since) return `화면 기록 ${kstStamp(since)}부터 · 운영자 폰은 따로 셈`;
  return rows.some((r) => 'op_7d' in r) ? '화면 기록 — 새 앱의 기록이 아직 없음' : null;
}

/** 화면 한 줄 — '보통 0.6초 · 느린 때 0.7초 · 4번 (바로 9번)'. 받아 둔 화면을 바로 보여준 것은 횟수만. */
export function speedLine(r: SpeedRow): string {
  const instant = Number(r.instant ?? 0);
  const waited = Number(r.opened ?? 0) - instant;
  const speed = r.p50_ms != null && r.p90_ms != null
    ? `보통 ${(r.p50_ms / 1000).toFixed(1)}초 · 느린 때 ${(r.p90_ms / 1000).toFixed(1)}초 · ${waited}번`
    : '기다린 적 없음';
  return speed + (instant ? ` (바로 ${instant}번)` : '');
}

/** CSP(보고만, v14 P0) 한 줄 — 'https://static.cloudflareinsights.com · 3번'. 출처와 숫자만. */
export type CspRow = { directive: string | null; blocked: string | null; n: number | null; last_at: string | null };

export function cspLine(r: CspRow): string {
  return `${r.blocked ?? '?'} · ${Number(r.n ?? 0)}번`;
}

/**
 * DB 용량(0028) 두 줄 — '전체 52MB / 무료 500MB (10%)' · '큰 표: transactions 12MB · …'. 매일 감시(fmt_db_size)와 같은 글.
 * 무료 플랜은 500MB 를 넘으면 읽기 전용이 된다(쓰기가 모두 막힘) — 400MB 를 넘으면 감시가 메일로 알린다.
 */
export type DbRow = { part: string | null; bytes: number | null };
export const DB_LIMIT_MB = 500;
export const DB_WARN_MB = 400;
const MB = 1048576;

/** '4.3MB' · '52MB' — 10MB 아래만 소수 한 자리(정수로 반올림해 감시와 같은 글). */
export function mbText(n: number): string {
  const v = (n || 0) / MB;
  if (v < 10) {
    const t = Math.round(v * 10);
    return `${Math.floor(t / 10)}.${t % 10}MB`;
  }
  return `${Math.round(v)}MB`;
}

export function dbLines(rows: DbRow[], limitMb = DB_LIMIT_MB, warnMb = DB_WARN_MB): string[] {
  const total = rows.find((r) => r.part === 'total');
  if (!total) return ['용량을 못 읽었다(전체 줄 없음)'];
  const bytes = Number(total.bytes ?? 0);
  const pct = Math.round((bytes / (limitMb * MB)) * 100);
  const over = bytes >= warnMb * MB;
  const lines = [`전체 ${mbText(bytes)} / 무료 ${limitMb}MB (${pct}%)` + (over ? ` · 경고 ${warnMb}MB 넘음` : '')];
  const tables = rows.filter((r) => r.part !== 'total').sort((a, b) => Number(b.bytes ?? 0) - Number(a.bytes ?? 0));
  if (tables.length) lines.push('큰 표: ' + tables.map((r) => `${r.part} ${mbText(Number(r.bytes ?? 0))}`).join(' · '));
  return lines;
}
