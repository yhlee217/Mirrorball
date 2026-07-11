# Mirrorball Web (P1 — Next.js 앱 셸)

로그인 → (데모 온보딩) → RLS 스코프로 자기 테넌트 데이터를 읽어 홈을 렌더하는 개념 검증 스캐폴딩.

## 스택
Next.js 14 (App Router) · @supabase/ssr · Supabase Auth(매직링크) · RLS.

## 셋업
```bash
cd web
cp .env.local.example .env.local     # 값 채우기
npm install
npm run dev                          # http://localhost:3000
```

`.env.local` 값(Supabase → Project Settings → API):
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (서버 전용, 데모 온보딩용 — 클라이언트 노출 금지)

Supabase Auth 설정:
- Authentication → URL Configuration → Site URL `http://localhost:3000`, Redirect `http://localhost:3000/auth/callback` 추가.
- 매직링크는 이메일 발송 필요(무료 프로젝트 기본 SMTP로 동작).

## 흐름
1. `/login` 에서 이메일 입력 → 매직링크 수신 → 클릭 시 `/auth/callback` 에서 세션 교환.
2. 홈 `/` 은 멤버십이 없으면 "데모 데이터로 시작" 버튼 노출 → `/api/onboard`(service_role)가 데모 테넌트+운영데이터 생성.
3. 홈이 RLS 스코프로 예약·신호(이탈위험·재방문·신규·VIP)를 표시.

## 경계(중요)
- 고객 **이름·생일·전화(PII)** 는 `customers.pii_enc`(암호화)라 이 화면에선 표시하지 않음. 복호화는 P3(키 계층 연결) 이후.
- 데모 데이터는 PII 없이 운영 필드만 시드.

## 다음(P2~)
- P2: 수집 워커(Fly.io + Playwright) — `../scrape_handsos.py` 등 이식.
- P3: hayewoni `records.yaml` → 스키마 임포트(PII 암호화) + 홈에 이름 복호화 연결.
