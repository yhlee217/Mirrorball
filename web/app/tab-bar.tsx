'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  { href: '/', label: '홈', icon: '🏠', match: (p: string) => p === '/' },
  { href: '/customers', label: '고객', icon: '👥', match: (p: string) => p.startsWith('/customer') },
  { href: '/alerts', label: '알림', icon: '🔔', match: (p: string) => p.startsWith('/alerts') },
];

export default function TabBar() {
  const p = usePathname() || '/';
  if (p.startsWith('/login') || p.startsWith('/auth')) return null;
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
