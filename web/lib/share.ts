/**
 * 폰의 공유 창으로 문구 보내기(개선 계획 v11 P1) — 카카오톡 · 문자 · 다른 앱을 디자이너가 고른다(공유 창에 '복사'도 있다).
 * 앱의 큰 버튼이 문자뿐이라 카톡으로 연락하면 앱엔 연락이 0명으로 남았다. 공유 창이 없는 브라우저(일부 PC)는 복사로 대신한다.
 *   sent   보내기를 마침(공유 창에서 앱을 골라 끝까지)     cancel  공유 창을 닫음 — 아무것도 안 남긴다
 *   copied 공유 창이 없어 복사로 대신함                    fail    복사도 안 됨
 */
export async function shareOrCopy(text: string): Promise<'sent' | 'cancel' | 'copied' | 'fail'> {
  if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
    try {
      await navigator.share({ text });
      return 'sent';
    } catch (e) {
      if ((e as { name?: string } | null)?.name === 'AbortError') return 'cancel';
      // 그 밖의 실패(권한 · 지원 안 하는 형식)는 복사로
    }
  }
  return (await copyText(text)) ? 'copied' : 'fail';
}

/** 클립보드에 복사 — 막힌 브라우저는 예전 방식(textarea + execCommand)으로. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (typeof navigator === 'undefined' || !navigator.clipboard) throw new Error('no clipboard');
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    if (typeof document === 'undefined') return false;
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px';
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand('copy');
    } catch {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  }
}
