# Mirrorball 배포 가이드

> 처음 연결하는 거면 **B. 최초 설정**부터. 이미 돌아가고 있으면 **A. 변경분 배포**만 하면 된다.

---

## A. 변경분 배포 (평소 이거만)

배포 대상이 **웹앱과 맥 워커 두 군데**다. 웹만 올리면 화면은 새 코드인데 수집 시각 기록이
안 남아 '수집 기준일'이 계속 안 보인다.

### A-1. 웹앱 — 대개 자동

Cloudflare Pages가 `claude/charming-planck-hmgazi` 브랜치에 연결돼 있으면 **푸시하는 순간 자동 빌드**된다.

1. Cloudflare 대시보드 → **Workers & Pages** → 프로젝트 → **Deployments**
2. 최신 커밋 해시로 빌드가 도는지 확인 (2~4분)
3. **Success** 뜨면 끝. 실패하면 로그 전체를 붙여줄 것

> 자동이 아니면 **Retry deployment** 또는 Pages 설정에서 Production branch가 위 브랜치인지 확인.

### A-2. 맥 워커 — 수동

```bash
cd ~/Desktop/Dev/Mirrorball
git pull origin claude/charming-planck-hmgazi

# 크로미움이 없으면 수집이 통째로 실패한다(주 1회라 놓치면 일주일 손해)
.venv/bin/python -m playwright install chromium

# 수집 주기 plist(주 1회)를 아직 안 걸었다면 한 번만
cp scripts/mac/com.mirrorball.collect.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.mirrorball.collect.plist 2>/dev/null
launchctl load   ~/Library/LaunchAgents/com.mirrorball.collect.plist

# 즉시 1회 — 이걸 돌려야 sync_jobs 에 기록이 남아 앱에 '수집 기준일'이 뜬다
FORCE=1 bash worker/run_mac.sh
```

확인:

```bash
launchctl list | grep mirrorball          # 등록됐는지
.venv/bin/python worker/gap_check.py      # 어디까지 모았는지
```

### A-3. DB 마이그레이션 — 이번엔 불필요

수집 시각은 기존 `sync_jobs` 테이블을 재사용한다. **적용할 SQL 없음.**

> 참고: `supabase/migrations/0016_tax_domain.sql`(세무 도메인)은 아직 실서버에 적용 안 된 상태다.
> 미용실 기능은 이 컬럼을 쓰지 않으므로 지금 적용할 필요 없다. 세무 작업 시작할 때 SQL Editor에서 실행.

### A-4. 배포 후 눈으로 확인할 것

| 화면 | 확인 |
|---|---|
| 홈 | 인사말 아래 `M월 D일 수집 기준 · N일 전`. 신호 4타일이 맨 위, 예약은 맨 아래 |
| 홈 예약 카드 | `… 수집 기준 · N건 — 그 뒤로 잡힌 예약은 HandSOS에서 확인하세요` |
| 고객 목록 | **이미 다녀간 사람에게 '예약 있음'이 안 붙는지** (이번 버그 수정 지점) |
| 카르테 | '다음 예약'에 취소·노쇼가 안 뜨는지 |
| 방문 관리 | `지난 2주 다녀가신 분` + 수집 기준일 |
| 알림 | 제목이 `챙길 고객`(‘오늘’ 빠짐) |
| 기록·통계 | 이번 달 막대가 점선이고 `8월*`, 아래 각주에 수집 기준일 |
| 설정 | 데이터 수집 설명이 `매주 일요일 1회` |

> A-2를 안 돌렸으면 '수집 기준일' 줄만 안 보인다(나머지는 정상). 다음 일요일에 자동으로 채워진다.

---

## B. 최초 설정 (Cloudflare Pages 연결)


### STEP 1 — Cloudflare Pages 프로젝트 생성

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

### STEP 2 — 환경변수 (IAN)

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

### STEP 3 — nodejs_compat 플래그 (IAN, 필수)

**Settings → Functions(또는 Runtime) → Compatibility flags**:
- Production, Preview **둘 다** `nodejs_compat` 추가
- Compatibility date: `2024-11-01`

> 이거 빠지면 런타임에서 `Node.JS Compatibility Error` 남.

### STEP 4 — 첫 배포 & 빌드 로그 확인

- **Save and Deploy** → 빌드 시작(2~4분)
- 성공하면 `https://<프로젝트명>.pages.dev` 발급
- **빌드가 실패하면 로그 전체를 나에게 붙여줘** → 원인 짚고 수정

### STEP 5 — 배포 도메인 확정 후 마무리 (IAN + AI)

발급된 도메인(`https://mirrorball-app.pages.dev` 형태)을 알려주면:

- **(IAN)** Cloudflare env에 `NEXT_PUBLIC_SITE_URL = https://<도메인>` 추가 후 재배포
- **(IAN)** Supabase → **Authentication → URL Configuration**:
  - Site URL: `https://<도메인>`
  - Redirect URLs: `https://<도메인>/auth/callback`, `https://<도메인>/auth/confirm`
- **(AI)** 온보딩 링크를 그 도메인 기준으로 생성해줌(디자이너 3명 로그인)

### STEP 6 — Workers AI 바인딩 (선택 · 문구 다듬기 활성화)

**Settings → Functions → AI Bindings** → Add → 이름 `AI` 저장 후 재배포.
- 없어도 앱은 동작(문구는 템플릿 폴백). 있으면 '문구 다듬기'가 실제 LLM.

---

### 최초 배포 후 확인 체크
- [ ] `https://<도메인>` 접속 → 로그인 화면
- [ ] 매직링크 로그인 → 홈에 데이터(챙길 고객·예약) 표시
- [ ] 설정·고객·통계·노출 탭 정상
- [ ] 빌드 로그에 edge 관련 에러 없음
