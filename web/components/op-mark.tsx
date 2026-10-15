'use client';
import { useEffect, useState } from 'react';
import { OP_KEY, setOpCookie } from './screen-timer';

/**
 * 운영자 폰 표시(개선 계획 v10 P0) — 설정을 `?op=1` 로 열면 이 폰을 운영자 폰으로(매장별 사용 수에서 빠지고 화면 속도엔
 * 남는다), `?op=0` 이면 푼다. 디자이너 화면엔 아무것도 없다 — 주소를 아는 운영자만 쓴다. 이 폰에만 저장한다(손님 정보 아님).
 * 운영자가 폰으로 확인한 화면이 가장 먼저 소속된 매장의 사용으로 섞였다(2026-10-15 첫 숫자).
 */
export default function OpMark() {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('op');
    if (q !== '1' && q !== '0') return;
    try {
      if (q === '1') window.localStorage.setItem(OP_KEY, '1');
      else window.localStorage.removeItem(OP_KEY);
      setOpCookie(q === '1'); // 서버 화면(/ops)도 알게 — 운영자 폰에서만 열린다(v12 P2)
      setMsg(q === '1' ? '이 폰은 운영자 폰 — 사용 수에서 빠져요' : '운영자 폰 표시를 풀었어요');
    } catch {
      setMsg('이 브라우저는 저장이 막혀 있어 표시하지 못했어요');
    }
    window.history.replaceState(null, '', window.location.pathname); // 주소에서 지운다 — 다시 열어도 또 뜨지 않게
    const t = setTimeout(() => setMsg(null), 4000);
    return () => clearTimeout(t);
  }, []);
  return msg ? <div className="toast" role="status">{msg}</div> : null;
}
