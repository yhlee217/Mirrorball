'use client';
import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { isVip, isLapsed, type TenantSettings } from '@/lib/settings';

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
      <input type="number" value={v} onChange={(e) => set(n(e.target.value))} style={w ? { width: w } : undefined} />
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
        setMsg('저장됐어요 ✓');
        router.refresh();
      } else setMsg('저장 실패');
    } catch {
      setMsg('저장 실패');
    }
    setSaving(false);
  };

  const copyUrl = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/p/${slug}`);
      setMsg('공개 소개 링크 복사됨 ✓');
    } catch {
      setMsg('복사 실패');
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
        <div className="ch" style={{ padding: 0, marginBottom: 3 }}>VIP 기준</div>
        <div className="crit-sub">아래 하나만 넘어도 VIP예요</div>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">누적매출</div>
            <Num v={vipWon} set={setVipWon} unit="만원" />
          </div>
          <div className="crit-hint">많이 쓰신 분</div>
        </div>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">누적방문</div>
            <Num v={vipVisits} set={setVipVisits} unit="회" />
          </div>
          <div className="crit-hint">오래 다니신 분</div>
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
          <div className="crit-hint">요즘 자주 오시는 분 · 0으로 두면 이 기준은 안 써요</div>
        </div>

        <div className="crit-sum">
          지금 VIP <b>{counts.vip}</b>명
          <span className="dim">· 관리 대상 {counts.total}명 중 {counts.vipPct}%</span>
        </div>
      </div>

      <div className="card" style={{ padding: '14px 15px' }}>
        <div className="ch" style={{ padding: 0, marginBottom: 3 }}>이탈 기준</div>
        <div className="crit-sub">여기 걸리면 챙길 고객·홈 신호에서 빠져요</div>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">이 기간 넘게 안 오시면</div>
            <Num v={lapsedM} set={setLapsedM} unit="개월" />
          </div>
          <div className="crit-hint">방문 횟수와 상관없이 제외</div>
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
          <div className="crit-hint">몇 번 오다 마신 분은 더 일찍 제외</div>
        </div>

        <div className="crit-sum">
          지금 <b>{counts.lapsed}</b>명 제외
          <span className="dim">· 남는 관리 대상 {counts.total - counts.lapsed}명</span>
        </div>
      </div>

      <div className="card" style={{ padding: '14px 15px' }}>
        <div className="ch" style={{ padding: 0, marginBottom: 3 }}>표시 설정</div>
        <div className="crit-sub">판정과 무관하게 화면에만 영향을 줘요</div>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">매출 구간 · 중</div>
            <Num v={revMid} set={setRevMid} unit="만원" />
          </div>
          <div className="crit-top" style={{ marginTop: 7 }}>
            <div className="crit-nm">매출 구간 · 상</div>
            <Num v={revHigh} set={setRevHigh} unit="만원" />
          </div>
          <div className="crit-hint">고객 목록 매출 필터의 경계</div>
        </div>

        <div className="crit">
          <div className="crit-top">
            <div className="crit-nm">다가오는 예약</div>
            <Num v={bDays} set={setBDays} unit="일 앞까지" w={54} />
          </div>
          <div className="crit-hint">홈에 며칠 앞 예약까지 보여줄지</div>
        </div>
      </div>

      <button className="primary" style={{ width: '100%', maxWidth: 'none', marginTop: 0 }} onClick={save} disabled={saving}>
        {saving ? '저장 중…' : '저장'}
      </button>
      {msg ? <div className="set-msg">{msg}</div> : null}
    </>
  );
}
