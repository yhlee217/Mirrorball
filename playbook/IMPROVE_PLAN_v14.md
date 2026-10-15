# 개선 계획 v14 — 보안 바탕: 응답 헤더 · Next.js 올리기 · 주간 취약점 점검

> 2026-10-15 · v13(디자이너 연결 · 자동 검증 · 운영 안내서) 뒤. 근거: 저장소 실사 · `npm audit`(운영 의존성).
> 앱 쪽 다음 큰 일(설치 안내 · 주간 알림)은 10.20 디자이너 숫자를 보고 정한다. 그 사이 미뤄 온 바탕 — **보안** — 을 본다.
> 손님 이름 · 번호를 보여 주는 앱인데 보안 응답 헤더가 하나도 없고, Next.js 14 에는 더 이상 고침이 나오지 않는다.

## 0. 지금 비어 있는 것

| # | 무엇 | 근거 | 일이 생기면 |
|---|---|---|---|
| 1 | **보안 응답 헤더가 없다** | `web/next.config.mjs` 에 headers 가 없고 Cloudflare `_headers` 파일도 없다 — 다른 사이트가 앱을 틀(iframe)에 넣어 누르게 하는 것(클릭재킹), 손님 상세 주소(`/customer/<id>`)가 바깥으로 새는 것(Referer), 엉뚱한 파일을 스크립트로 읽히는 것을 막는 줄이 없다 | 손님 정보를 보여 주는 앱이라 막을 수 있는 건 막아 둬야 한다(PIPA 안전성 확보 조치) |
| 2 | **Next.js 14.2.35 — 알려진 취약점, 고침은 15.5 이상에만** | `npm audit`: next 심각 1 · 높음 다수. 이 앱이 쓰지 않는 기능(next/image · 서버 액션 · rewrites · 윈도 서버)에 걸린 것은 해당 없음. **해당하는 것**: 서버 컴포넌트 요청으로 앱을 멈추게 하는 공격(DoS, 높음 3건) · 서버 컴포넌트 응답 캐시 오염(보통 2건) | 앱을 멈추게 하는 요청을 막을 고침이 14 에는 없다. 판이 낡을수록 올리기가 어려워진다 |
| 3 | Supabase 라이브러리 작은 취약점 | auth-js(낮음 — 잘못된 입력의 경로 처리) · cookie(낮음) — 같은 큰 판 안에서 올리면 끝 | |
| 4 | 취약점을 주기적으로 보는 곳이 없다 | 자동 검증(v13)은 테스트만 — 위 알림들은 오늘 처음 봤다 | 새 취약점이 나와도 모른다 |

## 1. 할 것

### P0 보안 응답 헤더
- 모든 화면 · API 에: 틀에 넣기 금지(`frame-ancestors 'none'` · `X-Frame-Options: DENY`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`(손님 주소가 바깥으로 안 샌다), `Permissions-Policy`(카메라 · 마이크 · 위치 끔), `Strict-Transport-Security`.
- 콘텐츠 보안 정책(CSP)은 **먼저 '보고만'**(Report-Only): 자기 주소 · Supabase 만 허용하는 정책을 걸고, 어긋나는 것이 생기면 운영 기록에 남긴다('무엇이 · 어디서'만 — 손님 정보 없음). 한 주 어긋남이 없으면 막기로 바꾼다(다음 계획). Next 14 의 nonce 방식 CSP 는 알려진 XSS 가 있어 쓰지 않는다(위 2).
- 확인: 이 환경에서 앱을 띄워(`next start`) 로그인 · 시작 안내 화면의 헤더와 CSP 어긋남 0 을 재고, 배포 뒤 폰에서 한 바퀴.

### P1 Next.js 15 로 올리기 (+ React 19 · Supabase 라이브러리)
- Next 15.5 최신(위 알림이 모두 고쳐진 판) · React 19 · Supabase 라이브러리 같은 큰 판의 최신. 바뀌는 곳: 요청 값(쿠키 · 주소 매개변수)을 기다려(`await`) 읽기 — 공식 바꿈 도구(codemod)로, 화면 몇 곳.
- **미리보기 주소로 먼저**: 새 브랜치에 올리면 Cloudflare 가 미리보기 주소를 만든다 — 운영자가 폰으로 한 바퀴 확인한 뒤 운영 브랜치에 합친다. 배포 도구(next-on-pages)가 15.5 를 못 따라오면 그 사실을 보고하고 멈춘다(운영 브랜치는 그대로).
- 확인: 타입 검사 · 테스트 690여 개 · UI 측정 · Pages 빌드 · `npm audit` 높음 0 · 미리보기에서 로그인 · 홈 · 챙길 고객 · 방문 · 상세보기 · 통계 · 설정. 합친 뒤 문제가 생기면 커밋 하나 되돌리면 지금 판으로 돌아간다.

### P2 주간 취약점 점검
- GitHub Actions — 매주 월요일 운영 의존성 `npm audit`, 높음 이상이면 실패 → 메일(감시와 같은 길). P1 뒤에 건다(지금 걸면 첫 주부터 빨강).

### 다음 — 설치 안내 · 주간 알림(10.20 숫자 뒤) · 생일 · HandSOS 엑셀(운영자 확인 뒤) · 내 말투로(연락이 쌓이면)

## 2. 하지 않을 것
- **Next 16 으로 바로** — 큰 판 둘(15 · 16)을 한꺼번에 넘으면 배포 도구가 따라오지 못할 수 있다. 고쳐진 15.5 먼저.
- **CSP 를 바로 막기로** — 어긋나는 게 있으면 화면이 깨진다. 한 주는 보고만.
- **배포 도구 바꾸기(OpenNext 등)** — 지금 도구로 15.5 가 되면 그대로 간다.

## 3. 순서와 확인

P0 → P1(미리보기 → 운영자 확인 → 합치기) → P2. 단계마다 tsc · 테스트 · Pages 빌드 · UI 측정.

| 단계 | 확인할 것 |
|---|---|
| P0 | 헤더가 모든 경로에(로컬 `next start` 로 재기) · CSP 어긋남 보고가 운영 기록에(손님 정보 없음 — 테스트) · 화면 깨짐 없음 |
| P1 | 위 '확인' 그대로 · 미리보기에서 운영자 확인 |
| P2 | 첫 실행 초록(P1 뒤) |

## 4. 정해야 할 것

1. 보안 헤더(P0) — **바로 · CSP 는 한 주 보고만(추천)** / CSP 도 바로 막기 / 안 함
2. Next 15(P1) — **미리보기 브랜치로 먼저(추천 — 운영 브랜치 말고 브랜치 하나를 더 써도 되는지 허락이 필요)** / 운영 브랜치에 바로 / 미루기
3. 주간 취약점 점검(P2) — **P1 뒤에(추천)** / 지금(첫 주부터 빨강)

## 5. 운영자가 할 일
P1 미리보기 주소가 나오면 폰에서 한 바퀴(로그인 · 홈 · 챙길 고객 · 방문 · 상세보기 · 통계 · 설정). Cloudflare Pages → 설정에서 '미리보기 배포'가 켜져 있는지(기본값은 켜짐). 그 밖은 `playbook/OPERATIONS_APP.md` §7.

## 6. 진행 기록 (2026-10-15 — 정해야 할 것 모두 추천대로, 미리보기 브랜치 허락)

| 단계 | 한 것 | 확인 |
|---|---|---|
| **P0 보안 헤더** | `web/lib/security-headers.mjs` — 틀 넣기 금지(CSP `frame-ancestors 'none'` · `X-Frame-Options: DENY`) · `nosniff` · `Referrer-Policy: same-origin` · `Permissions-Policy`(카메라 · 마이크 · 위치 · 결제 · USB) · HSTS, CSP 전체는 보고만(self · Supabase 출처, `report-uri`). `next.config` 가 모든 경로에 붙이고, **미들웨어도 직접 붙인다** — Cloudflare(next-on-pages)에선 미들웨어를 거치는 응답에 next.config 헤더가 안 붙는다(로컬 workerd 로 재 보니 로그인 화면에만 붙고 홈 · 설정 · API 엔 없었다 → 같은 날 고침). 어긋남은 `api/csp-report` + `components/csp-watch` → 운영 기록 kind 'csp'(규칙 · 출처 · 경로만, `lib/ops cleanCsp`), `0026_csp_reports.sql`(종류 · 정책 · `ops_csp()`), 매일 감시 · 운영 숫자에 지난 7일 어긋남 | `test_security_headers` · 임시 Postgres 0001~0026(디자이너는 자기 매장 csp 만 · '화면 오류' 수엔 안 섞임) · 로컬 workerd(`wrangler pages dev`): `/` · `/ops` · `/settings` · `/start` · `/login` · `/api/csp-report` 모두 헤더 7개, CSP 어긋남 0(로그인 '코드 받기'까지) |
| **P1 Next 15** | 미리보기 브랜치 `claude/charming-planck-hmgazi-next15`(커밋 하나): next 15.5.28 · React 19.2.9 · supabase-js 2.117.3 · @supabase/ssr 0.5.2. 쿠키 · 주소 값을 기다려 읽기(`supabaseServer()` async — 부르는 19곳, 운영자 쿠키, params 두 곳). 남은 npm audit 은 Next 안에 든 빌드 도구 postcss 뿐(우리 CSS 만 처리 — 바깥 입력이 안 닿음, Next 16 에서 풀림). next-on-pages 공식 지원은 15.5.2 까지라 빌드 · 로컬 workerd 실행으로 확인 | tsc · 695 passed · UI 측정 · Pages 빌드 · 로컬 workerd(헤더 7개 · CSP 0 · React 19 로그인 입력 · 단계 전환 · 콘솔 오류 0). **운영자가 폰으로 미리보기를 확인한 뒤 운영 브랜치에 합침**(합친 상태로 다시 tsc · 695 passed · UI 측정 · Pages 빌드) |
| **P2 주간 점검** | `.github/workflows/deps-audit.yml`(매주 월요일 10시 30분, 비밀값 없음) → `scripts/deps_audit.py` — 운영 의존성 `npm audit` 의 높음 · 심각 중 받아들이지 않은 것이 있으면 실패. 받아들인 것: postcss(Next 안의 빌드 도구 — 바깥 입력 없음, Next 16 에서 풀림)와 그 때문에만 걸린 패키지 | `test_deps_audit`(지금 모양은 통과 · 새 높음 · 자기 알림이 있는 next 는 실패 · 결과가 이상하면 '점검 실패') · 지금 잠금 파일로 돌려 정상 |
