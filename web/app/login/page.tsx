'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabaseBrowser } from '@/lib/supabase/client';

// PWA(홈 화면 앱)는 브라우저와 쿠키·저장소가 분리된다(특히 iOS). 메일의 '로그인 링크'를 누르면
// 브라우저에서만 로그인되고 앱은 로그아웃 상태로 남는다 → 앱 안에서 인증 코드를 입력해 세션을
// 만드는 OTP 방식이 기본. 메일 발송이 막힌 경우를 위해 '코드 직접 입력' 경로도 둔다(관리자 발급 코드).
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [step, setStep] = useState<'email' | 'code'>('email');
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setErr('');
    setLoading(true);
    const supabase = supabaseBrowser();
    const { error } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: { emailRedirectTo: `${location.origin}/auth/callback` },
    });
    setLoading(false);
    if (error) {
      // 발송 실패(메일 설정 문제)여도 관리자 발급 코드로 로그인할 수 있게 코드 단계는 열어둔다.
      setErr(error.message + ' — 발급받은 코드가 있으면 아래에 입력하세요.');
      setStep('code');
      return;
    }
    setStep('code');
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    setErr('');
    setLoading(true);
    const supabase = supabaseBrowser();
    const token = code.replace(/\D/g, '');
    // 앱에서 요청한 코드는 type 'email', 관리자 발급(매직링크) 코드는 'magiclink' 로 검증된다.
    let { error } = await supabase.auth.verifyOtp({ email: email.trim(), token, type: 'email' });
    if (error) {
      const r = await supabase.auth.verifyOtp({ email: email.trim(), token, type: 'magiclink' });
      error = r.error;
    }
    setLoading(false);
    if (error) {
      setErr(error.message);
      return;
    }
    router.replace('/');
    router.refresh();
  }

  return (
    <main className="wrap">
      <div className="entry">
        <div className="brand">살롱 컨시어지</div>
        {step === 'code' ? (
          <form onSubmit={verify} className="loginform">
            <p className="muted" style={{ marginBottom: 10, lineHeight: 1.5 }}>
              {email} 의 <b>인증 코드</b>를 입력하세요.
            </p>
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={10}
              required
              placeholder="인증 코드"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              style={{ letterSpacing: 4, textAlign: 'center', fontSize: 20 }}
            />
            <div className="err">{err}</div>
            <button disabled={loading} type="submit">
              {loading ? '확인 중…' : '로그인'}
            </button>
            <button
              type="button"
              className="linkbtn"
              style={{ marginTop: 12 }}
              onClick={() => {
                setStep('email');
                setCode('');
                setErr('');
              }}
            >
              이메일 다시 입력
            </button>
          </form>
        ) : (
          <form onSubmit={send} className="loginform">
            <input
              type="email"
              required
              placeholder="이메일"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <div className="err">{err}</div>
            <button disabled={loading} type="submit">
              {loading ? '보내는 중…' : '로그인 코드 받기'}
            </button>
            <button
              type="button"
              className="linkbtn"
              style={{ marginTop: 12 }}
              onClick={() => {
                if (!email.trim()) {
                  setErr('이메일을 먼저 입력하세요.');
                  return;
                }
                setErr('');
                setStep('code');
              }}
            >
              코드를 이미 받았다면 입력하기
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
