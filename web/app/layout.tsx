import './globals.css';
import type { Metadata, Viewport } from 'next';
import TabBar from './tab-bar';
import RefreshOnFocus from './refresh-on-focus';

export const metadata: Metadata = {
  title: '살롱 컨시어지',
  description: '헤어 디자이너용 고객 관리',
  manifest: '/manifest.webmanifest',
  appleWebApp: { capable: true, statusBarStyle: 'default', title: '컨시어지' },
  icons: { icon: '/icon-192.png', apple: '/apple-icon.png' },
};

export const viewport: Viewport = {
  themeColor: '#F4F1EC',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        {children}
        <TabBar />
        <RefreshOnFocus />
      </body>
    </html>
  );
}
