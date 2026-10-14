'use client';
import { useEffect, useMemo, useState } from 'react';
import { man } from '@/lib/format';
import { agoWords, daysBetween } from '@/lib/week';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { decodeList, encodeList, replaceQuery, FOLDED } from '@/lib/list-state';
import { isVip as isVipS, type TenantSettings } from '@/lib/settings';
import { needsCare, prepaidAway, PREPAID_AWAY_DAYS } from '@/lib/customers';
import { matchesQuery } from '@/lib/contact';
import { Empty } from '@/components/empty';
import { Help } from '@/components/help';
import { MSG } from '@/lib/copy';

type Row = {
  id: string;
  name: string;
  visit_count: number;
  total_won: number;
  last_visit: string | null;
  first_visit: string | null;
  state: string | null; // 휴가를 반영한 재방문 상태(서버에서 careState)
  cycle: number | null; // 평소 방문 주기(일)
  hasBooking: boolean;
  held: boolean; // 챙길 고객에서 뺄 분 — 앞으로 올 예약 + 수집 뒤 예약 시각이 지난 분(lib/bookings bookingSets)
  hasPhone: boolean;
  tail: string; // 전화번호 뒷자리 4자리(검색용) — 전체 번호는 받지 않는다
  churned: boolean;
  gender: 'M' | 'F' | null;
  visits_90d: number | null; // VIP 판정(최근 자주 오심)용 — 워커가 미리 집계
  visits_180d: number | null;
  visits_365d: number | null;
  prepaid_balance: number; // 선불 잔액(추정)
};


export default function CustomersList({
  rows,
  settings,
  asOf,
  today,
}: {
  rows: Row[];
  settings: TenantSettings;
  asOf: string; // 재방문 판정의 기준일(마지막 수집일)
  today: string; // KST — '3주 전'과 방문시기 필터의 기준
}) {
  const daysSince = (d: string | null) => (d ? daysBetween(d, today) : Infinity);
  // 검색·조건·정렬은 주소에서 시작하고 주소에 남긴다(lib/list-state) — 카르테를 보고 돌아와도 그대로.
  // 홈·통계 링크의 ?filter=overdue 같은 조건도 여기서 켜지고, 접힌 조건이면 '필터'를 펼친 채로 연다.
  const sp = useSearchParams();
  const [init] = useState(() => decodeList((k) => sp.get(k)));
  const [q, setQ] = useState(init.q);
  const [chips, setChips] = useState<Set<string>>(() => new Set(init.chips));
  const [more, setMore] = useState(init.more);
  const [visitF, setVisitF] = useState(init.visit);
  const [revF, setRevF] = useState(init.rev);
  const [recF, setRecF] = useState(init.rec);
  const [svcF, setSvcF] = useState(init.svc);
  const [sort, setSort] = useState(init.sort);
  useEffect(() => {
    replaceQuery(encodeList({ q, chips: [...chips], more, visit: visitF, rev: revF, rec: recF, svc: svcF, sort }));
  }, [q, chips, more, visitF, revF, recF, svcF, sort]);
  // 방금 지정한 것들. 저장하자마자 목록에서 빼면 '내가 뭘 눌렀는지'가 사라져 흐름이 끊긴다.
  // 화면에 남겨 두고 표시만 바꾼다(다음 진입 때 필터가 자연히 걸러낸다).
  const [picked, setPicked] = useState<Record<string, 'M' | 'F'>>({});
  const [saving, setSaving] = useState<string | null>(null);
  // 손님별 시술 갈래 — '시술' 필터를 처음 고를 때 받는다(목록을 열 때마다 거래 전체를 받지 않게).
  const [svcMap, setSvcMap] = useState<Record<string, string[]> | null>(null);
  const [svcErr, setSvcErr] = useState(false);
  useEffect(() => {
    if (!svcF || svcMap || svcErr) return;
    let live = true;
    fetch('/api/customer-services')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((m: Record<string, string[]>) => live && setSvcMap(m))
      .catch(() => live && setSvcErr(true));
    return () => {
      live = false;
    };
  }, [svcF, svcMap, svcErr]);
  const svcWaiting = !!svcF && !svcMap;

  const pickGender = async (id: string, g: 'M' | 'F') => {
    if (saving) return;
    setSaving(id);
    setPicked((p) => ({ ...p, [id]: g }));
    try {
      const r = await fetch('/api/customer-gender', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: id, gender: g }),
      });
      if (!r.ok) throw new Error();
    } catch {
      setPicked((p) => {
        const n = { ...p };
        delete n[id];
        return n;
      });
      alert(MSG.saveFail);
    } finally {
      setSaving(null);
    }
  };

  // 검색·칩·셀렉트 중 하나라도 걸려 있으면 '0명'은 데이터가 없는 게 아니라 걸러진 것이다.
  // 정렬(sort)은 목록을 줄이지 않으므로 세지 않는다.
  const narrowed = !!q.trim() || chips.size > 0 || !!visitF || !!revF || !!recF || !!svcF;
  const clearFilters = () => {
    setQ('');
    setChips(new Set());
    setVisitF('');
    setRevF('');
    setRecF('');
    setSvcF('');
  };

  const sweeping = chips.has('nogender'); // 성별 채우는 중인가
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
    if (term) f = f.filter((r) => matchesQuery(r, term)); // 숫자면 전화번호 뒷자리, 아니면 이름
    // 이탈위험·재방문도래는 홈 신호와 같은 기준으로 — '이탈 판정'(설정: N개월 초과 미방문 등)
    // 고객과 디자이너가 직접 이탈 표시한 고객은 홈 숫자에서 빠지므로 여기서도 빼야
    // '눌렀더니 인원이 다른' 불일치가 안 생긴다.
    // needsCare 는 이미 예약한 분도 뺀다 — 예약이 잡혔으면 더 챙길 대상이 아니다. 수집 뒤 예약 시각이
    // 지난 분(다녀가셨을 분)도 다음 수집까지는 뺀다 — 홈 숫자와 같아야 한다.
    const care = (r: Row) => needsCare(
      { revisit_state: r.state, last_visit: r.last_visit, visit_count: r.visit_count, revisit_cycle_days: r.cycle },
      { settings, churned: r.churned, booked: r.held, asOf },
    );
    if (chips.has('overdue')) f = f.filter((r) => r.state === 'overdue' && care(r));
    if (chips.has('due')) f = f.filter((r) => r.state === 'due' && care(r));
    if (chips.has('new')) f = f.filter((r) => r.state === 'new' && !r.churned);
    if (chips.has('vip')) f = f.filter((r) => isVipS(r, settings) && !r.churned);
    if (chips.has('churned')) f = f.filter((r) => r.churned);
    // 성별 미상만 모아 한 번에 채우기 위한 필터. 이 칩이 켜져 있을 때만 각 줄에
    // 지정 버튼이 나타난다 — 평소에도 달아두면 목록이 지저분해진다.
    if (chips.has('nogender')) f = f.filter((r) => !r.gender && !picked[r.id]);
    if (chips.has('booking')) f = f.filter((r) => r.hasBooking);
    if (chips.has('nophone')) f = f.filter((r) => !r.hasPhone);
    // 선불 잔액을 남긴 채 3개월 넘게 안 오신 분 — 통계 알약과 같은 기준(lib/customers prepaidAway)
    if (chips.has('prepaid')) f = f.filter((r) => prepaidAway({ ...r, churned_at: r.churned ? 'y' : null }, today));
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
    if (svcF) f = svcMap ? f.filter((r) => svcMap[r.id]?.includes(svcF)) : [];

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
  }, [rows, q, chips, visitF, revF, recF, svcF, svcMap, sort, settings, asOf, today]);

  // 접힌 조건 중 켜진 수 — 손잡이에 보여야 '왜 목록이 줄었지'가 안 생긴다.
  const hiddenOn = FOLDED.filter((k) => chips.has(k)).length + [visitF, revF, recF, svcF].filter(Boolean).length;

  const Chip = ({ k, label }: { k: string; label: string }) => (
    <button type="button" className={'fchip' + (chips.has(k) ? ' on' : '')} onClick={() => toggle(k)}>
      {label}
    </button>
  );

  return (
    <>
      {/* 찾기·정렬 한 줄, 조건 한 줄 — 손잡이가 세 줄이던 것을 두 줄로(첫 화면에 손님 10명) */}
      <div className="sbar">
        <input className="search" type="search" enterKeyHint="search" placeholder="이름 · 전화 뒷자리" aria-label="이름 또는 전화번호 뒷자리로 찾기"
          value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }} />
        <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="정렬">
          <option value="recent">최근 방문순</option>
          <option value="revenue">매출순</option>
          <option value="visits">방문순</option>
          <option value="avg">객단가순</option>
          <option value="new">신규 유입순</option>
          <option value="name">이름순</option>
        </select>
      </div>

      {/* 늘 보이는 건 자주 쓰는 넷. 나머지 조건 13개 중 9개는 '필터' 안에 접는다 — 폰 화면 절반이 필터였다. */}
      <div className="fchips">
        <Chip k="overdue" label="이탈 위험" />
        <Chip k="due" label="재방문 도래" />
        <Chip k="new" label="신규" />
        <Chip k="vip" label="VIP" />
        <button type="button" className={'fchip' + (hiddenOn ? ' on' : '')} aria-expanded={more} onClick={() => setMore((m) => !m)}>
          필터{hiddenOn ? ` ${hiddenOn}` : ''} {more ? '▴' : '▾'}
        </button>
      </div>

      {more ? (
        <div className="fmore">
          <div className="fchips">
            <Chip k="booking" label="예약있음" />
            <Chip k="nophone" label="전화없음" />
            <Chip k="churned" label="이탈" />
            <Chip k="nogender" label="성별 미상" />
            <Chip k="prepaid" label={`선불 ${PREPAID_AWAY_DAYS / 30}개월+`} />
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
          </div>
        </div>
      ) : null}

      {/* 거른 수는 걸렀을 때만 — 안 걸렀으면 위 제목의 '고객 N명'과 같은 숫자다 */}
      {narrowed ? (
        <div className="sect-h list-n">
          {filtered.length.toLocaleString()}명{sweeping ? ' 남음' : ''}
          {sweeping ? (
            <Help inline>
              시술명으로 성별을 알 수 없는 분들이에요. 아는 분만 눌러 채우면 통계에 바로 반영돼요.
              방문순으로 정렬하면 자주 오시는 분부터 나와요.
            </Help>
          ) : null}
        </div>
      ) : null}
      <div className="card">
        {filtered.length ? (
          filtered.map((r) => {
            const row = (
              <Link href={`/customer/${r.id}`} className="li li-link">
                <div className="av">{r.name.charAt(0)}</div>
                <div className="bd">
                  <div className="nm">
                    {r.name}
                    {vip(r) ? <span className="tag-vip">VIP</span> : null}
                    {r.churned ? <span className="tag-off">이탈</span> : null}
                    {r.prepaid_balance > 0 ? <span className="ppd">선불 {man(r.prepaid_balance)}</span> : null}
                  </div>
                  <div className="sub">
                    {r.visit_count}회 · {man(r.total_won)}
                    {r.last_visit ? ' · ' + agoWords(daysBetween(r.last_visit, today)) : ''}
                  </div>
                </div>
                <StateTag r={r} />
              </Link>
            );
            // 성별 채우는 중이 아니면 평소 목록 그대로 — 버튼을 늘 달아두면 지저분해진다.
            if (!sweeping) return <div key={r.id}>{row}</div>;
            const done = picked[r.id];
            return (
              <div key={r.id} className={'gsweep' + (done ? ' done' : '')}>
                {row}
                {/* 링크 밖에 둬야 눌렀을 때 카르테로 넘어가지 않는다 */}
                <div className="gsweep-b">
                  {done ? (
                    <span className="gs-ok">{done === 'M' ? '남성' : '여성'}으로 저장됨</span>
                  ) : (
                    <>
                      <button type="button" className="gs" disabled={saving === r.id}
                        onClick={() => pickGender(r.id, 'M')}>남성</button>
                      <button type="button" className="gs" disabled={saving === r.id}
                        onClick={() => pickGender(r.id, 'F')}>여성</button>
                    </>
                  )}
                </div>
              </div>
            );
          })
        ) : svcWaiting ? (
          svcErr ? (
            <Empty
              title="시술 기록을 불러오지 못했어요"
              action={<button type="button" onClick={() => setSvcErr(false)}>다시 시도</button>}
            />
          ) : (
            <Empty title="시술 기록 불러오는 중…" />
          )
        ) : sweeping ? (
          // 훑기를 끝낸 자리 — '없다'가 아니라 '다 채웠다'는 뜻이라 문구가 달라야 한다.
          <Empty
            title="성별 미상 고객을 다 채웠어요"
            action={<Link href="/stats">통계 보기 ›</Link>}
          />
        ) : narrowed ? (
          <Empty
            title="조건에 맞는 고객 없음"
            action={<button type="button" onClick={clearFilters}>필터 지우기</button>}
          />
        ) : (
          <Empty title="아직 고객이 없어요" hint="첫 수집이 끝나면 채워져요." />
        )}
      </div>
    </>
  );
}

/**
 * 줄 오른쪽 상태 뱃지 — 지금의 사실 하나만. 이탈로 확정한 분에게 '이탈 위험'(아직 붙잡을 수 있다)을
 * 띄우지 않고, 예약이 잡혔으면 '이탈 위험'보다 '예약 있음'이 지금의 사실이다.
 */
function StateTag({ r }: { r: Row }) {
  if (r.churned) return null;
  if (r.hasBooking) return <span className="ctag booked">예약 있음</span>;
  // 수집 뒤 예약 시각이 지난 분 — 다녀가셨는지는 다음 수집에 잡힌다. '이탈 위험'을 띄우지 않는다
  if (r.held) return <span className="ctag held">지난 예약</span>;
  if (r.state === 'overdue') return <span className="ctag overdue">이탈 위험</span>;
  if (r.state === 'due') return <span className="ctag due">재방문 도래</span>;
  return null;
}
