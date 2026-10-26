export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { getTenantId } from '@/lib/tenant';
import { isOpsReader } from '@/lib/ops-gate';
import { cleanTiming } from '@/lib/ops';

/**
 * 화면 속도 기록 — 화면이 뜰 때 components/screen-timer 가 부른다(개선 계획 v7 P0). 경로(id 는 지움) ·
 * 밀리초 · 받아 둔 화면이었나 · 처음 열기였나만 남긴다(lib/ops cleanTiming). 매일 감시가 화면별 보통 ·
 * 느린 때와 매장별 화면 연 수를 숫자로만 읽는다(0024 ops_speed · ops_usage). 기록이 안 돼도(0024 전 등)
 * 화면엔 영향이 없다 — 폰은 답을 기다리지 않는다(sendBeacon).
 */
export async function POST(request: Request) {
  const supabase = await supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ ok: false }, { status: 401 });
  const tenantId = await getTenantId(supabase);
  if (!tenantId) return NextResponse.json({ ok: false }, { status: 400 });

  const detail = cleanTiming(await request.json().catch(() => null));
  if (!detail) return NextResponse.json({ ok: false }, { status: 400 });
  // 운영자 계정이면 폰 표시가 없어도(홈 화면 앱) 운영자 것으로 — 디자이너 사용 수에 섞이지 않게(lib/ops-gate)
  if (!detail.op && (await isOpsReader(supabase))) detail.op = true;
  const { error } = await supabase.from('ops_events').insert({ tenant_id: tenantId, kind: 'timing', detail });
  return NextResponse.json({ ok: !error });
}
