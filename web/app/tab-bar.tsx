'use client';
import { useEffect, useRef } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { NAV_KEY } from '@/components/back-button';

const TABS = [
  { href: '/', label: '홈', icon: '🏠', match: (p: string) => p === '/' },
  { href: '/customers', label: '고객', icon: '👥', match: (p: string) => p.startsWith('/customer') },
  // '알림'은 실시간 푸시를 기대하게 하는데 실제로는 주 1회 갱신되는 목록이다. 🔔 도 같은 오해를 키웠다.
  // 홈 칩·화면 제목이 이미 '챙길 고객'이라 탭만 어긋나 있었다 → 같은 말로 맞춘다.
  // ⏳ 는 '아직 안 오신 분'을 뜻해 방문(✅ 다녀가신 분)과 짝이 된다.
  { href: '/alerts', label: '챙길 고객', icon: '⏳', match: (p: string) => p.startsWith('/alerts') },
  { href: '/visits', label: '방문', icon: '✅', match: (p: string) => p.startsWith('/visits') },
  // '소개'는 설정 안으로 옮겼다 — 공개 페이지는 한 번 만들고 거의 안 고친다(UX 계획 v2 2-3).
];

export default function TabBar() {
  const p = usePathname() || '/';
  // 처음 연 화면에서 다른 화면으로 옮겨 가면 '앱 안에서 다니는 중'을 남긴다 — '‹ 뒤로'가 이전 화면으로 갈지,
  // 앱 밖으로 나가지 않게 홈으로 갈지 정하는 근거(components/back-button).
  const first = useRef(p);
  useEffect(() => {
    if (p === first.current) return;
    try {
      sessionStorage.setItem(NAV_KEY, '1');
    } catch {
      /* 저장소를 못 쓰면 '‹ 뒤로'는 늘 홈으로 — 앱 밖으로 나가는 것보다 낫다 */
    }
  }, [p]);
  if (p.startsWith('/login') || p.startsWith('/auth') || p.startsWith('/p/')) return null;
  return (
    <nav className="tabbar">
      {TABS.map((t) => (
        <Link key={t.href} href={t.href} className={'tab' + (t.match(p) ? ' on' : '')}>
          <div className="i">{t.icon}</div>
          <div className="tl">{t.label}</div>
        </Link>
      ))}
    </nav>
  );
}
