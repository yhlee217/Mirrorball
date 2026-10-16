/**
 * 로그인 오류를 알아들을 말로(개선 계획 v15 P0). 전에는 Supabase 영어 오류가 그대로 떴다('Email address … not authorized').
 *
 * 메일 설정(SMTP)을 따로 하지 않았다면 Supabase 기본 메일은 프로젝트 팀원 주소로만 · 한 시간에 2통 보낸다. 그때는
 * 운영자가 맥에서 코드를 만들어 준다(worker/login_code.py) — 그래서 보내기 실패엔 늘 '운영자에게 코드'를 붙인다.
 * 오류 이름(code)이 있으면 그걸로, 없으면(옛 응답) 문장으로 가른다.
 */
type AuthErr = { message?: string | null; status?: number | null; code?: string | null } | null | undefined;

const ASK = '운영자에게 로그인 코드를 받아 아래에 넣어 주세요.';

function parts(e: AuthErr) {
  return { m: String(e?.message ?? '').toLowerCase(), c: String(e?.code ?? '').toLowerCase(), s: Number(e?.status ?? 0) };
}

const isRate = (m: string, c: string, s: number) =>
  s === 429 || c.startsWith('over_') || m.includes('rate limit') || m.includes('security purposes');

/** '로그인 코드 받기'가 실패했을 때. 코드 단계는 그대로 연다 — 운영자에게 받은 코드를 넣을 수 있게. */
export function sendError(e: AuthErr): string {
  const { m, c, s } = parts(e);
  if (c === 'email_address_not_authorized' || m.includes('not authorized')) return `이 주소로는 아직 메일을 보낼 수 없어요. ${ASK}`;
  if (isRate(m, c, s)) return `메일을 너무 자주 요청했어요. 1분쯤 뒤에 다시 하거나, ${ASK}`;
  if (c === 'email_address_invalid' || c === 'validation_failed' || (m.includes('invalid') && m.includes('email')))
    return '이메일 주소를 다시 확인해 주세요.';
  if (c === 'signup_disabled' || c === 'otp_disabled' || m.includes('signups not allowed')) return `아직 등록되지 않은 이메일이에요. ${ASK}`;
  return `메일을 보내지 못했어요. ${ASK}`;
}

/** 코드로 로그인이 실패했을 때. */
export function verifyError(e: AuthErr): string {
  const { m, c, s } = parts(e);
  if (isRate(m, c, s)) return '너무 여러 번 시도했어요. 잠시 뒤에 다시 해 주세요.';
  if (c === 'otp_expired' || m.includes('expired') || m.includes('invalid')) return '코드가 맞지 않거나 시간이 지났어요. 새 코드를 받아 주세요.';
  return '로그인하지 못했어요. 코드를 다시 확인하거나, 운영자에게 새 코드를 받아 주세요.';
}
