# Mirrorball 배포 가이드 (Cloudflare Pages)

> 목표: 리포를 Cloudflare Pages에 연결해 디자이너가 실제 URL로 접속. 무료 티어.
> 코드는 이미 origin(`claude/charming-planck-hmgazi`)에 다 올라가 있음 → 바로 연결 가능.

---

## STEP 1 — Cloudflare Pages 프로젝트 생성 (IAN)

1. Cloudflare 대시보드(무료 계정) → **Workers & Pages** → **Create** → **Pages** 탭 → **Connect to Git**
2. GitHub 연결 승인 → 리포 **Mirrorball** 선택
3. **Set up builds and deployments**에서 아래처럼 설정:

| 항목 | 값 |
|---|---|
| Production branch | `claude/charming-planck-hmgazi` |
| Framework preset | `Next.js` |
| Build command | `npx @cloudflare/next-on-pages@1` |
| Build output directory | `.vercel/output/static` |
| Root directory (Advanced) | `web` |

## STEP 2 — 환경변수 (IAN)

**Settings → Environment variables → Production**(+ Preview 동일)에 추가.
값은 **`web/.env.local` 파일에서 그대로 복사**(여기 값은 비밀이라 코드/채팅에 안 적음):

| 변수명 | 값 출처 |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | .env.local |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | .env.local |
| `SUPABASE_SERVICE_ROLE_KEY` | .env.local (서버 전용) |
| `MIRRORBALL_KEK` | .env.local (서버 전용) |
| `NODE_VERSION` | `20` |

> `NEXT_PUBLIC_SITE_URL`은 1차 배포 뒤 도메인이 정해지면 그때 추가(STEP 5).

## STEP 3 — nodejs_compat 플래그 (IAN, 필수)

**Settings → Functions(또는 Runtime) → Compatibility flags**:
- Production, Preview **둘 다** `nodejs_compat` 추가
- Compatibility date: `2024-11-01`

> 이거 빠지면 런타임에서 `Node.JS Compatibility Error` 남.

## STEP 4 — 첫 배포 & 빌드 로그 확인

- **Save and Deploy** → 빌드 시작(2~4분)
- 성공하면 `https://<프로젝트명>.pages.dev` 발급
- **빌드가 실패하면 로그 전체를 나에게 붙여줘** → 원인 짚고 수정

## STEP 5 — 배포 도메인 확정 후 마무리 (IAN + AI)

발급된 도메인(`https://mirrorball-app.pages.dev` 형태)을 알려주면:

- **(IAN)** Cloudflare env에 `NEXT_PUBLIC_SITE_URL = https://<도메인>` 추가 후 재배포
- **(IAN)** Supabase → **Authentication → URL Configuration**:
  - Site URL: `https://<도메인>`
  - Redirect URLs: `https://<도메인>/auth/callback`, `https://<도메인>/auth/confirm`
- **(AI)** 온보딩 링크를 그 도메인 기준으로 생성해줌(디자이너 3명 로그인)

## STEP 6 — Workers AI 바인딩 (IAN, 선택·문구 다듬기 활성화)

**Settings → Functions → AI Bindings** → Add → 이름 `AI` 저장 후 재배포.
- 없어도 앱은 동작(문구는 템플릿 폴백). 있으면 '문구 다듬기'가 실제 LLM.

---

### 배포 후 확인 체크
- [ ] `https://<도메인>` 접속 → 로그인 화면
- [ ] 매직링크 로그인 → 홈에 데이터(챙길 고객·예약) 표시
- [ ] 설정·고객·통계·노출 탭 정상
- [ ] 빌드 로그에 edge 관련 에러 없음
