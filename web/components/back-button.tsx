'use client';
import { useRouter } from 'next/navigation';

/** 이 탭(세션)에서 앱 안을 한 번이라도 옮겨 다녔나 — app/tab-bar.tsx 가 화면이 바뀔 때 남긴다. */
export const NAV_KEY = 'mb_nav';

/**
 * '‹ 뒤로' — 앱 안에서 넘어왔으면 그 화면으로, 링크로 처음 연 화면이면 fallback 으로(모바일 개선 M2).
 *
 * 전에는 '‹ 홈' 링크라 늘 홈으로 갔다: 고객 목록에서 카르테를 보고 돌아가면 목록이 아니라 홈이 떠
 * 검색을 다시 해야 했다. 홈 화면에 설치한 앱엔 브라우저 뒤로 버튼이 없어 이 버튼이 유일한 길이다.
 * 바깥(메신저 링크 등)에서 처음 열었을 때 history.back() 하면 앱 밖으로 나가므로 그때만 fallback.
 */
export function BackButton({ fallback = '/' }: { fallback?: string }) {
  const router = useRouter();
  const go = () => {
    let inApp = false;
    try {
      inApp = sessionStorage.getItem(NAV_KEY) === '1';
    } catch {
      /* 저장소를 못 쓰면 안전하게 fallback */
    }
    if (inApp && window.history.length > 1) router.back();
    else router.push(fallback);
  };
  return (
    <button type="button" className="back" onClick={go}>
      ‹ 뒤로
    </button>
  );
}
