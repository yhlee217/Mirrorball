'use client';
import { useEffect } from 'react';

/**
 * 화면 속도 재기(개선 계획 v7 P0) — 화면을 누른 순간 → 그 화면 내용이 뜬 순간을 폰에서 잰다.
 *
 *  NavStart     앱 안의 링크를 누르거나 뒤로 가면 그 시각을 적는다(루트 레이아웃에 하나).
 *  SkeletonSeen 뼈대(각 화면 loading.tsx)가 떴다는 표시 — 안 떴으면 받아 둔 화면을 바로 보여준 것(3분 저장).
 *  ScreenReady  각 화면 끝에 — 뜬 순간 걸린 시간을 보낸다. 앱을 처음 열 때는 열기 시작부터 잰다.
 *
 * 보내는 건 경로 · 밀리초 · 받아 둔 화면이었나 · 처음 열기였나 · 운영자 폰이었나 · 홈 화면 앱으로 열었나뿐이다
 * (api/client-timing, lib/ops cleanTiming). 재기는 화면을 막지 않는다 — 답을 기다리지 않고(sendBeacon), 실패해도 아무 일도 없다.
 */

let start: number | null = null; // 마지막으로 누른 시각(performance.now)
let skeleton = false; // 그 뒤 뼈대가 떴나
let opened = false; // 이 문서(앱 열기)에서 첫 화면을 이미 보냈나

/** 운영자 폰 표시 — 설정을 ?op=1 로 열면 이 폰에 남는다(components/op-mark). 사용 수에서 빼고 속도엔 남긴다(v10 P0). */
export const OP_KEY = 'mb-op';

function isOp(): boolean {
  try {
    return window.localStorage.getItem(OP_KEY) === '1';
  } catch {
    return false; // 저장이 막힌 브라우저 — 디자이너로 센다
  }
}

/** 운영자 폰 쿠키 — 서버 화면(운영자 화면 /ops)이 알 수 있게(v12 P2). 숫자뿐인 화면이라 쿠키 하나로 가린다. */
export function setOpCookie(on: boolean) {
  try {
    document.cookie = on ? 'mb-op=1; path=/; max-age=31536000; samesite=lax' : 'mb-op=; path=/; max-age=0; samesite=lax';
  } catch {
    /* 쿠키가 막혀도 사용 수 표시는 그대로 */
  }
}

/** 홈 화면 앱으로 열었나 — 브라우저 탭이 아니라(아이폰은 navigator.standalone). 설치 안내를 정할 숫자(v10 P0). */
function isApp(): boolean {
  try {
    return window.matchMedia('(display-mode: standalone)').matches
      || (navigator as Navigator & { standalone?: boolean }).standalone === true;
  } catch {
    return false;
  }
}

function post(url: string, body: Record<string, unknown>) {
  try {
    const json = JSON.stringify({ ...body, op: isOp(), app: isApp() });
    const ok = typeof navigator.sendBeacon === 'function'
      && navigator.sendBeacon(url, new Blob([json], { type: 'application/json' }));
    if (!ok) {
      void fetch(url, { method: 'POST', body: json, headers: { 'content-type': 'application/json' }, keepalive: true })
        .catch(() => undefined);
    }
  } catch {
    /* 재기 실패는 화면과 무관하다 */
  }
}

function send(body: { path: string; ms: number; cached: boolean; first: boolean; server?: number }) {
  post('/api/client-timing', body);
}

/** 챙길 고객 줄을 펼쳤다(개선 계획 v16 P1) — 펼쳤다는 것만 보낸다. 어느 손님인지는 안 보낸다(api/care-event). */
export function sendCareOpen() {
  post('/api/care-event', { step: 'open' });
}

/**
 * 앱 첫 열기 — 서버가 첫 바이트를 보낸 때(문서를 열기 시작한 때부터, ms). 브라우저가 이미 잰 값이라 따로 재지 않는다
 * (개선 계획 v16 P2). 전체 시간 가운데 서버 몫(로그인 확인 · 첫 화면 데이터)과 폰이 그린 몫을 가른다.
 */
function serverMs(): number | undefined {
  try {
    const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
    return nav && nav.responseStart > 0 ? nav.responseStart : undefined;
  } catch {
    return undefined;
  }
}

export function NavStart() {
  useEffect(() => {
    if (isOp() && !document.cookie.includes('mb-op=1')) setOpCookie(true); // 쿠키 전에 ?op=1 로 표시한 폰
    const onClick = (e: MouseEvent) => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
      if (!a || a.target === '_blank' || a.origin !== window.location.origin) return; // 전화 · 문자 · 바깥 링크
      if (a.pathname === window.location.pathname && a.search === window.location.search) return; // 같은 화면
      start = performance.now();
      skeleton = false;
    };
    const onPop = () => {
      start = performance.now();
      skeleton = false;
    };
    document.addEventListener('click', onClick, true); // 링크가 기본 동작을 막기 전에(캡처 단계)
    window.addEventListener('popstate', onPop);
    return () => {
      document.removeEventListener('click', onClick, true);
      window.removeEventListener('popstate', onPop);
    };
  }, []);
  return null;
}

export function SkeletonSeen() {
  useEffect(() => {
    skeleton = true;
  }, []);
  return null;
}

export function ScreenReady() {
  useEffect(() => {
    const now = performance.now();
    const path = window.location.pathname;
    if (start !== null) {
      send({ path, ms: now - start, cached: !skeleton, first: false });
      start = null;
    } else if (!opened) {
      send({ path, ms: now, cached: false, first: true, server: serverMs() }); // 앱을 처음 열 때 — 문서를 열기 시작한 때부터
    }
    opened = true;
  }, []);
  return null;
}
