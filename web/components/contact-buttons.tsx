'use client';
import { smsHref, telHref, type ContactVia } from '@/lib/contact';

/**
 * 📞 전화 · 💬 문자 — 손님을 보고 있는 화면에서 바로(모바일 개선 M3). 전에는 카르테에서 번호를 볼 수도,
 * 걸 수도 없어 챙길 고객 탭으로 돌아가거나 연락처 앱을 따로 열어야 했다.
 *
 * log 이면 '연락함'을 남긴다(api/customer-contact) — 챙길 고객 대상인 분께 카르테에서 연락해도 챙길 고객
 * 목록·연락 효과에 같이 잡히게. 예약 확인 같은 연락까지 세면 연락 효과가 부풀어서, 대상일 때만.
 * 문자는 빈 문구로 연다(무슨 말을 할지는 그때그때 다르다 — 챙길 고객 문구는 그 탭에서).
 */
export function ContactButtons({ id, phone, log }: { id: string; phone: string; log: boolean }) {
  const mark = (via: ContactVia) => {
    if (!log) return;
    fetch('/api/customer-contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer_id: id, via }),
      keepalive: true, // 누르는 순간 전화·문자 앱으로 넘어가도 요청이 끊기지 않게
    }).catch(() => {});
  };
  return (
    <div className="cta">
      <a className="cta-b" href={telHref(phone)} aria-label="전화 걸기" onClick={() => mark('call')}>📞</a>
      <a className="cta-b" href={smsHref(phone, '')} aria-label="문자 보내기" onClick={() => mark('sms')}>💬</a>
    </div>
  );
}
