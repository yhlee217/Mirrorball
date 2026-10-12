'use client';
import { useEffect } from 'react';

/**
 * 맨 바깥(레이아웃)까지 무너졌을 때의 안내 — 이때는 전역 스타일도 못 믿어 글자만 둔다(개선 계획 v5 P2).
 * 기록은 app/error.tsx 와 같은 길로.
 */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    fetch('/api/client-error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: window.location.pathname, digest: error.digest ?? null }),
      keepalive: true,
    }).catch(() => {});
  }, [error]);
  return (
    <html lang="ko">
      <body style={{ fontFamily: '-apple-system, sans-serif', textAlign: 'center', padding: '80px 24px', color: '#2A2622' }}>
        <p style={{ fontSize: 17, fontWeight: 800 }}>잠시 문제가 생겼어요</p>
        <p style={{ fontSize: 14 }}>다시 시도해도 안 되면 잠시 뒤에 열어 주세요.</p>
        <button type="button" onClick={reset} style={{ fontSize: 15, padding: '10px 18px', marginTop: 12 }}>
          다시 시도
        </button>
      </body>
    </html>
  );
}
