export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { redirect, notFound } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';

type Cust = {
  id: string;
  tenant_id: string;
  pii_enc: string | null;
  visit_count: number;
  first_visit: string | null;
  last_visit: string | null;
  total_won: number;
  revisit_state: string | null;
};
type Tx = { id: string; date: string; service: string | null; amount_won: number };

const SIGNAL: Record<string, string> = { overdue: '이탈 위험', due: '재방문 도래', new: '신규' };

function won(n: number): string {
  if (!n) return '';
  return (n >= 10000 ? Math.round(n / 10000) + '만' : n.toLocaleString()) + '원';
}

export default async function CustomerPage({ params }: { params: { id: string } }) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: c } = await supabase
    .from('customers')
    .select('id,tenant_id,pii_enc,visit_count,first_visit,last_visit,total_won,revisit_state')
    .eq('id', params.id)
    .maybeSingle();
  if (!c) notFound();
  const cust = c as Cust;

  let name = '고객';
  const { data: tenant } = await supabase.from('tenants').select('dek_wrapped').eq('id', cust.tenant_id).maybeSingle();
  const dw = (tenant as { dek_wrapped: string | null } | null)?.dek_wrapped ?? null;
  if (dw && cust.pii_enc) {
    try {
      const dek = await unwrapDek(dw);
      const p = await decryptPII(cust.pii_enc, dek);
      if (typeof p.name === 'string') name = p.name;
    } catch {
      // 폴백
    }
  }

  const { data: tx } = await supabase
    .from('transactions')
    .select('id,date,service,amount_won')
    .eq('customer_id', cust.id)
    .order('date', { ascending: false })
    .limit(50);
  const history = (tx as Tx[]) ?? [];

  return (
    <main className="wrap">
      <div className="bar">
        <Link href="/" className="back">‹ 홈</Link>
      </div>
      <div className="body">
        <div className="chd">
          <div className="cav">{name.charAt(0)}</div>
          <div>
            <h2>{name} 님</h2>
            <div className="s">
              {cust.visit_count}회 방문{cust.total_won ? ' · 누적 ' + won(cust.total_won) : ''}
            </div>
          </div>
        </div>

        <div className="kv">
          {cust.first_visit && <div className="r"><span className="k">첫 방문</span><span>{cust.first_visit}</span></div>}
          {cust.last_visit && <div className="r"><span className="k">마지막 방문</span><span>{cust.last_visit}</span></div>}
          {cust.revisit_state && (
            <div className="r"><span className="k">신호</span><span>{SIGNAL[cust.revisit_state] ?? cust.revisit_state}</span></div>
          )}
        </div>

        <div className="card">
          <div className="ch">시술 이력{history.length ? ' · ' + history.length + '건' : ''}</div>
          {history.length ? (
            history.map((h) => (
              <div className="li" key={h.id}>
                <div className="bd"><div className="nm" style={{ fontWeight: 600 }}>{h.service ?? '시술'}</div></div>
                <div className="rt">{h.date}</div>
              </div>
            ))
          ) : (
            <div className="empty">시술 이력이 없어요 (임포트 재실행 시 채워집니다)</div>
          )}
        </div>
      </div>
    </main>
  );
}
