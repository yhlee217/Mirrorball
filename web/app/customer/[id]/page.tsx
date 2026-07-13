export const runtime = 'edge';
export const dynamic = 'force-dynamic';

import Link from 'next/link';
import { redirect, notFound } from 'next/navigation';
import { supabaseServer } from '@/lib/supabase/server';
import { unwrapDek, decryptPII } from '@/lib/crypto';
import { mergeSettings, isVip } from '@/lib/settings';
import CustomerNote from './customer-note';

type Cust = {
  id: string;
  tenant_id: string;
  pii_enc: string | null;
  visit_count: number;
  first_visit: string | null;
  last_visit: string | null;
  total_won: number;
  revisit_state: string | null;
  revisit_cycle_days: number | null;
  prefer_tags: string[] | null;
  memo: string | null;
};
type Tx = { id: string; date: string; service: string | null; amount_won: number };
type Bk = { date: string; time: string | null; service: string | null };

const SIGNAL: Record<string, string> = { overdue: '이탈 위험', due: '재방문 도래', new: '신규' };

function won(n: number): string {
  if (!n) return '0원';
  return (n >= 10000 ? Math.round(n / 10000) + '만' : n.toLocaleString()) + '원';
}
function monthsAgo(d: string | null): number | null {
  if (!d) return null;
  return Math.max(1, Math.round((Date.now() - new Date(d).getTime()) / 2592000000));
}

export default async function CustomerPage({ params }: { params: { id: string } }) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: c } = await supabase
    .from('customers')
    .select(
      'id,tenant_id,pii_enc,visit_count,first_visit,last_visit,total_won,revisit_state,revisit_cycle_days,prefer_tags,memo',
    )
    .eq('id', params.id)
    .maybeSingle();
  if (!c) notFound();
  const cust = c as Cust;

  const today = new Date().toISOString().slice(0, 10);
  const [{ data: tenant }, { data: tx }, { data: bk }] = await Promise.all([
    supabase.from('tenants').select('dek_wrapped,settings').eq('id', cust.tenant_id).maybeSingle(),
    supabase
      .from('transactions')
      .select('id,date,service,amount_won')
      .eq('customer_id', cust.id)
      .order('date', { ascending: false })
      .limit(100),
    supabase
      .from('bookings')
      .select('date,time,service')
      .eq('customer_id', cust.id)
      .gte('date', today)
      .order('date', { ascending: true })
      .order('time', { ascending: true, nullsFirst: false })
      .limit(1),
  ]);

  const settings = mergeSettings((tenant as { settings: unknown } | null)?.settings);
  const dw = (tenant as { dek_wrapped: string | null } | null)?.dek_wrapped ?? null;

  let name = '고객';
  if (dw && cust.pii_enc) {
    try {
      const dek = await unwrapDek(dw);
      const p = await decryptPII(cust.pii_enc, dek);
      if (typeof p.name === 'string' && p.name) name = p.name;
    } catch {
      /* 폴백 */
    }
  }

  const history = (tx as Tx[]) ?? [];
  const nextBk = ((bk as Bk[]) ?? [])[0] ?? null;
  const vip = isVip(cust, settings);
  const avg = cust.visit_count ? Math.round(cust.total_won / cust.visit_count) : 0;

  const svcCount = new Map<string, number>();
  for (const h of history) {
    const s = (h.service || '').trim();
    if (s) svcCount.set(s, (svcCount.get(s) || 0) + 1);
  }
  const topSvc = [...svcCount.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);

  const overdue = cust.revisit_state === 'overdue';
  const due = cust.revisit_state === 'due';
  const reason = overdue && cust.last_visit ? `${monthsAgo(cust.last_visit)}개월 미방문` : due ? '재방문 시기예요' : '';

  return (
    <main className="wrap">
      <div className="bar">
        <Link href="/" className="back">‹ 홈</Link>
      </div>
      <div className="body">
        <div className="chd">
          <div className="cav">{name.charAt(0)}</div>
          <div>
            <h2>
              {name} 님{vip ? <span className="tag-vip">VIP</span> : null}
            </h2>
            <div className="s">
              {cust.visit_count}회 방문{cust.total_won ? ' · 누적 ' + won(cust.total_won) : ''}
            </div>
          </div>
        </div>

        {(overdue || due) && (
          <div className={'signal-card ' + (overdue ? 'x' : 'd')}>
            <div className="sig-t">{SIGNAL[cust.revisit_state as string]}</div>
            <div className="sig-w">
              {reason}
              {cust.revisit_cycle_days ? ` · 평소 ${cust.revisit_cycle_days}일 주기` : ''}
            </div>
          </div>
        )}

        <div className="stat-grid">
          <div className="stat"><div className="sn">{cust.visit_count}</div><div className="sl">방문</div></div>
          <div className="stat"><div className="sn">{won(cust.total_won)}</div><div className="sl">누적 매출</div></div>
          <div className="stat"><div className="sn">{won(avg)}</div><div className="sl">객단가</div></div>
          <div className="stat"><div className="sn">{cust.revisit_cycle_days ? cust.revisit_cycle_days + '일' : '-'}</div><div className="sl">재방문 주기</div></div>
        </div>

        {nextBk && (
          <div className="card" style={{ padding: '13px 15px' }}>
            <div className="ch" style={{ padding: 0, marginBottom: 6 }}>다음 예약</div>
            <div className="set-row">
              {nextBk.date}
              {nextBk.time ? ' ' + nextBk.time : ''}
              {nextBk.service ? ' · ' + nextBk.service : ''}
            </div>
          </div>
        )}

        <CustomerNote id={cust.id} initMemo={cust.memo ?? ''} initTags={cust.prefer_tags ?? []} />

        {topSvc.length > 0 && (
          <div className="card" style={{ padding: '13px 15px' }}>
            <div className="ch" style={{ padding: 0, marginBottom: 8 }}>자주 받는 시술</div>
            <div className="tags">
              {topSvc.map(([s, n]) => (
                <span key={s} className="tagr">
                  {s} <b>{n}</b>
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="card">
          <div className="ch">시술 이력{history.length ? ' · ' + history.length + '건' : ''}</div>
          {history.length ? (
            history.map((h) => (
              <div className="li" key={h.id}>
                <div className="bd">
                  <div className="nm" style={{ fontWeight: 600 }}>{h.service ?? '시술'}</div>
                  <div className="sub">{h.date}</div>
                </div>
                <div className="rt">{won(h.amount_won)}</div>
              </div>
            ))
          ) : (
            <div className="empty">시술 이력이 없어요</div>
          )}
        </div>
      </div>
    </main>
  );
}
