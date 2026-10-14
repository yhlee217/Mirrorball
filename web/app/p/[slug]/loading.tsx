/**
 * 공개 소개(손님이 보는 화면) — 디자이너 앱의 뼈대가 비치지 않게 빈 종이만 둔다.
 * 이 파일이 없으면 홈 뼈대(app/loading.tsx — 오늘 · 지난주)가 손님에게 잠깐 보인다.
 */
export default function Loading() {
  return <main className="pub" aria-busy="true" />;
}
