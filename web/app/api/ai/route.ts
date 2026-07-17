export const runtime = 'edge';

import { NextResponse } from 'next/server';
import { supabaseServer } from '@/lib/supabase/server';
import { buildPrompt, templateImprove } from '@/lib/coach';

const SYSTEM =
  '너는 한국 헤어살롱 디자이너를 돕는 카피라이터야. SNS 캡션과 고객 메시지를 자연스럽고 친근한 존댓말로, 과장·이모지 남발 없이 담백하게 써줘.';

// 온디맨드 문구 다듬기. Cloudflare Workers AI 바인딩(env.AI)이 있으면 LLM, 없으면 템플릿(무료 폴백).
// 자동 호출 금지 — 디자이너가 '다듬기' 누를 때만 호출되어 사용량이 작게 유지된다(스케일 안전).
export async function POST(request: Request) {
  const supabase = supabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: 'unauthorized' }, { status: 401 });

  const body = await request.json();
  const kind = String(body.kind || '');
  const ctx = (body.context && typeof body.context === 'object' ? body.context : {}) as Record<string, string>;

  try {
    // @ts-ignore — Cloudflare 배포 런타임 전용(로컬엔 모듈/타입 없음). 없으면 catch→템플릿 폴백.
    const mod = await import('@cloudflare/next-on-pages');
    const env = mod.getRequestContext().env as unknown as { AI?: { run: (m: string, o: unknown) => Promise<{ response?: string }> } };
    if (env.AI) {
      const out = await env.AI.run('@cf/meta/llama-3.1-8b-instruct', {
        messages: [
          { role: 'system', content: SYSTEM },
          { role: 'user', content: buildPrompt(kind, ctx) },
        ],
        max_tokens: 320,
      });
      const text = (out?.response || '').trim();
      if (text) return NextResponse.json({ text, source: 'ai' });
    }
  } catch {
    /* 로컬/바인딩 없음 → 템플릿 폴백 */
  }

  return NextResponse.json({ text: templateImprove(kind, ctx), source: 'template' });
}
