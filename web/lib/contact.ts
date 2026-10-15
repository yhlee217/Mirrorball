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

export type ContactLog = { customer_id: string | null; sent_at: string | null };

/**
 * 연락 기록(손님 · 시각) — 지난 days 일. 홈은 이것 하나로 숨김(최근 CONTACT_QUIET_DAYS)과 '이번 주 다시 오른 분'
 * (숨김이 지난 7일 안에 끝남, lib/fresh)을 함께 센다 — 따로 받지 않게.
 */
export async function recentContactRows(
  supabase: ReturnType<typeof supabaseServer>,
  tenantId: string,
  days: number,
): Promise<ContactLog[]> {
  return fetchAllRows<ContactLog>((from, to) =>
    supabase.from('care_items').select('customer_id,sent_at')
      .eq('tenant_id', tenantId).eq('kind', 'contact').gte('sent_at', new Date(Date.now() - days * 86400000).toISOString())
      .order('id').range(from, to));
}

/** 받아 둔 연락 기록 중 최근 CONTACT_QUIET_DAYS 안에 연락한 손님 — recentlyContactedIds 와 같은 셈. */
export function quietIds(rows: ContactLog[], now = Date.now()): Set<string> {
  const since = Date.parse(contactSince(now));
  return new Set(
    rows.filter((r) => r.customer_id && r.sent_at && Date.parse(r.sent_at) >= since).map((r) => r.customer_id as string),
  );
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
 * 전화번호 뒷자리 4자리 — 고객 목록 검색용. 목록은 전 고객을 화면으로 내려보내므로 전체 번호
 * 대신 뒷자리만 보낸다. 전화가 오거나 "뒷자리 1234요" 할 때 찾는 용도면 이걸로 충분하다.
 */
export function phoneTail(phone: string | null | undefined): string {
  const d = (phone ?? '').replace(/\D/g, '');
  return d.length >= 4 ? d.slice(-4) : '';
}

/**
 * 고객 검색 — 숫자만 넣으면 전화번호 뒷자리로, 아니면 이름으로 찾는다. 하이픈·띄어쓰기는 무시.
 * 번호를 통째로 넣어도 뒤 4자리로 비교한다(화면엔 뒷자리만 있다).
 */
export function matchesQuery(r: { name: string; tail: string }, query: string): boolean {
  const q = query.trim();
  if (!q) return true;
  const digits = q.replace(/[\s-]/g, '');
  if (/^\d+$/.test(digits)) return !!r.tail && r.tail.endsWith(digits.slice(-4));
  return r.name.includes(q);
}

/**
 * 문자 앱을 문구가 채워진 채로 연다. iOS 는 'sms:번호&body=', 안드로이드는 'sms:번호?body=' 를
 * 읽는다. '?&body=' 는 두 쪽이 다 읽는 형태다.
 */
export const smsHref = (digits: string, body: string): string => `sms:${digits}?&body=${encodeURIComponent(body)}`;
