export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { getTenantId } from '@/lib/tenant';
import { cleanPath } from '@/lib/ops';

/**
 * 화면 오류 기록 — 오류 안내 화면(app/error.tsx)이 부른다(개선 계획 v5 P2). 어느 화면(경로, id 는 지움)과
 * Next 오류 번호(digest)만 남긴다 — 오류 본문엔 손님 정보가 섞일 수 있어 받지 않는다. sync-health 가 매일
 * 지난 24시간 건수를 본다(0023 ops_health). 기록이 안 돼도 화면엔 영향이 없게 늘 조용히 끝난다.
 */
export async function POST(request: Request) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ ok: false }, { status: 401 });
  const tenantId = await getTenantId(supabase);
  if (!tenantId) return NextResponse.json({ ok: false }, { status: 400 });

  const body = await request.json().catch(() => ({}));
  const detail = {
    path: cleanPath(body.path),
    digest: typeof body.digest === 'string' ? body.digest.slice(0, 40) : null,
  };
  const { error } = await supabase.from('ops_events').insert({ tenant_id: tenantId, kind: 'error', detail });
  return NextResponse.json({ ok: !error });
}
