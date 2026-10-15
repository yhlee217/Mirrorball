'use client';
import { useState } from 'react';
import { smsHref, telHref, type ContactVia } from '@/lib/contact';
import { MSG } from '@/lib/copy';
import type { ContactButton } from '@/lib/settings';
import { shareOrCopy } from '@/lib/share';

/**
 * 📞 전화 · 💬 문자(또는 📤 카톡 등) — 손님을 보고 있는 화면에서 바로(모바일 개선 M3). 전에는 카르테에서 번호를 볼 수도,
 * 걸 수도 없어 챙길 고객 탭으로 돌아가거나 연락처 앱을 따로 열어야 했다.
 *
 * log 이면 '연락함'을 남긴다(api/customer-contact) — 챙길 고객 대상인 분께 카르테에서 연락해도 챙길 고객
 * 목록·연락 효과에 같이 잡히게. 예약 확인 같은 연락까지 세면 연락 효과가 부풀어서, 대상일 때만.
 * draft 는 대상일 때 챙길 고객 탭과 같은 문구(lib/care-draft, v12 P1) — 그때는 설정의 '연락 버튼'(button)을 따라
 * 💬 문자 또는 📤 카톡 등(폰의 공유 창 — 보내기를 마쳐야 기록)으로 연다. 대상이 아니면 빈 문자(무슨 말을 할지는 그때그때).
 * 번호가 없는 분은 대상일 때만 📤 하나.
 */
export function ContactButtons({
  id,
  phone,
  log,
  draft = null,
  button = 'sms',
}: {
  id: string;
  phone: string | null;
  log: boolean;
  draft?: string | null;
  button?: ContactButton;
}) {
  const [msg, setMsg] = useState('');
  const mark = (via: ContactVia) => {
    if (!log) return;
    fetch('/api/customer-contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer_id: id, via }),
      keepalive: true, // 누르는 순간 전화·문자 앱으로 넘어가도 요청이 끊기지 않게
    }).catch(() => {});
  };
  const send = async () => {
    if (!draft) return;
    const r = await shareOrCopy(draft);
    if (r === 'sent') mark('share');
    else if (r === 'copied') {
      mark('copy');
      setMsg('문구 복사됨 · 카톡에 붙여넣기');
      setTimeout(() => setMsg(''), 1800);
    } else if (r === 'fail') {
      setMsg(MSG.copyFail);
      setTimeout(() => setMsg(''), 1800);
    }
  };
  const share = !!draft && (button === 'share' || !phone);
  if (!phone && !share) return null;
  return (
    <div className="cta">
      {phone ? <a className="cta-b" href={telHref(phone)} aria-label="전화 걸기" onClick={() => mark('call')}>📞</a> : null}
      {share ? (
        <button type="button" className="cta-b" aria-label="카톡 등으로 보내기" onClick={send}>📤</button>
      ) : phone ? (
        <a className="cta-b" href={smsHref(phone, draft ?? '')} aria-label="문자 보내기" onClick={() => mark('sms')}>💬</a>
      ) : null}
      {msg ? <div className="toast" role="status">{msg}</div> : null}
    </div>
  );
}
