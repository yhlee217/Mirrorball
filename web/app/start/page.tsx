import Link from 'next/link';

export const metadata = { title: '시작 안내 · 살롱 컨시어지' };

/**
 * 시작 안내(개선 계획 v11 P0) — 처음 쓰는 디자이너께 운영자가 주소 하나로 보내는 페이지. 로그인 없이 열리고 손님 정보는
 * 읽지 않는다(정적 페이지 — tests/test_start_page). 홈 화면에 먼저 추가하고 그 앱에서 로그인하게 순서를 잡았다 —
 * 아이폰은 홈 화면 앱과 사파리의 로그인이 따로라, 거꾸로 하면 로그인을 두 번 한다(app/login 참고).
 */
export default function StartPage() {
  return (
    <main className="wrap">
      <div className="body">
        <div className="top"><b>시작 안내</b></div>
        <p className="start-lead">디자이너님의 손님 관리를 돕는 앱이에요. 세 가지면 시작할 수 있어요.</p>

        <section className="card start-s">
          <h2>① 홈 화면에 추가</h2>
          <p>앱처럼 바로 열려요. 지금 이 화면에서 하면 돼요.</p>
          <ul>
            <li><b>아이폰</b> — 사파리 아래쪽 공유 버튼(□↑) → <b>홈 화면에 추가</b></li>
            <li><b>안드로이드</b> — 크롬 오른쪽 위 ⋮ → <b>홈 화면에 추가</b>(또는 &lsquo;앱 설치&rsquo;)</li>
          </ul>
        </section>

        <section className="card start-s">
          <h2>② 그 앱에서 로그인</h2>
          <ul>
            <li>홈 화면의 <b>컨시어지</b>를 열고 이메일을 넣은 뒤 <b>로그인 코드 받기</b></li>
            <li>메일로 온 <b>6자리 코드</b>를 넣으면 끝이에요</li>
            <li>처음엔 &lsquo;아직 매장에 연결되지 않았어요&rsquo;가 떠요 — 그 화면의 이메일을 운영자에게 알려 주시고, 연결되면 <b>다시 확인</b></li>
          </ul>
        </section>

        <section className="card start-s">
          <h2>③ 매주 이렇게</h2>
          <ul>
            <li><b>일요일 오후</b> — 앱이 한 주 방문 · 예약을 새로 받아요</li>
            <li><b>월요일</b> — 챙길 고객 맨 위 <b>새로</b>부터 한 분씩 문자나 카톡으로. 보낸 분은 2주 동안 목록에서 빠져요</li>
            <li><b>손님이 다녀가신 뒤</b> — 방문 탭에서 안 오셨으면 <b>노쇼</b>, 오셨으면 홈케어 안내를 보내 드려요</li>
          </ul>
        </section>

        <Link href="/login" className="btn start-go">로그인하러 가기</Link>
        <p className="start-q">궁금한 건 운영자에게 물어봐 주세요.</p>
      </div>
    </main>
  );
}
