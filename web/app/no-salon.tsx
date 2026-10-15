import Link from 'next/link';
import LogoutButton from './logout-button';
import OnboardButton from './onboard-button';

/**
 * 아직 매장에 연결되지 않은 계정(개선 계획 v11 P0) — 로그인은 됐지만 운영자가 매장을 잇기 전. 전에는 '데모 데이터로 시작'만
 * 보여 줘, 기다리던 디자이너가 누르면 데모 매장에 들어가 버렸다. 이제 운영자에게 알릴 이메일을 먼저 보여 주고, 데모는 작게.
 */
export default function NoSalon({ email }: { email: string | null }) {
  return (
    <main className="wrap">
      <div className="entry">
        <div className="brand">살롱 컨시어지</div>
        <p className="nos-t">아직 매장에 연결되지 않았어요</p>
        <p className="muted nos-p">운영자에게 이 이메일을 알려 주세요. 연결되면 &lsquo;다시 확인&rsquo;을 누르면 돼요.</p>
        {email ? <div className="nos-e">{email}</div> : null}
        <a className="btn nos-b" href="/">다시 확인</a>
        <div className="logout-row"><LogoutButton label="다른 이메일로 로그인" /></div>
        <div className="nos-x">
          <Link href="/start" className="linkbtn">사용 안내</Link>
          <OnboardButton />
        </div>
      </div>
    </main>
  );
}
