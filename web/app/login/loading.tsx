/** 로그인 — 받아 올 데이터가 없어 곧 뜬다. 홈 뼈대(app/loading.tsx)가 잠깐 비치지 않게 빈 바탕만. */
export default function Loading() {
  return <main className="wrap" aria-busy="true" />;
}
