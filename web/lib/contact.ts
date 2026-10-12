import { fetchAllRows } from './customers';
import type { supabaseServer } from './supabase/server';

/**
 * '연락함' — 챙길 고객 카드에서 문자·전화·문구 복사를 하면 남는 기록(care_items, kind='contact').
 *
 * 연락한 분이 다음 주에도 똑같이 목록 맨 위에 뜨면 이미 한 일을 매주 다시 하게 된다.
 * 그래서 연락 뒤 CONTACT_QUIET_DAYS 동안은 '할 일'(챙길 고객)에서 뺀다(onCareList).
 * 연락했다고 이탈 위험이 풀리진 않으니 이탈위험·재방문도래 숫자(손님 상태)는 그대로 센다.
 *
 * 문구 본문은 저장하지 않는다 — 손님 이름이 들어가는데 care_items 는 평문 컬럼이다.
 * 이름은 암호화해 두는 게 이 앱의 원칙(pii_enc)이라, 수단(문자·전화·복사)과 시각만 남긴다.
 */
export const CONTACT_QUIET_DAYS = 14;
export const CONTACT_VIAS = ['sms', 'call', 'copy'] as const;
export type ContactVia = (typeof CONTACT_VIAS)[number];

export function contactSince(now = Date.now()): string {
  return new Date(now - CONTACT_QUIET_DAYS * 86400000).toISOString();
}

/** 최근 CONTACT_QUIET_DAYS 안에 연락한 고객 id. */
export async function recentlyContactedIds(
  supabase: ReturnType<typeof supabaseServer>,
  tenantId: string,
): Promise<Set<string>> {
  const rows = await fetchAllRows<{ customer_id: string | null }>((from, to) =>
    supabase.from('care_items').select('customer_id')
      .eq('tenant_id', tenantId).eq('kind', 'contact').gte('sent_at', contactSince())
      .order('id').range(from, to));
  return new Set(rows.map((r) => r.customer_id).filter(Boolean) as string[]);
}

/** 전화번호에서 링크에 쓸 숫자만(국제번호 '+'는 남긴다). 번호가 아니면 null. */
export function phoneDigits(phone: string | null | undefined): string | null {
  const s = (phone ?? '').trim();
  if (!s) return null;
  const d = s.replace(/[^\d+]/g, '');
  return d.replace(/\D/g, '').length >= 9 ? d : null;
}

export const telHref = (digits: string): string => `tel:${digits}`;

/**
 * 문자 앱을 문구가 채워진 채로 연다. iOS 는 'sms:번호&body=', 안드로이드는 'sms:번호?body=' 를
 * 읽는다. '?&body=' 는 두 쪽이 다 읽는 형태다.
 */
export const smsHref = (digits: string, body: string): string => `sms:${digits}?&body=${encodeURIComponent(body)}`;
