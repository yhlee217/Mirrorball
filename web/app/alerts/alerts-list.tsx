'use client';
import Link from 'next/link';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Empty } from '@/components/empty';
import { Help } from '@/components/help';
import { MSG } from '@/lib/copy';
import { smsHref, telHref, type ContactVia } from '@/lib/contact';

// why = 한 줄 사유('2개월째 · 평소 5주 · 뿌리염색'), note = 펼친 곳의 한 줄(마지막 방문일·휴가)
type Item = { id: string; name: string; phone: string | null; state: string; why: string; note: string; draft: string };

const STATE: Record<string, string> = { overdue: '이탈 위험', due: '재방문 도래' };

export default function AlertsList({ items, quiet, quietDays }: { items: Item[]; quiet: number; quietDays: number }) {
  const router = useRouter();
  const [toast, setToast] = useState('');
  const [busy, setBusy] = useState('');
  // 방금 연락한 카드 — 바로 지우면 '내가 뭘 눌렀는지'가 사라진다. 화면엔 남겨 표시만 바꾸고,
  // 다음에 열 때 목록에서 빠진다(onCareList). 문자 보낸 뒤 전화도 걸 수 있게 버튼은 그대로 둔다.
  const [done, setDone] = useState<Record<string, true>>({});
  // 펼친 줄 — 문구·복사·카르테·이탈 처리는 펼쳤을 때만(첫 화면에 여러 분이 들어오게, UX 계획 v3)
  const [open, setOpen] = useState<string | null>(null);

  const flash = (m: string) => {
    setToast(m);
    setTimeout(() => setToast(''), 1800);
  };

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.cssText = 'position:fixed;left:-9999px';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
      } catch {
        /* noop */
      }
      document.body.removeChild(ta);
    }
    flash('문구 복사됨 · 카톡에 붙여넣기');
  }

  // 문자·전화·복사 중 무엇을 눌러도 '연락함'으로 남긴다 — 따로 '연락함' 버튼을 두면 누르는 걸
  // 잊고, 그러면 같은 분이 다음 주에 또 뜬다. 잘못 눌렀으면 카드에서 되돌린다.
  // 문자·전화는 누르는 순간 다른 앱으로 넘어가므로 keepalive 로 보내 요청이 끊기지 않게 한다.
  function markContacted(id: string, via: ContactVia) {
    setDone((d) => ({ ...d, [id]: true }));
    fetch('/api/customer-contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customer_id: id, via }),
      keepalive: true,
    })
      .then((r) => {
        if (!r.ok) throw new Error();
      })
      .catch(() => {
        setDone((d) => {
          const n = { ...d };
          delete n[id];
          return n;
        });
        flash(MSG.saveFailShort);
      });
  }

  async function undoContacted(id: string) {
    try {
      const r = await fetch('/api/customer-contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: id, undo: true }),
      });
      if (!r.ok) throw new Error();
      setDone((d) => {
        const n = { ...d };
        delete n[id];
        return n;
      });
    } catch {
      flash(MSG.saveFailShort);
    }
  }

  // '이 분은 확실히 안 오신다'는 판단이 드는 자리가 바로 여기라, 목록에서 곧장 처리하게 뒀다.
  // 표시하면 이 목록·홈 신호에서 빠지고, 고객 카르테에서 되돌릴 수 있다.
  async function markChurned(id: string, name: string) {
    if (!window.confirm(`${name} 님을 이탈로 표시할까요?\n\n챙길 고객에서 빠집니다. 이력은 그대로 남고, 고객 카르테에서 언제든 되돌릴 수 있어요.`)) return;
    setBusy(id);
    try {
      const r = await fetch('/api/customer-churn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: id, churned: true }),
      });
      if (r.ok) {
        flash(`${name} 님을 이탈로 표시했어요`);
        router.refresh();
      } else flash(MSG.saveFailShort);
    } catch {
      flash(MSG.saveFailShort);
    }
    setBusy('');
  }

  // 다 연락해서 빈 것과, 정말 챙길 분이 없는 것은 다른 말이다
  const quietNote = `최근 ${quietDays}일 안에 연락한 분은 잠시 빠져요. 그 뒤에도 안 오시면 다시 올라와요.`;
  if (!items.length)
    return quiet ? (
      <Empty title="다 연락했어요" hint={`연락한 ${quiet}명은 ${quietDays}일 동안 숨겨져요.`} action={<Link href="/visits">최근 방문 보기 ›</Link>} />
    ) : (
      <Empty title="챙길 고객이 없어요" hint="재방문 시기가 된 분이 생기면 여기에 올라와요." action={<Link href="/visits">최근 방문 보기 ›</Link>} />
    );

  return (
    <>
      {quiet > 0 && (
        <div className="crow-q">
          연락한 {quiet}명 숨김<Help inline>{quietNote}</Help>
        </div>
      )}
      <div className="card">
        {items.map((it) => {
          const isOpen = open === it.id;
          const sent = !!done[it.id];
          return (
            <div className={'crow' + (sent ? ' done' : '') + (isOpen ? ' open' : '')} key={it.id}>
              <div className="crow-r">
                <button type="button" className="crow-m" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : it.id)}>
                  <span className="crow-n">
                    <b>{it.name}</b>
                    <span className={'ctag ' + it.state}>{STATE[it.state] ?? ''}</span>
                  </span>
                  <span className="crow-w">{sent ? '✓ 연락함' : it.why}</span>
                </button>
                {/* 연락이 이 화면의 일이다 — 문자는 문구가 채워진 채로 열린다. 번호가 없으면 복사만. */}
                <div className="crow-a">
                  {it.phone ? (
                    <>
                      <a className="cbtn main" href={smsHref(it.phone, it.draft)} onClick={() => markContacted(it.id, 'sms')}>
                        💬 문자
                      </a>
                      <a className="cbtn" href={telHref(it.phone)} aria-label="전화" onClick={() => markContacted(it.id, 'call')}>
                        📞
                      </a>
                    </>
                  ) : (
                    <button type="button" className="cbtn main" onClick={() => { copy(it.draft); markContacted(it.id, 'copy'); }}>
                      📋 복사
                    </button>
                  )}
                </div>
              </div>
              {isOpen ? (
                <div className="crow-x">
                  <div className="draft">{it.draft}</div>
                  {it.note ? <div className="crow-note">{it.note}</div> : null}
                  <div className="crow-acts">
                    {it.phone ? (
                      <button type="button" onClick={() => { copy(it.draft); markContacted(it.id, 'copy'); }}>
                        문구 복사
                      </button>
                    ) : null}
                    <Link href={`/customer/${it.id}`}>카르테</Link>
                    {sent ? (
                      <button type="button" onClick={() => undoContacted(it.id)}>연락 되돌리기</button>
                    ) : (
                      <button type="button" onClick={() => markChurned(it.id, it.name)} disabled={busy === it.id}>
                        {busy === it.id ? '처리 중…' : '이탈 처리'}
                      </button>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
