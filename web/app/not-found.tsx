import Link from 'next/link';
import { Empty } from '@/components/empty';

/** 없는 화면 — 지워진 손님의 카르테 링크 등. 기본 영문 404 대신(개선 계획 v5 P2). */
export default function NotFound() {
  return (
    <main className="wrap">
      <div className="body" style={{ paddingTop: 48 }}>
        <Empty title="찾는 화면이 없어요" hint="지워졌거나 주소가 바뀌었어요." action={<Link href="/">홈으로</Link>} />
      </div>
    </main>
  );
}
