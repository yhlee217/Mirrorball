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

/** 홈 화면 앱으로 열었나 — 브라우저 탭이 아니라(아이폰은 navigator.standalone). 설치 안내를 정할 숫자(v10 P0). */
function isApp(): boolean {
  try {
    return window.matchMedia('(display-mode: standalone)').matches
      || (navigator as Navigator & { standalone?: boolean }).standalone === true;
  } catch {
    return false;
  }
}

function send(body: { path: string; ms: number; cached: boolean; first: boolean }) {
  try {
    const json = JSON.stringify({ ...body, op: isOp(), app: isApp() });
    const ok = typeof navigator.sendBeacon === 'function'
      && navigator.sendBeacon('/api/client-timing', new Blob([json], { type: 'application/json' }));
    if (!ok) {
      void fetch('/api/client-timing', { method: 'POST', body: json, headers: { 'content-type': 'application/json' }, keepalive: true })
        .catch(() => undefined);
    }
  } catch {
    /* 재기 실패는 화면과 무관하다 */
  }
}

export function NavStart() {
  useEffect(() => {
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
      send({ path, ms: now, cached: false, first: true }); // 앱을 처음 열 때 — 문서를 열기 시작한 때부터
    }
    opened = true;
  }, []);
  return null;
}
