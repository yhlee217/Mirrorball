# 키 교체 순서표 — 서비스 키 · 마스터 키(KEK)

> 개선 계획 v5 P0. `LAUNCH.md`에 '채팅에 노출된 서비스 키·KEK' 교체가 체크되지 않은 채 남아 있었다. 노출된 적이 있으면 아래 둘을 다 한다. 노출이 없었어도 1년에 한 번쯤은 같은 순서로 바꾼다.
>
> ⚠ **키 값은 어디에도 붙여넣지 않는다** — 채팅·이슈·커밋·메신저 모두. 화면에 띄운 키는 그 자리에서 바로 붙여넣고 지운다.

## 키가 있는 곳

| 키 | 맥 `web/.env.local` | Cloudflare Pages(설정 → 환경 변수) | GitHub(Settings → Secrets) |
|---|---|---|---|
| `SUPABASE_SERVICE_ROLE_KEY` — DB 전체 접근(RLS 우회) | ✓ 수집 · 백업 · 점검 스크립트 | ✓ 설정 저장(`/api/settings`) | ✓ `collect.yml`(수동 실행용) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` — 공개 키(로그인 전 화면) | ✓ | ✓ | `SUPABASE_ANON_KEY`(sync-health) |
| `MIRRORBALL_KEK` — 손님 이름·전화를 푸는 열쇠의 열쇠 | ✓ | ✓ | ✓ `collect.yml` |

## 1. 서비스 키 교체 (먼저 — 이게 DB 문을 닫는다)

1. 일요일 14시 수집 시간을 피한다(평일 낮이 좋다).
2. Supabase 대시보드 → 프로젝트 설정 → API(키) 화면에서 서비스(비밀) 키를 새로 만들고 옛 키를 폐기한다.
   - 화면이 옛 방식(JWT 비밀값 하나로 anon·service 키를 함께 만드는 방식)이면 비밀값을 새로 만들면 **anon 키도 함께 바뀌고 모두 다시 로그인**해야 한다 — 그럼 아래 표의 anon 키도 세 곳 다 바꾼다.
3. 새 키를 세 곳에 넣는다: 맥 `web/.env.local` → Cloudflare 환경 변수 → GitHub 비밀값.
4. Cloudflare 는 환경 변수를 바꾼 뒤 **다시 배포**해야 적용된다(배포 목록에서 최신 배포 '다시 시도' 또는 빈 커밋 푸시).
5. 확인: 앱 로그인 → 설정에서 아무 값이나 저장 → 맥에서 `FORCE=1 bash worker/run_mac.sh`(수집 1회) → GitHub Actions 에서 sync-health 수동 실행이 초록인지.

## 2. 마스터 키(KEK) 교체

봉투 암호화라 손님 이름·전화는 다시 암호화하지 않는다 — 매장 키(DEK) · HandSOS 접속 정보 · 백업 파일만 새 KEK로 다시 감싼다. 교체하는 동안 앱과 수집은 **옛 키로도 읽는다**(`MIRRORBALL_KEK_OLD`) — 이름이 '고객'으로 보이는 순간이 없다.

1. 맥 터미널에서 새 키를 만든다: `openssl rand -base64 32`
2. 세 곳 모두 이렇게 바꾼다(지금 키는 `_OLD` 로 옮기고, 새 키를 원래 이름에):
   - `MIRRORBALL_KEK_OLD` = 지금 키
   - `MIRRORBALL_KEK` = 새 키
   - Cloudflare 는 바꾼 뒤 다시 배포.
3. 앱에서 손님 이름이 그대로 보이는지 확인한다(옛 키로 읽는 중).
4. 맥에서 미리 보기 → 바꾸기:
   ```bash
   cd ~/Dev/Mirrorball && .venv/bin/python worker/rotate_kek.py
   .venv/bin/python worker/rotate_kek.py --apply
   ```
   매장마다 '다시 감쌈 · 이름 20/20 풀림', 접속 정보 '다시 감쌈', 백업 파일 'N개'가 나오고 X 줄이 없어야 한다.
5. 앱에서 이름이 보이는지 다시 확인한 뒤, 세 곳에서 `MIRRORBALL_KEK_OLD` 를 **지운다**(Cloudflare 는 다시 배포). 옛 키는 어디에도 남기지 않는다.
6. 확인: 맥에서 수집 1회(`FORCE=1 bash worker/run_mac.sh`) — 로그인·저장이 되면 접속 정보도 새 키로 풀린 것이다.

### 알아둘 것
- 옛 키가 이미 새 나갔고 그 사이 누군가 DB 를 통째로 가져갔다면, 그 사본은 옛 키로 여전히 풀린다. 교체는 **앞으로의** 접근을 막는다 — 그래서 서비스 키(1번)를 먼저 바꾼다.
- 멈추면: X 가 나온 매장은 건드리지 않았다. `MIRRORBALL_KEK_OLD` 를 지우지 말고 출력 그대로 확인한다. 같은 명령을 다시 돌려도 안전하다(이미 새 키인 것은 '이미 새 키'로 건너뛴다).
