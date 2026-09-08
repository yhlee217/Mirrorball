'use client';
import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';

// 성별 지정 — 추정이 못 가른 고객을 디자이너가 직접 채운다.
// 저장은 gender_manual 로 가고, 지우면 다시 추정값을 따른다.
// 통계가 이 값을 쓰므로 저장 뒤 화면을 다시 그려 즉시 반영한다.
export default function GenderPicker({
  id,
  manual,
  inferred,
}: {
  id: string;
  manual: 'M' | 'F' | null;
  inferred: 'M' | 'F' | null;
}) {
  const [cur, setCur] = useState<'M' | 'F' | null>(manual);
  const [saving, setSaving] = useState(false);
  const [pending, startTransition] = useTransition();
  const router = useRouter();
  const busy = saving || pending;

  const pick = async (g: 'M' | 'F' | null) => {
    if (busy) return;
    const next = cur === g ? null : g; // 같은 걸 다시 누르면 지정 해제
    setSaving(true);
    setCur(next);
    try {
      const r = await fetch('/api/customer-gender', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: id, gender: next }),
      });
      if (!r.ok) throw new Error();
      startTransition(() => router.refresh());
    } catch {
      setCur(manual);
      alert('저장하지 못했어요. 잠시 후 다시 눌러주세요.');
    } finally {
      setSaving(false);
    }
  };

  const shown = cur ?? inferred;
  const label = (g: 'M' | 'F') => (g === 'M' ? '남성' : '여성');

  return (
    <div className="gpick">
      <span className="gp-l">성별</span>
      {(['M', 'F'] as const).map((g) => (
        <button key={g} type="button" disabled={busy} aria-pressed={cur === g}
          className={'gp-b' + (cur === g ? ' on' : shown === g ? ' inf' : '')}
          onClick={() => pick(g)}
          title={cur === g ? '눌러서 지정 해제(다시 추정값 사용)' : `${label(g)}으로 지정`}>
          {label(g)}
        </button>
      ))}
      <span className="gp-s">
        {busy ? '저장 중…'
          : cur ? '직접 지정함'
          : inferred ? '시술명으로 추정' : '추정 불가 — 직접 지정해 주세요'}
      </span>
    </div>
  );
}
