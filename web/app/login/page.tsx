'use client';
import { useState } from 'react';
import { supabaseBrowser } from '@/lib/supabase/client';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr('');
    setLoading(true);
    const supabase = supabaseBrowser();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${location.origin}/auth/callback` },
    });
    setLoading(false);
    if (error) setErr(error.message);
    else setSent(true);
  }

  return (
    <main className="wrap">
      <div className="entry">
        <div className="brand">살롱 컨시어지</div>
        {sent ? (
          <p className="muted">메일함을 확인하세요. 로그인 링크를 보냈어요.</p>
        ) : (
          <form onSubmit={submit} className="loginform">
            <input
              type="email"
              required
              placeholder="이메일"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <div className="err">{err}</div>
            <button disabled={loading} type="submit">
              {loading ? '보내는 중…' : '로그인 링크 받기'}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
