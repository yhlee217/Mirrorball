// 콘텐츠 코치 — 문구 생성(템플릿 기준선, 무료·결정적).
// '진짜 AI' 다듬기는 /api/ai 온디맨드로만(제공자 추상화). 여기 함수들은 서버·클라 공용.
// 고객·SNS 에 나가는 문구의 시술명은 friendlyService 로 다듬는다(남자컷(부원장) → 커트).

import { kstNow } from './kst';
import { friendlyService } from '@/lib/service-name';

const HASHTAGS: Record<string, string[]> = {
  펌: ['#펌', '#볼륨매직', '#헤어펌', '#펌스타그램', '#셋팅펌'],
  염색: ['#염색', '#뿌리염색', '#헤어컬러', '#염색스타그램', '#새치커버'],
  클리닉: ['#헤어클리닉', '#두피케어', '#손상모케어', '#트리트먼트'],
  컷: ['#헤어컷', '#레이어드컷', '#단발머리', '#컷스타그램'],
};

export function svcCat(s: string): string | null {
  if (/펌|매직|볼륨|셋팅|디지털|웨이브/.test(s)) return '펌';
  if (/염색|컬러|뿌리|새치|이노아|탈색|블리치|하이라이트|톤다운|톤업/.test(s)) return '염색';
  if (/클리닉|트리트|케어|앰플|두피|스켈프/.test(s)) return '클리닉';
  if (/컷|커트/.test(s)) return '컷';
  return null;
}

export function hashtagsFor(service: string, salon?: string): string[] {
  const cat = svcCat(service);
  const base = (cat && HASHTAGS[cat]) || ['#오늘의헤어', '#헤어스타그램'];
  const extra = ['#헤어살롱', salon ? `#${salon.replace(/\s/g, '')}` : '#헤어디자이너'];
  return [...new Set([...base, ...extra])].slice(0, 7);
}

export function captionFor(service: string, salon?: string): string {
  const tags = hashtagsFor(service, salon).join(' '); // 해시태그 분류는 원본 메뉴명으로(정확도)
  const disp = friendlyService(service) || service;
  return `${disp} 시술 완료 ✨\n오늘도 정성껏 완성했어요. 마음에 드셨길 바라요 🥰\n예약·문의는 프로필 링크로!\n\n${tags}`;
}

/**
 * 방문이 며칠 전인지 말로. 수집이 주 1회라 목록의 방문은 대개 며칠 지난 것이어서,
 * '오늘 시술'이라 단정하면 고객에게 틀린 말이 나간다(닷새 전 시술에 "오늘 어떠셨어요?").
 */
function visitWhen(visitDate?: string | null): string {
  if (!visitDate) return '지난번';
  const today = kstNow().date;
  const days = Math.round((Date.parse(today) - Date.parse(visitDate)) / 86400000);
  if (Number.isNaN(days)) return '지난번';
  if (days <= 0) return '오늘';
  if (days === 1) return '어제';
  return '지난번';
}

export function reviewRequestFor(name: string, service?: string, visitDate?: string | null): string {
  const disp = friendlyService(service);
  const when = visitWhen(visitDate);
  const svc = disp ? `${when} ${disp} 시술` : `${when} 시술`;
  return `${name}님, ${svc} 어떠셨어요? 😊 만족하셨다면 네이버 플레이스에 짧게 리뷰 남겨주시면 큰 힘이 돼요. 다음에도 예쁘게 해드릴게요 🙏`;
}

// LLM 없을 때 '다듬기' 폴백 — 템플릿 재생성(무료 파일럿).
export function templateImprove(kind: string, ctx: Record<string, string>): string {
  if (kind === 'caption') return captionFor(ctx.service || '시술', ctx.salon);
  if (kind === 'review') return reviewRequestFor(ctx.name || '고객', ctx.service, ctx.visitDate);
  return ctx.text || '';
}

// LLM 프롬프트(온디맨드 시). 제공자(Cloudflare/Gemini/유료)와 무관하게 동일 프롬프트.
export function buildPrompt(kind: string, ctx: Record<string, string>): string {
  if (kind === 'caption')
    return `헤어살롱 인스타그램 게시물 캡션을 써줘. 시술명: ${friendlyService(ctx.service) || ctx.service}. 살롱: ${ctx.salon || '헤어살롱'}. 3~4줄, 친근한 존댓말, 이모지 1~2개, 마지막 줄에 관련 해시태그 5개. 과장·이모지 남발 금지.`;
  if (kind === 'review')
    return `${ctx.name}님에게 보낼 네이버 플레이스 리뷰 요청 메시지를 써줘. ${visitWhen(ctx.visitDate)} ${friendlyService(ctx.service) || '시술'}을 받음. 부담 없고 따뜻하게, 2~3문장, 존댓말, 이모지 1개.`;
  return ctx.text || '';
}
