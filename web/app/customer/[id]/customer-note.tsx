'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

const PRESETS = ['펌', '염색', '클리닉', '컷', '내추럴', '볼륨', '민감두피', '탈색모', '곱슬', '숱많음', '두피예민'];

export default function CustomerNote({ id, initMemo, initTags }: { id: string; initMemo: string; initTags: string[] }) {
  const router = useRouter();
  const [memo, setMemo] = useState(initMemo);
  const [tags, setTags] = useState<string[]>(initTags);
  const [input, setInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const addTag = (t: string) => {
    const v = t.trim();
    if (v && !tags.includes(v)) setTags([...tags, v]);
    setInput('');
  };
  const rmTag = (t: string) => setTags(tags.filter((x) => x !== t));

  const save = async () => {
    setSaving(true);
    setMsg('');
    try {
      const r = await fetch('/api/customer-note', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: id, memo, prefer_tags: tags }),
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

  return (
    <div className="card" style={{ padding: '14px 15px' }}>
      <div className="ch" style={{ padding: 0, marginBottom: 8 }}>메모 · 취향</div>
      {tags.length > 0 && (
        <div className="tags" style={{ marginBottom: 8 }}>
          {tags.map((t) => (
            <span key={t} className="tagx" onClick={() => rmTag(t)}>
              {t} ✕
            </span>
          ))}
        </div>
      )}
      <input
        className="tagin"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            addTag(input);
          }
        }}
        placeholder="취향 태그 입력 후 Enter"
      />
      <div className="tagsug">
        {PRESETS.filter((p) => !tags.includes(p)).map((p) => (
          <button key={p} type="button" className="sug" onClick={() => addTag(p)}>
            + {p}
          </button>
        ))}
      </div>
      <textarea
        value={memo}
        onChange={(e) => setMemo(e.target.value)}
        placeholder="모발 상태, 선호 스타일, 주의사항 등 메모"
        rows={3}
        style={{ marginTop: 10 }}
      />
      <button className="primary" style={{ width: '100%', marginTop: 6 }} onClick={save} disabled={saving}>
        {saving ? '저장 중…' : '저장'}
      </button>
      {msg ? <div className="set-msg">{msg}</div> : null}
    </div>
  );
}
