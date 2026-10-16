# 운영 안내서 — 디자이너 앱(살롱 컨시어지)

> 지금 앱 기준(2026-10-15, 개선 계획 v13 P2). v5~v12 계획서의 '운영자가 할 일'을 여기에 모았다 — 앞으로 새로 생기는 할 일도
> 여기에 더한다. 예전 소개 페이지 · 노출 진단 런북은 `playbook/OPERATIONS.md`.
> 키 값은 어디에도 붙여넣지 않는다(채팅 · 이슈 · 문서). 맥의 `web/.env.local` 에만 둔다.

## 0. 한눈에

| 무엇 | 어디서 | 메모 |
|---|---|---|
| 앱 | `web/` → Cloudflare Pages | 브랜치 `claude/charming-planck-hmgazi` 에 푸시되면 몇 분 뒤 배포 |
| 데이터 | Supabase | 손님 이름 · 번호는 매장 키로 암호화(`pii_enc`) — 화면만 푼다 |
| 수집 | 매장 맥(국내 IP), 매주 일요일 14시 | HandSOS → Supabase. 약관 리스크로 주 1회(`LAUNCH.md`) |
| 백업 | 같은 맥, 수집 뒤 | 앱에만 있는 데이터(메모 · 노쇼 표시 · 연락 기록 등)를 암호화해 주 1회 |
| 매일 감시 | GitHub Actions `sync-health`, 매일 10시쯤(GitHub 사정으로 늦을 수 있다) | 수집 지연 · 백업 · 화면 오류는 실패(메일), 화면 속도 · 매장별 사용은 출력만 |
| 자동 검증 | GitHub Actions `test`, 푸시마다 | 타입 검사 + 테스트. 빨갛게 끝나면 메일 |
| 취약점 점검 | GitHub Actions `deps-audit`, 매주 월요일 10시 30분 | 운영 의존성에 받아들이지 않은 높음 · 심각이 있으면 메일(`scripts/deps_audit.py`) |
| 열쇠 한 부 | 운영자 비밀번호 관리자 | `MIRRORBALL_KEK` — 맥 밖에서 다시 읽을 수 있는 유일한 사본(Cloudflare · GitHub 는 넣기만 된다). 맥이 없어져도 이것으로 되살린다(§6) |

## 1. 매주 흐름

| 언제 | 무엇이 일어나나 | 운영자가 볼 것 |
|---|---|---|
| 일요일 14시 | 맥이 수집 + 백업 | 월요일 감시가 초록인지(메일이 없으면 초록) |
| 월요일 | 챙길 고객 '이번 주 새로'가 바뀐다 | 운영 숫자(`/ops`) — 매장별 디자이너 화면 · 연락 수 |
| 매일 | 감시 | 메일이 오면 §6 |

## 2. 새 디자이너 연결

1. 매장이 아직 없으면(새 디자이너) — `secrets/stores.yaml` 의 designers 에 넣고 맥에서:

```bash
cd ~/Dev/Mirrorball && CONFIRM=1 .venv/bin/python worker/onboard_designers.py
```

2. 디자이너님께 **앱 주소 끝에 `/start`** 를 붙인 주소를 보낸다 — 홈 화면에 추가 → 그 앱에서 로그인(로그인 없이 열리는 안내 페이지).
   - **메일로 코드가 안 오면**(스팸함에도 없으면) 아래 3 대신 '코드가 메일로 안 올 때'로 간다. 메일 설정(SMTP)을 따로 하지
     않았다면 Supabase 기본 메일은 프로젝트 팀원 주소로만 가서, 처음엔 대개 이쪽이다(v15).
3. 디자이너님 화면에 '아직 매장에 연결되지 않았어요'와 이메일이 뜬다 — 그 이메일을 받는다.
4. 맥에서 미리보기 → 확인되면 연결(이메일 · 매장 이름은 그대로 바꿔 넣는다):

```bash
cd ~/Dev/Mirrorball && .venv/bin/python worker/link_designer.py 이메일 매장
```

```bash
cd ~/Dev/Mirrorball && CONFIRM=1 .venv/bin/python worker/link_designer.py 이메일 매장
```

5. 디자이너님이 앱에서 **다시 확인**을 누르면 자기 매장이 열린다.

**코드가 메일로 안 올 때** — 디자이너님 이메일을 전화나 카톡으로 받아, 맥에서 미리보기 → 확인되면 실행. 계정이 없으면
만들고, 매장에 잇고, 6자리 로그인 코드를 화면에만 찍는다(메일은 보내지 않는다):

```bash
cd ~/Dev/Mirrorball && .venv/bin/python worker/login_code.py 이메일 매장
```

```bash
cd ~/Dev/Mirrorball && CONFIRM=1 .venv/bin/python worker/login_code.py 이메일 매장
```

- 나온 코드를 불러 드린다 → 디자이너님은 앱 로그인 화면에서 이메일 → **코드를 이미 받았다면 입력하기** → 코드. 매장이
  이미 이어져 있어 바로 자기 매장이 열린다('다시 확인' 단계가 없다).
- 코드는 한 번만 · 1시간 안에. 새로 만들면 앞의 코드는 못 쓴다. 나중에 로그인이 풀렸을 때도 같은 명령이다(이미 이어진
  계정이면 코드만 나온다 — 매장 이름은 빼도 된다).
- 메일로도 코드가 가게 하려면(선택): 메일 설정(SMTP) + 메일 양식 두 개 — `supabase/email_templates/README.md`.

- 누가 어느 매장에 이어져 있나(이메일은 가려서):

```bash
cd ~/Dev/Mirrorball && .venv/bin/python worker/link_designer.py --list
```

- 기다리다 '데모로 둘러보기'를 눌렀던 계정도, 실제 매장을 이으면 실제 매장이 먼저 열린다.
- 이미 다른 실제 매장에 이어진 계정은 막힌다 — 정말 둘 다 이을 때만 앞에 `MULTI=1`.

## 3. 운영자 폰 · 운영 숫자

- **운영자 폰 표시**: 운영자 폰(PC 로도 보면 거기서도)에서 앱 주소 끝에 `/settings?op=1` 을 붙여 한 번 연다('이 폰은 운영자 폰' 알림). 풀 때는 `?op=0`.
  - 그 폰에서 연 화면은 디자이너 사용 수에서 빠진다(화면 속도엔 남는다).
  - 설정 맨 아래에 **운영 숫자** 버튼이 생긴다(디자이너 화면엔 없다). `0027` 뒤엔 운영자 계정(§4 `ops_add_reader`)일 때만.
- **운영 숫자(`/ops`)**: 매장별 디자이너 화면 수 · 앱으로 연 비율 · 연락한 손님 수 · 마지막 사용 · 운영자 폰 화면 수, 화면별 속도(지난 7일). 매일 감시와 같은 숫자다. 손님 정보는 없다.
  - `0027` 전엔 운영자 폰 표시(쿠키)로 열린다 — 누구나 켤 수 있는 표시라, `0027` 뒤엔 **운영자 계정**으로 로그인했을 때만 열린다.
- **디자이너님이 직접 고르는 것**: 설정 → 연락 버튼(💬 문자 / 📤 카톡 등), 휴무.

## 4. SQL(마이그레이션) 이력

Supabase → SQL Editor 에서 `supabase/migrations/` 파일을 번호 순서대로 실행한다. 모두 다시 돌려도 안전하게 만들어져 있다.

| 파일 | 무엇 | 실행 |
|---|---|---|
| `0001` ~ `0021` | 기본 표 · 보안(RLS) · 손님 · 거래 · 예약 · 성별 등 | 실행됨(앱이 돌고 있다) |
| `0022_sync_health.sql` | 수집 감시 함수 | 실행됨(매일 감시가 쓴다) |
| `0023_ops_events.sql` | 백업 · 화면 오류 기록 | 실행됨 |
| `0024_speed_usage.sql` | 화면 속도 · 매장별 사용 · 매장 통계 저장 | 실행됨(2026-10-15) |
| `0025_usage_designer.sql` | 사용 수는 디자이너 것만 · 기록 시작 | **확인** — 운영 숫자 맨 위에 '화면 기록 ○○부터'가 보이면 실행된 것 |
| `0026_csp_reports.sql` | 보안 정책(CSP) 어긋남 기록 — 한 주 '보고만' 동안 | **실행 필요**(v14) — 운영 숫자 '보안 정책' 칸이 '어긋남 없음'이나 목록으로 보이면 실행된 것 |
| `0027_ops_lock.sql` | 운영 숫자 문단속 — 공개 키로는 안 보이게(운영자 계정 · 감시 열쇠만) | **실행 필요**(v15) — 아래 세 단계를 한 번에 |

새 SQL 이 생기면 이 표에 한 줄 더한다.

**`0027` 세 단계** — 0025 · 0026 을 먼저 실행한 뒤, 같은 SQL Editor 에서 이어서 한다. 하나라도 빠지면 매일 감시가 빨갛게 끝나거나
운영 숫자 화면이 안 열린다(조용히 넘어가지 않게 했다).

1. `0027_ops_lock.sql` 실행
2. 감시 열쇠 만들기 — 아래 한 줄이 열쇠를 **한 번만** 보여 준다(DB 엔 해시만 남는다). 그 값을 GitHub → 저장소 → Settings →
   Secrets and variables → Actions → **New repository secret**, 이름 `OPS_WATCH_KEY` 에 붙여 넣는다. 서비스 키가 아니라 운영
   숫자만 여는 열쇠다. 채팅 · 문서엔 붙여 넣지 않는다. 다시 만들면 앞의 열쇠는 못 쓴다(GitHub 값도 새로).

```sql
select public.ops_new_watch_key();
```

3. 운영자 계정 — 운영자님이 앱에 로그인하는 이메일로(따옴표 안만 바꾼다):

```sql
select public.ops_add_reader('운영자 이메일');
```

- 확인: 다음 매일 감시가 초록이고, 운영자 폰에서 설정 → 운영 숫자가 열리면 끝. 다른 계정에선 운영 숫자 버튼이 사라진다.

## 5. 맥에서 할 일

- **코드 받기** — 맥 쪽 기능(백업 · 연결 스크립트 · 사용 현황)이 바뀌었을 때. **2026-10-18 일요일 14시 수집 전에 한 번 꼭**(첫 백업 — 안 하면 10.20부터 감시가 '백업 없음'으로 실패한다):

```bash
cd ~/Dev/Mirrorball && git pull origin claude/charming-planck-hmgazi
```

- **사용 현황**(매장별 계정 수 · 마지막 로그인 · 연락 수 — 이름 · 이메일 없음):

```bash
cd ~/Dev/Mirrorball && .venv/bin/python worker/usage_probe.py
```

- 수집은 launchd(`com.mirrorball.collect`)가 일요일에 돌린다 — 손댈 것 없음. 확인은 `DEPLOY.md` 의 `launchctl list | grep mirrorball`.
- **열쇠 한 부**(한 번, v15) — `web/.env.local` 의 `MIRRORBALL_KEK` 값을 비밀번호 관리자(아이폰 '암호' 앱 · 1Password 등)에
  한 부 둔다. 채팅 · 문서 · 메신저엔 붙여 넣지 않는다. 그다음 맞게 적었는지 — 매장마다 '매장 열쇠 풀림', 비밀번호 관리자
  값을 붙여 넣으면 '같아요'(값은 화면에 안 보이고 어디에도 찍히지 않는다):

```bash
cd ~/Dev/Mirrorball && .venv/bin/python worker/kek_check.py
```

  열쇠를 바꾸면(`playbook/KEY_ROTATION.md`) 비밀번호 관리자 값도 새 열쇠로 바꾸고 다시 확인한다.

## 6. 문제가 생기면

| 증상 | 먼저 볼 곳 | 할 일 |
|---|---|---|
| 감시 메일 — 수집 지연(8일 넘음) | 맥이 켜져 있나 · 잠자기 | 맥을 깨우고 수동 수집: `cd ~/Dev/Mirrorball && FORCE=1 bash worker/run_mac.sh` |
| 감시 메일 — 백업 없음 · 늦음 | 맥의 코드가 최신인가(§5 코드 받기) | 코드를 받고 다음 일요일을 기다리거나, 수동 수집(백업이 따라 돈다) |
| 감시 메일 — 화면 오류가 많음 | 운영 숫자 · 디자이너님께 어느 화면인지 | 화면 이름(경로)을 알려 주시면 고친다 — 오류 기록엔 손님 정보가 없다 |
| 자동 검증(`test`) 메일 — 빨강 | GitHub → Actions → test | 그대로 알려 주시면 고친다(배포된 앱은 그 전 상태로 돈다) |
| 취약점 점검(`deps-audit`) 메일 — 빨강 | GitHub → Actions → deps-audit 의 '받아들이지 않은' 줄 | 그대로 알려 주시면 의존성을 올린다 |
| 감시 메일 — '감시 열쇠' 조회 실패(HTTP 401) | GitHub 비밀값 `OPS_WATCH_KEY` | §4 `0027` 2단계 — 열쇠를 다시 만들어 GitHub 값을 바꾼다 |
| 손님 이름이 '고객'으로만 보임 | 매장 키(`dek_wrapped`) · 맥 `.env.local` 의 KEK | `playbook/KEY_ROTATION.md` |
| 데이터를 되살려야 함 | 백업 파일 | 미리보기 `.venv/bin/python worker/backup.py --restore 파일` → 확인 뒤 `--apply` |
| 맥이 고장 나거나 없어짐 | 비밀번호 관리자의 열쇠 한 부 | 아래 '맥이 없어지면' 순서. 앱은 Cloudflare 에 있는 열쇠로 그대로 돈다 |

### 맥이 없어지면

앱 · 매일 감시는 그대로 돈다. 멈추는 것은 일요일 수집 · 백업뿐이다. 손님 데이터의 원본은 DB 이고, HandSOS 접속 정보 ·
매장 열쇠는 열쇠(KEK)로 감싸서 DB 에 있다 — 그래서 열쇠 한 부만 있으면 새 맥에서 모두 되살아난다.

1. 새 맥에 저장소를 받고 파이썬 환경을 만든다:

```bash
mkdir -p ~/Dev && cd ~/Dev && git clone https://github.com/yhlee217/Mirrorball.git
```

```bash
cd ~/Dev/Mirrorball && python3 -m venv .venv && .venv/bin/pip install -r worker/requirements.txt && .venv/bin/python -m playwright install chromium
```

2. `web/.env.local` 을 채운다 — Supabase 주소 · 공개 키 · 서비스 키는 Supabase 대시보드(설정 → API)에서, `MIRRORBALL_KEK` 는
   비밀번호 관리자에서. 키 값은 그 파일에만 넣는다.
3. 열쇠가 맞는지(§5 `kek_check.py`) → 수집 한 번(`FORCE=1 bash worker/run_mac.sh`) → 일요일 자동 실행 다시 걸기
   (`bash scripts/mac/install_schedule.sh collect`, `DEPLOY.md` A-2).
4. 백업은 다음 일요일부터 다시 쌓인다. Cloudflare · GitHub 는 손대지 않는다.

## 7. 남은 운영자 확인(계획서에서 이어짐)

- **열쇠 한 부**(v15 P1) — 비밀번호 관리자에 `MIRRORBALL_KEK` → 맥에서 `kek_check.py`(§5)
- **`0026` SQL**(v14 P0) — CSP 어긋남 기록. 실행 전엔 기록만 조용히 건너뛴다
- **`0027` SQL**(v15 P2) — 운영 숫자 문단속. 세 단계(§4) — SQL · 감시 열쇠를 GitHub 비밀값에 · 운영자 이메일 한 줄
- HandSOS 고객 화면에 **생일** 칸이 있나 — 칸 이름만(v13 P3)
- HandSOS 에서 **엑셀 내보내기**(예약 · 매출)가 되나 — 열 이름만(v8 P3)
- 디자이너님들께 — 손님께 연락할 때 주로 **문자 / 카톡**(v11)
- 키 교체 · 개인정보 처리방침 초안(v5)
