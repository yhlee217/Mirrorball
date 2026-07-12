export const runtime = 'edge';

import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import { fetchAllRows } from '@/lib/customers';

type Row = {
  id: string;
  pii_enc: string | null;
  visit_count: number;
  total_won: number;
  last_visit: string | null;
  first_visit: string | null;
  revisit_state: string | null;
};

const STATE: Record<string, string> = { overdue: '이탈위험', due: '재방문도래', new: '신규' };
const q = (v: unknown) => '"' + String(v ?? '').replace(/"/g, '""') + '"';

// 고객 데이터 CSV 내보내기(본인 테넌트). 이름/전화 복호화 포함.
export async function GET() {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return new Response('unauthorized', { status: 401 });

  const { data: mem } = await supabase.from('memberships').select('tenant_id').limit(1).maybeSingle();
  if (!mem) return new Response('no tenant', { status: 400 });
  const tid = (mem as { tenant_id: string }).tenant_id;

  const { data: tenant } = await supabase.from('tenants').select('dek_wrapped').eq('id', tid).maybeSingle();
  let dek: Uint8Array | null = null;
  const dw = (tenant as { dek_wrapped: string | null } | null)?.dek_wrapped ?? null;
  if (dw) {
    try {
      dek = await unwrapDek(dw);
    } catch {
      dek = null;
    }
  }

  const rows = await fetchAllRows<Row>((from, to) =>
    supabase
      .from('customers')
      .select('id,pii_enc,visit_count,total_won,last_visit,first_visit,revisit_state')
      .order('id')
      .range(from, to),
  );

  const lines = ['이름,전화,방문횟수,누적매출,첫방문,마지막방문,상태'];
  for (const r of rows) {
    let name = '';
    let phone = '';
    if (dek && r.pii_enc) {
      try {
        const p = await decryptPII(r.pii_enc, dek);
        name = typeof p.name === 'string' ? p.name : '';
        phone = typeof p.phone === 'string' ? p.phone : '';
      } catch {
        /* noop */
      }
    }
    lines.push(
      [q(name), q(phone), r.visit_count, r.total_won || 0, q(r.first_visit), q(r.last_visit), q(STATE[r.revisit_state ?? ''] ?? '')].join(','),
    );
  }

  const csv = '﻿' + lines.join('\r\n'); // BOM → 엑셀 한글 깨짐 방지
  return new Response(csv, {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': 'attachment; filename="mirrorball-customers.csv"',
    },
  });
}
