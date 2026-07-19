'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabaseBrowser } from '@/lib/supabase/client';

// PWA(홈 화면 앱)는 브라우저와 쿠키·저장소가 분리된다(특히 iOS). 그래서 메일의 '로그인 링크'를
// 누르면 브라우저에서만 로그인되고 앱은 계속 로그아웃 상태가 된다. → 앱 안에서 6자리 코드를
// 입력해 세션을 만드는 OTP 방식이 기본. (링크도 함께 오므로 브라우저에서는 그대로 써도 된다.)
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState(false);
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
    if (error) setErr(error.message);
    else setSent(true);
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    setErr('');
    setLoading(true);
    const supabase = supabaseBrowser();
    const { error } = await supabase.auth.verifyOtp({
      email: email.trim(),
      token: code.replace(/\D/g, ''),
      type: 'email',
    });
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
        {sent ? (
          <form onSubmit={verify} className="loginform">
            <p className="muted" style={{ marginBottom: 10, lineHeight: 1.5 }}>
              {email} 으로 보낸 <b>6자리 코드</b>를 입력하세요.
            </p>
            <input
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
              placeholder="000000"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              style={{ letterSpacing: 6, textAlign: 'center', fontSize: 20 }}
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
                setSent(false);
                setCode('');
                setErr('');
              }}
            >
              코드 다시 받기
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
          </form>
        )}
      </div>
    </main>
  );
}
