'use client';
import { useEffect } from 'react';

/**
 * CSP 어긋남 듣기(개선 계획 v14 P0) — 정책(lib/security-headers.mjs)은 v16 P3 부터 막는다. 막히면(보고만이던 때는 어긋나면)
 * 무엇이 · 어디서만 운영 기록으로 보낸다(api/csp-report). 브라우저 자체 보고(report-uri)도 있지만 로그인 쿠키가
 * 안 실리는 브라우저가 있어 화면에서도 한 번 더. 같은 어긋남은 이 문서에서 한 번만.
 */
const seen = new Set<string>();

function blocked(uri: string): string {
  if (!uri || /^[a-z-]+$/i.test(uri)) return uri || 'unknown';
  try {
    const u = new URL(uri);
    return /^(https?|wss):$/.test(u.protocol) ? u.origin : u.protocol.replace(':', '');
  } catch {
    return 'unknown';
  }
}

export function CspWatch() {
  useEffect(() => {
    const on = (e: SecurityPolicyViolationEvent) => {
      const b = blocked(e.blockedURI);
      const key = `${e.effectiveDirective}|${b}`;
      if (seen.has(key)) return;
      seen.add(key);
      try {
        const json = JSON.stringify({ directive: e.effectiveDirective, blocked: b, path: window.location.pathname });
        navigator.sendBeacon?.('/api/csp-report', new Blob([json], { type: 'application/json' }));
      } catch {
        /* 기록 실패는 화면과 무관하다 */
      }
    };
    document.addEventListener('securitypolicyviolation', on);
    return () => document.removeEventListener('securitypolicyviolation', on);
  }, []);
  return null;
}
