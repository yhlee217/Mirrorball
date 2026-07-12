'use client';
import { useState } from 'react';

type Spec = { name: string; desc: string };
type Faq = { q: string; a: string };
type P = { tagline: string; bio: string; location: string; services: Spec[]; faq: Faq[] };

export default function ProfileEdit({ initial }: { initial: P }) {
  const [p, setP] = useState<P>(initial);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const field = (k: 'tagline' | 'bio' | 'location', v: string) => setP((s) => ({ ...s, [k]: v }));
  const spec = (i: number, k: keyof Spec, v: string) =>
    setP((s) => ({ ...s, services: s.services.map((x, j) => (j === i ? { ...x, [k]: v } : x)) }));
  const faq = (i: number, k: keyof Faq, v: string) =>
    setP((s) => ({ ...s, faq: s.faq.map((x, j) => (j === i ? { ...x, [k]: v } : x)) }));

  async function save() {
    setSaving(true);
    setMsg('');
    let ok = false;
    try {
      const res = await fetch('/api/profile', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(p),
      });
      ok = res.ok;
    } catch {
      ok = false;
    }
    setSaving(false);
    setMsg(ok ? '저장됐어요' : '저장 실패');
    setTimeout(() => setMsg(''), 2200);
  }

  return (
    <>
      <div className="fld">
        <label>한 줄 소개</label>
        <input value={p.tagline} onChange={(e) => field('tagline', e.target.value)} />
      </div>
      <div className="fld">
        <label>소개</label>
        <textarea rows={5} value={p.bio} onChange={(e) => field('bio', e.target.value)} />
      </div>
      <div className="fld">
        <label>위치</label>
        <input value={p.location} onChange={(e) => field('location', e.target.value)} />
      </div>

      <div className="sec-h">시술 설명</div>
      {p.services.map((s, i) => (
        <div className="card" style={{ padding: '12px 13px', marginBottom: 8 }} key={i}>
          <input placeholder="시술명" value={s.name} onChange={(e) => spec(i, 'name', e.target.value)} />
          <textarea rows={2} placeholder="설명" value={s.desc} onChange={(e) => spec(i, 'desc', e.target.value)} />
          <button className="del" onClick={() => setP((st) => ({ ...st, services: st.services.filter((_, j) => j !== i) }))}>
            삭제
          </button>
        </div>
      ))}
      <button className="btn ghost" onClick={() => setP((s) => ({ ...s, services: [...s.services, { name: '', desc: '' }] }))}>
        + 시술 추가
      </button>

      <div className="sec-h" style={{ marginTop: 16 }}>자주 묻는 질문</div>
      {p.faq.map((f, i) => (
        <div className="card" style={{ padding: '12px 13px', marginBottom: 8 }} key={i}>
          <input placeholder="질문" value={f.q} onChange={(e) => faq(i, 'q', e.target.value)} />
          <textarea rows={2} placeholder="답변" value={f.a} onChange={(e) => faq(i, 'a', e.target.value)} />
          <button className="del" onClick={() => setP((st) => ({ ...st, faq: st.faq.filter((_, j) => j !== i) }))}>
            삭제
          </button>
        </div>
      ))}
      <button className="btn ghost" onClick={() => setP((s) => ({ ...s, faq: [...s.faq, { q: '', a: '' }] }))}>
        + 질문 추가
      </button>

      <div style={{ marginTop: 18 }}>
        <button className="btn" onClick={save} disabled={saving}>
          {saving ? '저장 중…' : '저장'}
        </button>
      </div>
      {msg && <div className="toast">{msg}</div>}
    </>
  );
}
