import { redirect } from 'next/navigation';
import { supabaseServer } from './supabase/server';
import { unwrapDek, decryptPII } from './crypto';
import { pickTenant, type MembershipRow } from './tenant-pick';

/**
 * 서버 컴포넌트가 매번 반복하던 앞부분 — 로그인 확인 → 소속 테넌트 → 복호화 키.
 *
 * 화면 8개가 같은 20줄을 각자 들고 있었고, 그러다 보니 조금씩 어긋났다(이름 복호화 4곳이
 * 서로 다른 분기를 갖고 있었다). 인증·암호화 경로라 어긋나면 조용히 위험해지므로 한 곳에 모은다.
 * RLS 가 최종 방어선이지만 앱도 같은 기준으로 움직여야 한다.
 */

/** 로그인 필수. 아니면 /login 으로 보낸다. */
export async function requireUser() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');
  return { supabase, user };
}

/** 이 사용자가 속한 테넌트. 없으면 null(가입 직후 등). */
export async function getTenantId(
  supabase: ReturnType<typeof supabaseServer>,
): Promise<string | null> {
  // 정렬 없이 첫 줄을 고르면 여러 매장에 속한 계정은 요청마다 다른 매장이 될 수 있다 — 가장 먼저 소속된 매장으로 고정.
  // 데모 매장은 뒤로(lib/tenant-pick) — 매장 연결 전에 데모를 만들었어도 실제 매장이 열린다(개선 계획 v11 P0).
  const { data, error } = await supabase.from('memberships').select('tenant_id,tenants(slug)')
    .order('created_at', { ascending: true }).order('tenant_id').limit(10);
  if (!error) return pickTenant((data as MembershipRow[] | null) ?? []);
  // 매장 이름을 함께 못 읽으면 예전처럼 가장 먼저 소속된 매장 — 이 길이 막혀 매장을 잃는 일은 없게
  const { data: first } = await supabase.from('memberships').select('tenant_id')
    .order('created_at', { ascending: true }).order('tenant_id').limit(1).maybeSingle();
  return (first as { tenant_id: string } | null)?.tenant_id ?? null;
}

/**
 * 로그인 + 소속까지 필수인 화면용. 소속이 없으면 홈으로 보낸다.
 * 홈(app/page.tsx)만은 소속이 없을 때 온보딩 화면을 보여줘야 하므로 이걸 쓰지 않고
 * requireUser + getTenantId 를 직접 조합한다.
 */
export async function requireTenant() {
  const { supabase, user } = await requireUser();
  const tenantId = await getTenantId(supabase);
  if (!tenantId) redirect('/');
  return { supabase, user, tenantId };
}

/** 감싸인 테넌트 키를 푼다. 실패해도 화면은 떠야 하므로(이름만 '고객'으로 보임) null 로 삼킨다. */
export async function openDek(wrapped: string | null | undefined): Promise<Uint8Array | null> {
  if (!wrapped) return null;
  try {
    return await unwrapDek(wrapped);
  } catch {
    return null;
  }
}

/**
 * 암호문에서 이름을 꺼내는 함수를 만든다.
 *
 * 이름이 빈 문자열인 경우까지 '고객'으로 돌려준다 — 화면 4곳 중 2곳만 이 분기를 갖고 있어
 * 같은 고객이 홈에서는 빈칸, 카르테에서는 '고객'으로 보였다. 안전한 쪽으로 통일한다.
 */
export function nameReader(dek: Uint8Array | null) {
  return async (pii: string | null | undefined): Promise<string> => {
    if (!dek || !pii) return '고객';
    try {
      const p = await decryptPII(pii, dek);
      return typeof p.name === 'string' && p.name ? p.name : '고객';
    } catch {
      return '고객';
    }
  };
}

/** 이름과 전화번호를 함께 연다 — 챙길 고객 카드의 문자·전화 버튼용. 번호는 있을 때만. */
export function contactReader(dek: Uint8Array | null) {
  return async (pii: string | null | undefined): Promise<{ name: string; phone: string | null }> => {
    if (!dek || !pii) return { name: '고객', phone: null };
    try {
      const p = await decryptPII(pii, dek);
      return {
        name: typeof p.name === 'string' && p.name ? p.name : '고객',
        phone: typeof p.phone === 'string' && p.phone.trim() ? p.phone : null,
      };
    } catch {
      return { name: '고객', phone: null };
    }
  };
}
