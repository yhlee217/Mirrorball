import { redirect } from 'next/navigation';
import { supabaseServer } from './supabase/server';
import { unwrapDek, decryptPII } from './crypto';

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
  const { data } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  return (data as { tenant_id: string } | null)?.tenant_id ?? null;
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
