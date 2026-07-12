import './globals.css';
import type { Metadata } from 'next';
import TabBar from './tab-bar';

export const metadata: Metadata = {
  title: '살롱 컨시어지',
  description: '헤어 디자이너용 고객 관리',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        {children}
        <TabBar />
      </body>
    </html>
  );
}
