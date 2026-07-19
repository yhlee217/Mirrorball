'use client';
import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';

// PWA(홈 화면 앱)를 백그라운드에 뒀다 다시 열면, 이미 렌더된 서버 컴포넌트가 그대로 남아
// 다가오는 예약·챙길 고객이 갱신되지 않는다(새 요청이 없으므로). 화면이 다시 보이는 순간
// 서버 컴포넌트를 다시 렌더해 최신 데이터로 바꾼다.
// '오늘 지난 시간 제외'(lib/kst) 필터도 렌더 시각 기준이라, 앱을 오래 열어둔 경우를 위해
// 주기적으로도 갱신한다 — 10시 예약이 11시가 되면 저절로 사라지도록.
export default function RefreshOnFocus() {
  const router = useRouter();
  const last = useRef(0);

  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - last.current < 20_000) return; // 연속 이벤트로 과도하게 재요청하지 않도록
      last.current = now;
      router.refresh();
    };
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('focus', refresh);
    const timer = setInterval(refresh, 5 * 60 * 1000); // 열어둔 채로도 5분마다
    return () => {
      document.removeEventListener('visibilitychange', refresh);
      window.removeEventListener('focus', refresh);
      clearInterval(timer);
    };
  }, [router]);

  return null;
}
