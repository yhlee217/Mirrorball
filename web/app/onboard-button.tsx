'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

/**
 * 데모로 둘러보기 — 가짜 손님으로 채운 데모 매장을 만든다(api/onboard). 매장 연결을 기다리는 디자이너가 실제 매장으로
 * 착각하지 않게 작게 두고 한 번 묻는다(개선 계획 v11 P0). 실제 매장이 연결되면 실제 매장이 먼저 열린다(lib/tenant-pick).
 */
export default function OnboardButton() {
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  return (
    <button
      className="linkbtn"
      disabled={loading}
      onClick={async () => {
        if (!window.confirm('가짜 손님으로 채운 데모 매장을 둘러봅니다.\n\n실제 매장이 연결되면 실제 매장이 열려요.')) return;
        setLoading(true);
        await fetch('/api/onboard', { method: 'POST' });
        router.refresh();
      }}
    >
      {loading ? '만드는 중…' : '데모로 둘러보기 — 실제 매장이 아니에요'}
    </button>
  );
}
