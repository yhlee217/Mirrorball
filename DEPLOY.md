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

# 크로미움은 이제 run_mac.sh 가 없으면 스스로 설치한다(2026-10-06). 수동 설치는 불필요.
# 다만 플레이라이트 자체를 올렸다면 한 번 돌려두는 게 빠르다.
.venv/bin/python -m playwright install chromium

# 수집 주기 plist(주 1회) 등록·갱신. plist 에 경로를 직접 적지 않는다(아래 ⚠ 참조)
bash scripts/mac/install_schedule.sh collect

# 즉시 1회 — 이걸 돌려야 sync_jobs 에 기록이 남아 앱에 '수집 기준일'이 뜬다
FORCE=1 bash worker/run_mac.sh
```

확인:

```bash
launchctl list | grep mirrorball          # 2번째 칸이 종료코드 — 0 이어야 정상
.venv/bin/python worker/gap_check.py      # 어디까지 모았는지
.venv/bin/python worker/sync_log.py       # 예정된 일요일이 실제로 돌았는지
```

> ### ⚠ 저장소를 `~/Desktop`·`~/Documents`·`~/Downloads` 에 두지 말 것
>
> 2026-08~10, 저장소가 `~/Desktop` 에 있어서 주간 수집이 **1392번 연속 실패**했다.
> macOS 는 이 세 폴더를 TCC 로 보호하고, launchd 는 그 안으로 `chdir` 하거나 로그를
> 열 수 없어 `posix_spawn(/bin/bash)` 이 `EPERM` 으로 죽는다. **11ms 만에, 스크립트가
> 한 줄도 돌지 않고** — 그래서 로그도 알림도 종료코드도 남지 않았다. 두 달을 날렸다.
>
> 터미널에서 `bash worker/run_mac.sh` 를 직접 돌리면 Terminal 의 권한을 쓰므로 **잘 된다.**
> "수동은 되는데 자동은 안 된다"가 이 증상의 모양이다.
>
> 옮기기(`.venv` 재생성·plist 재등록·실제 spawn 확인까지 한 번에):
> ```bash
> bash scripts/mac/relocate.sh          # → ~/Dev/Mirrorball
> ```
> `install_schedule.sh` 는 보호 폴더에서 실행하면 등록을 거부한다. launchd 로그는
> 저장소 위치와 무관하게 `~/Library/Logs/Mirrorball/` 에 쓴다.
>
> 그래도 78(EX_CONFIG)이 남으면 **시스템 설정 → 일반 → 로그인 항목 및 확장 →
> '백그라운드에서 허용'** 에서 Mirrorball 항목이 켜져 있는지 확인한다. 사유는:
> ```bash
> log show --predicate 'process == "launchd"' --last 10m --info | grep -i mirrorball
> ```

> **수집이 조용히 멈추는 걸 두 번 당했다.** 둘 다 로그 파일에만 흔적이 있었다.
> 지금은 실패하면 ① 맥 알림센터에 뜨고 ② `sync_jobs` 에 error 행이 남아
> `sync_log.py` 와 앱이 '안 돌았다/돌다가 실패했다'를 구분한다. 그래도 가장 확실한
> 점검은 위 세 줄이니, 배포 때마다 돌려볼 것.

### A-2.5. 수집 감시 — 최초 1회만 (GitHub Actions)

맥 밖에서 수집 지연을 감시한다. 맥이 꺼져 있어도, 크로미움이 없어도, 맥 알림을 놓쳐도
걸린다. **한 번만 설정하면 이후엔 손댈 일이 없다.**

1. Supabase SQL Editor 에서 `supabase/migrations/0022_sync_health.sql` 실행
2. GitHub → 저장소 → **Settings → Secrets and variables → Actions → New repository secret**
   | 이름 | 값 |
   |---|---|
   | `SUPABASE_URL` | `https://<ref>.supabase.co` |
   | `SUPABASE_ANON_KEY` | anon 키 (`NEXT_PUBLIC_SUPABASE_ANON_KEY` 와 같은 값) |
   | `ALERT_WEBHOOK` | *(선택)* 슬랙·디스코드 웹훅 URL |
3. **Actions → sync-health → Run workflow** 로 지금 한 번 돌려 확인

> anon 키면 충분하다 — 감시자는 `sync_health()` 함수만 호출하고, 그 함수는 수집
> 시각만 돌려준다(고객 정보에 구조적으로 닿을 수 없다). service_role 키는 주지 않는다.
>
> 지연이면 실행이 **실패**로 끝나고 GitHub 가 소유자에게 메일을 보낸다.
> 곁따라오는 효과로 이 일일 호출이 **Supabase 무료 플랜의 비활성 일시정지 타이머를
> 매일 리셋**한다 — 주 1회 수집은 그 기준과 간격이 거의 같아 여유가 없었다.

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
