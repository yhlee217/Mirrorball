export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { getTenantId } from '@/lib/tenant';
import { cleanCsp } from '@/lib/ops';

/**
 * CSP 어긋남 기록(개선 계획 v14 P0) — 브라우저 보고(report-uri, application/csp-report)와 화면의 어긋남 소식
 * (components/csp-watch)을 받는다. 어긋난 규칙 · 막힐 뻔한 것의 출처 · 화면 경로(id 는 지움)만 남긴다(lib/ops cleanCsp).
 * 로그인한 매장의 기록으로만(로그인 전 화면 · 다른 매장은 남기지 않는다). 0026 전이거나 실패해도 늘 조용히 204.
 * '화면 오류'(0023 ops_health 실패 기준)와 섞지 않으려 종류를 따로 둔다(kind 'csp').
 */
export async function POST(request: Request) {
  const done = new NextResponse(null, { status: 204 });
  const text = await request.text().catch(() => '');
  if (!text || text.length > 8000) return done;
  let body: unknown = null;
  try {
    body = JSON.parse(text);
  } catch {
    return done;
  }
  const detail = cleanCsp(body);
  if (!detail) return done;
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return done;
  const tenantId = await getTenantId(supabase);
  if (!tenantId) return done;
  await supabase.from('ops_events').insert({ tenant_id: tenantId, kind: 'csp', detail });
  return done;
}
