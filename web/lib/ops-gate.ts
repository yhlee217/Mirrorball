import type { ServerClient } from './supabase/server';

/**
 * 운영 숫자(/ops)를 볼 수 있나(개선 계획 v15 P2).
 *
 * 0027 뒤엔 운영자 계정(ops_readers — SQL `ops_add_reader('이메일')`)만 — 숫자 함수도 DB 가 같은 계정에만 준다.
 * 그 전엔 함수가 없어 오류가 나므로 예전처럼 운영자 폰 쿠키(?op=1)로 연다. 쿠키는 누구나 켤 수 있어서 0027 뒤엔
 * '사용 수에서 빼기'(lib/ops)에만 쓴다.
 */
export async function canSeeOps(supabase: ServerClient, opCookie: boolean): Promise<boolean> {
  const { data, error } = await supabase.rpc('ops_is_reader');
  if (error) return opCookie;
  return data === true;
}

/**
 * 운영자 계정인가 — 기록(화면 속도 · 챙길 고객 펼침)의 '운영자 폰' 칸을 계정으로도 채운다(2026-10-26).
 * 폰 표시(?op=1)는 그 브라우저에만 남는데, 아이폰 홈 화면 앱은 사파리와 저장을 따로 써서 표시가 없었다 — 운영자가
 * 앱으로 연 화면이 디자이너 사용으로 섞였다. 0027 전(함수 없음)엔 false — 예전처럼 폰 표시만.
 */
export async function isOpsReader(supabase: ServerClient): Promise<boolean> {
  const { data, error } = await supabase.rpc('ops_is_reader');
  return !error && data === true;
}
