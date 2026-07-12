'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import type { TenantSettings } from '@/lib/settings';

export default function SettingsForm({
  initSettings,
  designer,
  salon,
  slug,
}: {
  initSettings: TenantSettings;
  designer: string;
  salon: string;
  slug: string;
}) {
  const router = useRouter();
  const [dn, setDn] = useState(designer);
  const [sn, setSn] = useState(salon);
  const [vipWon, setVipWon] = useState(Math.round(initSettings.vip_won / 10000));
  const [vipVisits, setVipVisits] = useState(initSettings.vip_visits);
  const [lapsedM, setLapsedM] = useState(initSettings.lapsed_months);
  const [softM, setSoftM] = useState(initSettings.lapsed_soft_months);
  const [softV, setSoftV] = useState(initSettings.lapsed_soft_visits);
  const [revMid, setRevMid] = useState(Math.round(initSettings.revenue_mid / 10000));
  const [revHigh, setRevHigh] = useState(Math.round(initSettings.revenue_high / 10000));
  const [bDays, setBDays] = useState(initSettings.booking_days_ahead);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const n = (v: string) => Math.max(0, Math.floor(Number(v) || 0));

  const save = async () => {
    setSaving(true);
    setMsg('');
    const settings: TenantSettings = {
      vip_won: vipWon * 10000,
      vip_visits: vipVisits,
      lapsed_months: lapsedM,
      lapsed_soft_months: softM,
      lapsed_soft_visits: softV,
      revenue_mid: revMid * 10000,
      revenue_high: revHigh * 10000,
      booking_days_ahead: bDays,
    };
    try {
      const r = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings, designer_name: dn, salon_name: sn }),
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
        <div className="ch" style={{ padding: 0, marginBottom: 10 }}>판정 기준</div>

        <div className="set-lbl">VIP 기준</div>
        <div className="set-row">
          누적매출 <input type="number" value={vipWon} onChange={(e) => setVipWon(n(e.target.value))} /> 만원 이상
        </div>
        <div className="set-row">
          또는 방문 <input type="number" value={vipVisits} onChange={(e) => setVipVisits(n(e.target.value))} /> 회 이상
        </div>

        <div className="set-lbl">이탈 고객 (홈 · 챙길 고객에서 제외)</div>
        <div className="set-row">
          <input type="number" value={lapsedM} onChange={(e) => setLapsedM(n(e.target.value))} /> 개월 초과 미방문
        </div>
        <div className="set-row">
          또는 <input type="number" value={softM} onChange={(e) => setSoftM(n(e.target.value))} /> 개월 초과 · 방문{' '}
          <input type="number" value={softV} onChange={(e) => setSoftV(n(e.target.value))} /> 회 미만
        </div>

        <div className="set-lbl">매출 구간 (필터)</div>
        <div className="set-row">
          중 <input type="number" value={revMid} onChange={(e) => setRevMid(n(e.target.value))} /> 만원 · 상{' '}
          <input type="number" value={revHigh} onChange={(e) => setRevHigh(n(e.target.value))} /> 만원
        </div>

        <div className="set-lbl">다가오는 예약 표시</div>
        <div className="set-row">
          <input type="number" value={bDays} onChange={(e) => setBDays(n(e.target.value))} /> 일 앞까지
        </div>

        <button className="primary" style={{ width: '100%', marginTop: 14 }} onClick={save} disabled={saving}>
          {saving ? '저장 중…' : '저장'}
        </button>
        {msg ? <div className="set-msg">{msg}</div> : null}
      </div>
    </>
  );
}
