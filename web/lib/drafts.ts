import { addDays, daysBetween, dowMon, spanWords } from './week';
import type { Care } from './care-cycle';

/**
 * 챙길 고객 문자 문구 — 앱은 문구를 채워 문자 앱을 열 뿐, 보내기 전에 디자이너가 고칠 수 있다.
 * 화면(alerts/page.tsx)에 있던 이탈 위험·재방문 도래 문구를 그대로 옮기고, 첫 방문 손님 문구 둘을 더했다
 * (개선 계획 v4 P1).
 *   hello(안부)      — 예약 권유 없이 안부 + 오래 두고 쓸 관리 팁 한 줄(결정 2). 처음 온 분이 '나를 기억한다'고
 *                      느끼는 첫 접점이라, 누가 보냈는지(디자이너 이름)를 먼저 밝힌다.
 *   back(다시 오실 때) — 처음 받은 시술의 표준 주기가 지났을 때. 번호를 저장 안 했을 수 있어 역시 이름부터.
 */
export type DraftKind = 'overdue' | 'due' | 'hello' | 'back';

export type DraftInput = {
  kind: DraftKind;
  name: string;
  designer: string | null; // 첫 방문 문구의 자기소개(tenants.designer_name)
  svc: string | null; // 손님께 쓸 시술 이름(friendlyService — '남자컷(원장)' → '커트')
  care: Care | null; // 그 시술의 표준 주기·표현·팁(lib/care-cycle)
  days: number | null; // 마지막(첫) 방문 뒤 지난 날 — 달력 그대로, 오늘 기준
  when?: string; // hello: '오늘' · '어제' · '이번 주' · '지난주' · '지난번'(whenWord)
  loyal?: boolean; // overdue: 단골 말투
  cycleDays?: number | null; // due: 평소 주기(일)
};

/** 이름 뒤 '이에요/예요' — 받침이 있으면 '이에요'(하예원이에요), 없으면 '예요'(서하예요). */
export function copula(word: string): '이에요' | '예요' {
  const code = word.trim().slice(-1).charCodeAt(0) - 0xac00;
  if (!(code >= 0 && code <= 11171)) return '이에요';
  return code % 28 ? '이에요' : '예요';
}

/** 그날이 언제였나 — 안부 문구의 첫마디. 주는 월요일부터(lib/week dowMon). */
export function whenWord(day: string, today: string): string {
  const n = daysBetween(day, today);
  if (n <= 0) return '오늘';
  if (n === 1) return '어제';
  const monday = addDays(today, -dowMon(today));
  if (day >= monday) return '이번 주';
  if (day >= addDays(monday, -7)) return '지난주';
  return '지난번';
}

export function draftFor(d: DraftInput): string {
  const { name, svc, care } = d;
  switch (d.kind) {
    case 'hello': {
      const keep = care?.keep ? ` ${care.keep}` : '';
      const when = d.when ?? '지난번';
      if (d.designer) {
        const what = svc ? `${svc} 해드린` : '뵀던';
        return `${name}님, ${when} ${what} ${d.designer}${copula(d.designer)} 😊 지내보시니 괜찮으세요?${keep} 불편한 점 있으면 편하게 말씀 주세요!`;
      }
      const what = svc ? `${svc} 받으신` : '다녀가신';
      return `${name}님, ${when} ${what} 뒤로 지내보시니 괜찮으세요? 😊${keep} 불편한 점 있으면 편하게 말씀 주세요!`;
    }
    case 'back': {
      const hi = d.designer ? `${name}님, ${d.designer}${copula(d.designer)}! ` : `${name}님, `;
      const ago = d.days !== null && d.days > 0 ? `${spanWords(d.days)} 전 ` : '';
      const body = svc
        ? `${ago}처음 오셨을 때 ${svc} 해드렸는데, ${care?.phrase ?? '슬슬 관리하실 때쯤이라'} 연락드려요.`
        : `${ago}처음 뵙고 시간이 좀 지났네요.`;
      return `${hi}${body} 편하신 시간에 예약 도와드릴게요!`;
    }
    case 'overdue': {
      const m = d.days !== null ? Math.max(1, Math.round(d.days / 30)) : null;
      const open = d.loyal
        ? `${name}님, 오랜만이에요! 벌써 ${m}개월 됐네요. 늘 찾아주셔서 감사해요 🙏`
        : `${name}님, ${m ? m + '개월 만이에요' : '오랜만이에요'}! 잘 지내셨어요? 😊`;
      const mid =
        care && svc
          ? ` 지난 ${svc} ${care.phrase} 한번 뵙고 싶어서 연락드려요.`
          : svc
            ? ` 지난 ${svc} 이제 슬슬 관리할 시기라 생각나서 연락드려요.`
            : ` 슬슬 컨디션 체크 겸 한번 뵙고 싶어서요.`;
      return `${open}${mid} 편하신 때 편하게 연락 주세요!`;
    }
    case 'due':
      return care && svc
        ? `${name}님, 지난 ${svc} ${care.phrase} 연락드려요. 편하신 시간에 예약 도와드릴게요!`
        : `${name}님, ${svc ? '지난 ' + svc : '지난 시술'} 이제 관리해주실 시기예요${d.cycleDays ? ` (평소 ${d.cycleDays}일 주기)` : ''}. 편하신 시간에 예약 도와드릴게요!`;
  }
}
