'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function OnboardButton() {
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  return (
    <button
      className="primary"
      disabled={loading}
      onClick={async () => {
        setLoading(true);
        await fetch('/api/onboard', { method: 'POST' });
        router.refresh();
      }}
    >
      {loading ? '생성 중…' : '데모 데이터로 시작'}
    </button>
  );
}
