'use client';
import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { MSG } from '@/lib/copy';
import { Help } from '@/components/help';
import { isVip, isLapsed, cleanOffDates, type ContactButton, type TenantSettings } from '@/lib/settings';
import { dayLabel } from '@/lib/week';

const WEEK = ['월', '화', '수', '목', '금', '토', '일']; // 월=0 — lib/week dowMon 과 같은 번호

// 판정 기준은 숫자만 보면 감이 안 온다("20회가 적당한가?"의 근거는 사실 인원수다).
// 그래서 값을 바꾸는 즉시 '지금 몇 명이 되는지' 다시 세어 보여준다. 판정은 화면에서 다시
// 구현하지 않고 lib/settings 의 isVip·isLapsed 를 그대로 써서 실제 판정과 어긋날 수 없게 했다.
type Stat = [number, number, number, number, number, string | null]; // 매출·방문·90·180·365·마지막방문

const n = (v: string) => Math.max(0, Math.floor(Number(v) || 0));

// 반드시 모듈 스코프에 — 컴포넌트 안에서 정의하면 렌더마다 새 타입이 돼 input 이 remount 되고
// 한 글자 칠 때마다 포커스가 날아간다.
function Num({ v, set, unit, w }: { v: number; set: (x: number) => void; unit: string; w?: number }) {
  return (
    <div className="crit-in">
      {/* 숫자 패드로(type=number 는 아이폰에서 기호 키보드가 뜬다) */}
      <input type="text" inputMode="numeric" pattern="[0-9]*" enterKeyHint="done" value={v}
        onChange={(e) => set(n(e.target.value))} style={w ? { width: w } : undefined} />
      <span className="u">{unit}</span>
    </div>
  );
}

export default function SettingsForm({
  initSettings,
  designer,
  salon,
  slug,
  stats,
}: {
  initSettings: TenantSettings;
  designer: string;
  salon: string;
  slug: string;
  stats: Stat[];
}) {
  const router = useRouter();
  const [dn, setDn] = useState(designer);
  const [sn, setSn] = useState(salon);
  const [vipWon, setVipWon] = useState(Math.round(initSettings.vip_won / 10000));
  const [vipVisits, setVipVisits] = useState(initSettings.vip_visits);
  const [vipRecM, setVipRecM] = useState(initSettings.vip_recent_months);
  const [vipRecV, setVipRecV] = useState(initSettings.vip_recent_visits);
  const [lapsedM, setLapsedM] = useState(initSettings.lapsed_months);
  const [softM, setSoftM] = useState(initSettings.lapsed_soft_months);
  const [softV, setSoftV] = useState(initSettings.lapsed_soft_visits);
  const [revMid, setRevMid] = useState(Math.round(initSettings.revenue_mid / 10000));
  const [revHigh, setRevHigh] = useState(Math.round(initSettings.revenue_high / 10000));
  const [bDays, setBDays] = useState(initSettings.booking_days_ahead);
  // 휴무 — 통계가 영업한 날끼리 견주게(lib/offdays). 정기 휴무 요일 + 휴가 기간.
  const [offW, setOffW] = useState<number[]>(initSettings.off_weekdays);
  const [offD, setOffD] = useState(initSettings.off_dates);
  // 챙길 고객 줄의 큰 버튼 — 문자 · 카톡 등(폰의 공유 창), 개선 계획 v11 P1
  const [cBtn, setCBtn] = useState<ContactButton>(initSettings.contact_button);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const draft: TenantSettings = {
    vip_won: vipWon * 10000,
    vip_visits: vipVisits,
    vip_recent_months: vipRecM,
    vip_recent_visits: vipRecV,
    lapsed_months: lapsedM,
    lapsed_soft_months: softM,
    lapsed_soft_visits: softV,
    revenue_mid: revMid * 10000,
    revenue_high: revHigh * 10000,
    booking_days_ahead: bDays,
    off_weekdays: offW,
    off_dates: offD,
    contact_button: cBtn,
  };
  // 휴무는 고르자마자 저장되는 게 아니라 아래 '저장'으로 함께 저장된다 — 잊지 않게 바뀌면 알린다.
  const offDirty =
    JSON.stringify([offW, offD]) !== JSON.stringify([initSettings.off_weekdays, initSettings.off_dates]);
  const toggleW = (d: number) => setOffW((w) => (w.includes(d) ? w.filter((x) => x !== d) : [...w, d].sort((a, b) => a - b)));
  // 겹치거나 맞닿은 기간은 저장할 때처럼 바로 합친다(lib/settings cleanOffDates) — 목록이 서버와 같게.
  const addRange = () => {
    if (!from) return;
    setOffD((d) => cleanOffDates([...d, { from, to: to || from }]));
    setFrom('');
    setTo('');
  };
  const rangeLabel = (r: { from: string; to: string }) => {
    if (r.from === r.to) return dayLabel(r.from);
    const n = Math.round((Date.parse(r.to) - Date.parse(r.from)) / 86400000) + 1;
    return `${dayLabel(r.from)} ~ ${dayLabel(r.to)} · ${n}일`;
  };

  const counts = useMemo(() => {
    let vip = 0;
    let lapsed = 0;
    for (const c of stats) {
      const row = { total_won: c[0], visit_count: c[1], visits_90d: c[2], visits_180d: c[3], visits_365d: c[4] };
      if (isVip(row, draft)) vip++;
      if (isLapsed({ last_visit: c[5], visit_count: c[1] }, draft)) lapsed++;
    }
    const total = stats.length;
    return { vip, lapsed, total, vipPct: total ? Math.round((vip / total) * 100) : 0 };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stats, vipWon, vipVisits, vipRecM, vipRecV, lapsedM, softM, softV]);

  const save = async () => {
    setSaving(true);
    setMsg('');
    try {
      const r = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings: draft, designer_name: dn, salon_name: sn }),
      });
      if (r.ok) {
        setMsg(MSG.saved);
        router.refresh();
      } else setMsg(MSG.saveFailShort);
    } catch {
      setMsg(MSG.saveFailShort);
    }
    setSaving(false);
  };

  const copyUrl = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/p/${slug}`);
      setMsg('공개 소개 링크 복사됨 ✓');
    } catch {
      setMsg(MSG.copyFail);
    }
  };

  return (
    <>
      <div className="card" style={{ padding: '14px 15px' }}>
        <div className="ch" style={{ padding: 0, marginBottom: 10 }}>매장 · 프로필</div>
        <div className="fld">
          <label>디자이너 이름</label>
          <input value={dn} onChange={(e) => setDn(e.target.value)} placeholder="예: 하예원" />
        </div>
        <div className="fld">
          <label>살롱 이름</label>
          <input value={sn} onChange={(e) => setSn(e.target.value)} placeholder="예: 살롱톤" />
        </div>
        <div className="row2">
          <a className="btn ghost" href="/profile">소개 편집</a>
          <button type="button" className="btn ghost" onClick={copyUrl}>공개 링크 복사</button>
        </div>
      </div>

      <div className="card" style={{ padding: '14px 15px' }}>
        <div className="ch" style={{ padding: 0, marginBottom: 3 }}>연락 버튼</div>
        <Help>
          챙길 고객 줄의 큰 버튼이에요. 손님께 주로 문자를 보내시면 &lsquo;문자&rsquo;, 카카오톡으로 보내시면 &lsquo;카톡 등&rsquo;
          — 폰의 공유 창이 문구가 채워진 채 열려요. 다른 쪽은 줄을 펼치면 있어요. 보내기를 마치면 &lsquo;연락함&rsquo;으로 남아요.
        </Help>
        <div className="seg" role="group" aria-label="연락 버튼">
          {([['sms', '💬 문자'], ['share', '📤 카톡 등']] as const).map(([v, label]) => (
            <button
              key={v}
              type="button"
              className={cBtn === v ? 'on' : undefined}
              aria-pressed={cBtn === v}
              onClick={() => setCBtn(v)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="card" style={{ padding: '14px 15px' }}>
        <div className="ch" style={{ padding: 0, marginBottom: 3 }}>휴무</div>
        <Help>
          쉬는 날을 알려주시면 통계가 영업한 날끼리 견주고, 챙길 고객도 휴가만큼 늦춰서 셈해요. 정기 휴무 요일이라도
          그날 일한 기록이 있으면 영업한 날로 셉니다. 휴가가 하루뿐이면 마지막 날은 비워 두세요.
        </Help>

        <div className="crit">
          <div className="crit-nm" style={{ marginBottom: 8 }}>정기 휴무</div>
          <div className="fchips" style={{ margin: 0 }}>
            {WEEK.map((d, i) => (
              <button
                key={d}
                type="button"
                className={'fchip' + (offW.includes(i) ? ' on' : '')}
                aria-pressed={offW.includes(i)}
                onClick={() => toggleW(i)}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        <div className="crit">
          <div className="crit-nm" style={{ marginBottom: 6 }}>휴가 · 임시 휴무</div>
          {offD.length ? (
            [...offD].reverse().map((r) => (
              <div className="off-r" key={r.from}>
                <span>{rangeLabel(r)}</span>
                <button type="button" className="off-x" onClick={() => setOffD((d) => d.filter((x) => x !== r))}>
                  삭제
                </button>
              </div>
            ))
          ) : (
            <div className="crit-hint" style={{ marginTop: 0 }}>등록된 휴가 없음</div>
          )}
          <div className="off-add">
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="쉬는 첫날" />
            <span>~</span>
            <input type="date" value={to} min={from || undefined} onChange={(e) => setTo(e.target.value)} aria-label="쉬는 마지막 날" />
          </div>
          <button type="button" className="btn ghost" style={{ marginTop: 8, width: '100%' }} onClick={addRange} disabled={!from}>
            기간 추가
          </button>
        </div>
        {offDirty ? <div className="off-dirty">화면 아래 &lsquo;저장&rsquo;을 눌러야 반영돼요</div> : null}
      </div>

      <div className="card" style={{ padding: '14px 15px' }}>
        <div className="ch" style={{ padding: 0, marginBottom: 3 }}>VIP 기준</div>
        <Help>
          아래 하나만 넘어도 VIP예요 — 누적매출은 많이 쓰신 분, 누적방문은 오래 다니신 분, &lsquo;최근&rsquo;은 요즘 자주
          오시는 분이에요. 횟수를 0으로 두면 그 기준은 쓰지 않아요.
        </Help>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">누적매출</div>
            <Num v={vipWon} set={setVipWon} unit="만원" />
          </div>
        </div>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">누적방문</div>
            <Num v={vipVisits} set={setVipVisits} unit="회" />
          </div>
        </div>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">
              최근
              <select value={vipRecM} onChange={(e) => setVipRecM(Number(e.target.value))}>
                <option value={3}>3개월</option>
                <option value={6}>6개월</option>
                <option value={12}>12개월</option>
              </select>
            </div>
            <Num v={vipRecV} set={setVipRecV} unit="회" />
          </div>
        </div>

        <div className="crit-sum">
          지금 VIP <b>{counts.vip}</b>명
          <span className="dim">· 관리 대상 {counts.total}명 중 {counts.vipPct}%</span>
        </div>
      </div>

      <div className="card" style={{ padding: '14px 15px' }}>
        <div className="ch" style={{ padding: 0, marginBottom: 3 }}>이탈 기준</div>
        <Help>
          여기 걸리면 챙길 고객·홈 신호에서 빠져요. 첫 줄은 방문 횟수와 상관없이, 둘째 줄은 몇 번 오다 마신 분을 더 일찍
          빼는 기준이에요.
        </Help>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">이 기간 넘게 안 오시면</div>
            <Num v={lapsedM} set={setLapsedM} unit="개월" />
          </div>
        </div>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">또는 이 기간 넘게</div>
            <Num v={softM} set={setSoftM} unit="개월" />
          </div>
          <div className="crit-top" style={{ marginTop: 7 }}>
            <div className="crit-nm">안 오시고 방문이</div>
            <Num v={softV} set={setSoftV} unit="회 미만" w={54} />
          </div>
        </div>

        <div className="crit-sum">
          지금 <b>{counts.lapsed}</b>명 제외
          <span className="dim">· 남는 관리 대상 {counts.total - counts.lapsed}명</span>
        </div>
      </div>

      <div className="card" style={{ padding: '14px 15px' }}>
        <div className="ch" style={{ padding: 0, marginBottom: 3 }}>표시 설정</div>
        <Help>
          판정과 상관없이 화면에만 영향을 줘요. 매출 구간은 고객 목록 매출 필터의 경계, 다가오는 예약은 홈에 며칠 앞
          예약까지 보여줄지예요.
        </Help>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">매출 구간 · 중</div>
            <Num v={revMid} set={setRevMid} unit="만원" />
          </div>
          <div className="crit-top" style={{ marginTop: 7 }}>
            <div className="crit-nm">매출 구간 · 상</div>
            <Num v={revHigh} set={setRevHigh} unit="만원" />
          </div>
        </div>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">다가오는 예약</div>
            <Num v={bDays} set={setBDays} unit="일 앞까지" w={54} />
          </div>
        </div>
      </div>

      {/* 저장은 화면 아래(탭바 위)에 붙어 있다 — 긴 양식 끝까지 내려가지 않아도 된다(모바일 개선 M4) */}
      <div className="savebar">
        <button className="primary" style={{ width: '100%', maxWidth: 'none', marginTop: 0 }} onClick={save} disabled={saving}>
          {saving ? '저장 중…' : '저장'}
        </button>
        {msg ? <div className="set-msg">{msg}</div> : null}
      </div>
    </>
  );
}
