export const runtime = 'edge';

import { redirect } from 'next/navigation';

// '노출' 탭은 없앴다 — 콘텐츠 제안은 소개 안(/profile/content)으로, 리뷰 요청은 방문 관리(/visits)로 옮김.
// 홈 화면에 추가된 앱이나 북마크가 옛 경로를 갖고 있을 수 있어 리다이렉트만 남긴다.
export default function ExposePage() {
  redirect('/profile/content');
}
