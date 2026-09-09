'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  { href: '/', label: '홈', icon: '🏠', match: (p: string) => p === '/' },
  { href: '/customers', label: '고객', icon: '👥', match: (p: string) => p.startsWith('/customer') },
  // '알림'은 실시간 푸시를 기대하게 하는데 실제로는 주 1회 갱신되는 목록이다. 🔔 도 같은 오해를 키웠다.
  // 홈 칩·화면 제목이 이미 '챙길 고객'이라 탭만 어긋나 있었다 → 같은 말로 맞춘다.
  // ⏳ 는 '아직 안 오신 분'을 뜻해 방문(✅ 다녀가신 분)과 짝이 된다.
  { href: '/alerts', label: '챙길 고객', icon: '⏳', match: (p: string) => p.startsWith('/alerts') },
  { href: '/visits', label: '방문', icon: '✅', match: (p: string) => p.startsWith('/visits') },
  { href: '/profile', label: '소개', icon: '📇', match: (p: string) => p.startsWith('/profile') },
];

export default function TabBar() {
  const p = usePathname() || '/';
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
