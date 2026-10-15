/**
 * 현재 매장 고르기(개선 계획 v8 · v11) — 소속이 여럿이면 가장 먼저 소속된 매장으로 고정한다(요청마다 바뀌지 않게).
 * 단 데모 매장(slug 'demo-…', api/onboard)은 뒤로 — 매장 연결 전에 '데모로 둘러보기'를 눌렀어도, 운영자가 실제
 * 매장을 이으면 실제 매장이 열린다. 전에는 먼저 생긴 데모가 이겨 SQL 로 소속을 지워야 풀렸다.
 * rows 는 소속된 순서(created_at, tenant_id)대로 온다. 매장 이름을 못 읽은 줄(tenants 없음)은 실제 매장으로 본다.
 */
export const DEMO_PREFIX = 'demo-';

export const isDemoSlug = (slug: string | null | undefined): boolean => !!slug && slug.startsWith(DEMO_PREFIX);

type Slug = { slug: string | null };
export type MembershipRow = { tenant_id: string; tenants?: Slug | Slug[] | null };

export function pickTenant(rows: MembershipRow[]): string | null {
  const slugOf = (r: MembershipRow) => (Array.isArray(r.tenants) ? r.tenants[0]?.slug : r.tenants?.slug) ?? null;
  return (rows.find((r) => !isDemoSlug(slugOf(r))) ?? rows[0])?.tenant_id ?? null;
}
