'use client';
import { useEffect } from 'react';
import Link from 'next/link';
import { Empty } from '@/components/empty';

/**
 * 화면 오류 안내 — Next 기본 오류 화면('Application error…') 대신(개선 계획 v5 P2). 어느 화면에서 났는지만
 * 운영 기록에 남긴다(api/client-error — 손님 정보·오류 본문은 보내지 않는다). 디자이너가 말해주기 전에
 * 운영자가 알 수 있게 sync-health 가 매일 건수를 본다.
 */
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    fetch('/api/client-error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: window.location.pathname, digest: error.digest ?? null }),
      keepalive: true,
    }).catch(() => {});
  }, [error]);

  return (
    <main className="wrap">
      <div className="body" style={{ paddingTop: 48 }}>
        <Empty
          title="잠시 문제가 생겼어요"
          hint="다시 시도해도 안 되면 잠시 뒤에 열어 주세요. 문제는 자동으로 기록됐어요."
          action={
            <>
              <button type="button" onClick={reset}>다시 시도</button>
              {' · '}
              <Link href="/">홈으로</Link>
            </>
          }
        />
      </div>
    </main>
  );
}
