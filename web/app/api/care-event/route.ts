export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { getTenantId } from '@/lib/tenant';
import { cleanCare } from '@/lib/ops';

/**
 * 챙길 고객 펼침 기록 — 줄을 펼칠 때 alerts-list 가 부른다(개선 계획 v16 P1). 펼쳤다는 것과 운영자 폰 · 홈 화면 앱
 * 여부만 남긴다(lib/ops cleanCare — 어느 손님인지는 없다). 매일 감시 · /ops 가 매장별 숫자로만 읽는다(0029 ops_usage).
 * 0029 전이면 기록이 거절되지만 화면엔 영향이 없다 — 폰은 답을 기다리지 않는다(sendBeacon).
 */
export async function POST(request: Request) {
  const supabase = await supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ ok: false }, { status: 401 });
  const tenantId = await getTenantId(supabase);
  if (!tenantId) return NextResponse.json({ ok: false }, { status: 400 });

  const detail = cleanCare(await request.json().catch(() => null));
  if (!detail) return NextResponse.json({ ok: false }, { status: 400 });
  const { error } = await supabase.from('ops_events').insert({ tenant_id: tenantId, kind: 'care', detail });
  return NextResponse.json({ ok: !error });
}
