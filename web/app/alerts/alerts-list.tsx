'use client';
import Link from 'next/link';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Empty } from '@/components/empty';
import { Help } from '@/components/help';
import { MSG } from '@/lib/copy';
import { smsHref, telHref, type ContactVia } from '@/lib/contact';
import type { Effect } from '@/lib/effect';
import { man } from '@/lib/format';

// why = 한 줄 사유('2개월째 · 평소 5주 · 뿌리염색' · '안부 · 6일 전 · 뿌리염색'), note = 펼친 곳의 한 줄(방문일·휴가)
// prepaid = 선불 잔액(추정) — 디자이너만 보는 꼬리표. 문구엔 넣지 않는다
type Item = { id: string; name: string; phone: string | null; state: string; why: string; note: string; draft: string; prepaid?: number };

// 첫 방문 손님은 안부·다시 오실 때 모두 '첫 방문' — 무엇을 할지는 사유 줄 첫마디가 말한다(lib/customers firstCare)
const STATE: Record<string, string> = { overdue: '이탈 위험', due: '재방문 도래', hello: '첫 방문', back: '첫 방문' };
const STEP = 50; // 한 번에 펼치는 수 — 급한 분(이탈 위험)부터 정렬돼 온다

// 연락 효과는 사람 수가 이만큼은 돼야 보여준다 — 서너 명이면 한 명에 크게 흔들린다
const EFFECT_MIN = 10;

export default function AlertsList({
  items,
  quiet,
  quietDays,
  effect,
}: {
  items: Item[];
  quiet: number;
  quietDays: number;
  effect: Effect | null; // 지난 4주 연락 → 그 뒤 오심·예약(lib/effect) — 연락 기록이 없으면 null
}) {
  const router = useRouter();
  const [toast, setToast] = useState('');
  const [busy, setBusy] = useState('');
  // 방금 연락한 카드 — 바로 지우면 '내가 뭘 눌렀는지'가 사라진다. 화면엔 남겨 표시만 바꾸고,
  // 다음에 열 때 목록에서 빠진다(onCareList). 문자 보낸 뒤 전화도 걸 수 있게 버튼은 그대로 둔다.
  const [done, setDone] = useState<Record<string, true>>({});
  // 펼친 줄 — 문구·복사·카르테·이탈 처리는 펼쳤을 때만(첫 화면에 여러 분이 들어오게, UX 계획 v3)
  const [open, setOpen] = useState<string | null>(null);
  const [shown, setShown] = useState(STEP);

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

  // 맨 위 한 줄 — 연락 효과(보낸 뒤 오셨나)와 잠시 숨긴 수. 설명은 ? 하나에.
  const eff = effect && effect.contacted > 0 ? effect : null;
  return (
    <>
      {eff || quiet > 0 ? (
        <div className="crow-q">
          {eff ? (
            eff.contacted >= EFFECT_MIN ? (
              <span>
                4주 연락 {eff.contacted}명 → <b>{eff.came}명 오심</b>
                {eff.booked ? ` · ${eff.booked}명 예약` : ''}
              </span>
            ) : (
              <span>4주 연락 {eff.contacted}명 · 효과는 쌓이는 중</span>
            )
          ) : null}
          {eff && quiet > 0 ? ' · ' : ''}
          {quiet > 0 ? <span>{eff ? `${quiet}명 숨김` : `연락한 ${quiet}명 숨김`}</span> : null}
          <Help inline>
            {eff ? (
              <>
                지난 4주 연락한 분 중 연락한 날 뒤에 다녀가신 분은 &lsquo;오심&rsquo;, 아직 안 오셨지만 예약이 잡힌 분은
                &lsquo;예약&rsquo;이에요(같은 분께 여러 번 연락해도 한 번). 방문은 주 1회 수집이라 최대 한 주 늦게 잡히고,
                {EFFECT_MIN}명이 넘어야 숫자를 보여드려요.{' '}
              </>
            ) : null}
            {quiet > 0 ? quietNote : null}
          </Help>
        </div>
      ) : null}
      <div className="card">
        {items.slice(0, shown).map((it) => {
          const isOpen = open === it.id;
          const sent = !!done[it.id];
          return (
            <div className={'crow' + (sent ? ' done' : '') + (isOpen ? ' open' : '')} key={it.id}>
              <div className="crow-r">
                <button type="button" className="crow-m" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : it.id)}>
                  <span className="crow-n">
                    <b>{it.name}</b>
                    <span className={'ctag ' + it.state}>{STATE[it.state] ?? ''}</span>
                    {it.prepaid ? <span className="ppd">선불 {man(it.prepaid)}</span> : null}
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
      {items.length > shown ? (
        <button type="button" className="more-btn" onClick={() => setShown((n) => n + STEP)}>
          더 보기 <span className="sect-n">{Math.min(STEP, items.length - shown)}명 · 남은 {items.length - shown}명</span>
        </button>
      ) : null}
      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
