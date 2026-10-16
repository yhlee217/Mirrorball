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
