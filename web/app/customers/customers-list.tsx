'use client';
import { useMemo, useState } from 'react';
import Link from 'next/link';
import { isVip as isVipS, isLapsed, type TenantSettings } from '@/lib/settings';

type Row = {
  id: string;
  name: string;
  visit_count: number;
  total_won: number;
  last_visit: string | null;
  first_visit: string | null;
  state: string | null;
  hasBooking: boolean;
  hasPhone: boolean;
  churned: boolean;
  visits_90d: number | null; // VIP 판정(최근 자주 오심)용 — 워커가 미리 집계
  visits_180d: number | null;
  visits_365d: number | null;
  services: string[];
};

const DAY = 86400000;
const daysSince = (d: string | null) => (d ? Math.floor((Date.now() - new Date(d).getTime()) / DAY) : Infinity);
const won = (n: number) => (n >= 10000 ? Math.round(n / 10000) + '만' : String(n));

export default function CustomersList({
  rows,
  settings,
  initialFilter = null,
}: {
  rows: Row[];
  settings: TenantSettings;
  initialFilter?: string | null;
}) {
  const [q, setQ] = useState('');
  // 홈 신호 타일(이탈위험/재방문도래/신규/VIP 등)에서 넘어온 초기 필터를 켠 상태로 시작.
  const [chips, setChips] = useState<Set<string>>(() => new Set(initialFilter ? [initialFilter] : []));
  const [visitF, setVisitF] = useState('');
  const [revF, setRevF] = useState('');
  const [recF, setRecF] = useState('');
  const [svcF, setSvcF] = useState('');
  const [sort, setSort] = useState('recent');

  const vip = (r: Row) => isVipS(r, settings);
  const manH = Math.round(settings.revenue_high / 10000);
  const manM = Math.round(settings.revenue_mid / 10000);

  const toggle = (k: string) =>
    setChips((s) => {
      const n = new Set(s);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });

  const filtered = useMemo(() => {
    const term = q.trim();
    let f = rows;
    if (term) f = f.filter((r) => r.name.includes(term));
    // 이탈위험·재방문도래는 홈 신호와 같은 기준으로 — '이탈 판정'(설정: N개월 초과 미방문 등)
    // 고객과 디자이너가 직접 이탈 표시한 고객은 홈 숫자에서 빠지므로 여기서도 빼야
    // '눌렀더니 인원이 다른' 불일치가 안 생긴다.
    if (chips.has('overdue')) f = f.filter((r) => r.state === 'overdue' && !isLapsed(r, settings) && !r.churned);
    if (chips.has('due')) f = f.filter((r) => r.state === 'due' && !isLapsed(r, settings) && !r.churned);
    if (chips.has('new')) f = f.filter((r) => r.state === 'new' && !r.churned);
    if (chips.has('vip')) f = f.filter((r) => isVipS(r, settings) && !r.churned);
    if (chips.has('churned')) f = f.filter((r) => r.churned);
    if (chips.has('booking')) f = f.filter((r) => r.hasBooking);
    if (chips.has('nophone')) f = f.filter((r) => !r.hasPhone);
    if (visitF === 'reg') f = f.filter((r) => r.visit_count >= 10);
    else if (visitF === 'rep') f = f.filter((r) => r.visit_count >= 3 && r.visit_count <= 9);
    else if (visitF === 'new') f = f.filter((r) => r.visit_count <= 2);
    if (revF === '100') f = f.filter((r) => r.total_won >= settings.revenue_high);
    else if (revF === '50') f = f.filter((r) => r.total_won >= settings.revenue_mid && r.total_won < settings.revenue_high);
    else if (revF === 'lo') f = f.filter((r) => r.total_won < settings.revenue_mid);
    if (recF === '1m') f = f.filter((r) => daysSince(r.last_visit) <= 30);
    else if (recF === '3m') f = f.filter((r) => daysSince(r.last_visit) <= 90);
    else if (recF === '6m') f = f.filter((r) => daysSince(r.last_visit) <= 180);
    else if (recF === '1y') f = f.filter((r) => daysSince(r.last_visit) > 365);
    if (svcF) f = f.filter((r) => r.services.includes(svcF));

    const arr = [...f];
    arr.sort((a, b) => {
      if (sort === 'revenue') return b.total_won - a.total_won;
      if (sort === 'visits') return b.visit_count - a.visit_count;
      if (sort === 'avg') return b.total_won / (b.visit_count || 1) - a.total_won / (a.visit_count || 1);
      if (sort === 'new') return (b.first_visit || '').localeCompare(a.first_visit || '');
      if (sort === 'name') return a.name.localeCompare(b.name);
      return (b.last_visit || '').localeCompare(a.last_visit || ''); // recent
    });
    return arr;
  }, [rows, q, chips, visitF, revF, recF, svcF, sort, settings]);

  const Chip = ({ k, label }: { k: string; label: string }) => (
    <button type="button" className={'fchip' + (chips.has(k) ? ' on' : '')} onClick={() => toggle(k)}>
      {label}
    </button>
  );

  return (
    <>
      <input className="search" placeholder="이름 검색" value={q} onChange={(e) => setQ(e.target.value)} />

      <div className="fchips">
        <Chip k="overdue" label="이탈위험" />
        <Chip k="due" label="재방문도래" />
        <Chip k="new" label="신규" />
        <Chip k="vip" label="VIP" />
        <Chip k="booking" label="예약있음" />
        <Chip k="nophone" label="전화없음" />
        <Chip k="churned" label="이탈" />
      </div>

      <div className="fsel">
        <select value={visitF} onChange={(e) => setVisitF(e.target.value)}>
          <option value="">방문 전체</option>
          <option value="reg">단골 10회+</option>
          <option value="rep">재방문 3~9회</option>
          <option value="new">신규 1~2회</option>
        </select>
        <select value={revF} onChange={(e) => setRevF(e.target.value)}>
          <option value="">매출 전체</option>
          <option value="100">{manH}만+</option>
          <option value="50">
            {manM}~{manH}만
          </option>
          <option value="lo">{manM}만 미만</option>
        </select>
        <select value={recF} onChange={(e) => setRecF(e.target.value)}>
          <option value="">방문시기 전체</option>
          <option value="1m">1개월 이내</option>
          <option value="3m">3개월 이내</option>
          <option value="6m">6개월 이내</option>
          <option value="1y">1년+ 미방문</option>
        </select>
        <select value={svcF} onChange={(e) => setSvcF(e.target.value)}>
          <option value="">시술 전체</option>
          <option value="펌">펌</option>
          <option value="염색">염색</option>
          <option value="클리닉">클리닉</option>
          <option value="컷">컷</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="recent">최근 방문순</option>
          <option value="revenue">매출순</option>
          <option value="visits">방문순</option>
          <option value="avg">객단가순</option>
          <option value="new">신규 유입순</option>
          <option value="name">이름순</option>
        </select>
      </div>

      <div className="sec-h">{filtered.length}명</div>
      <div className="card">
        {filtered.length ? (
          filtered.map((r) => (
            <Link key={r.id} href={`/customer/${r.id}`} className="li li-link">
              <div className="av">{r.name.charAt(0)}</div>
              <div className="bd">
                <div className="nm">
                  {r.name} 님{vip(r) ? <span className="tag-vip">VIP</span> : null}
                  {r.churned ? <span className="tag-off">이탈</span> : null}
                </div>
                <div className="sub">
                  {r.visit_count}회 · {won(r.total_won)}원{r.last_visit ? ' · 마지막 ' + r.last_visit : ''}
                </div>
              </div>
              <div className="rt">
                {/* 이탈로 확정한 고객에게 '이탈 위험'(=아직 붙잡을 수 있다) 추정을 띄우지 않는다 */}
                {r.churned ? '' : r.state === 'overdue' ? '이탈 위험' : r.state === 'due' ? '재방문 도래' : r.hasBooking ? '예약 있음' : ''}
              </div>
            </Link>
          ))
        ) : (
          <div className="empty">조건에 맞는 고객이 없어요</div>
        )}
      </div>
    </>
  );
}
