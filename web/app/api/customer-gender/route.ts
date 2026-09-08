export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';

// 고객 성별 직접 지정 — 시술명 추정이 못 가른 고객을 사람이 채운다.
// gender(추정)가 아니라 gender_manual 에 쓴다. 워커는 이 칸을 건드리지 않으므로
// 주간 재계산에 덮이지 않는다. null 을 보내면 지정을 지우고 다시 추정값을 따른다.
export async function POST(request: Request) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  const body = await request.json();
  const id = body.customer_id;
  if (!id || typeof id !== 'string') return NextResponse.json({ error: 'no id' }, { status: 400 });

  const g = body.gender;
  if (g !== 'M' && g !== 'F' && g !== null) {
    return NextResponse.json({ error: 'bad gender' }, { status: 400 });
  }

  const { error } = await supabase.from('customers').update({ gender_manual: g }).eq('id', id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, gender: g });
}
