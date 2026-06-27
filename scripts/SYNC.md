# 핸드SOS 자동 동기화 가이드

핸드SOS는 개인용 공개 API가 없습니다. 그래서 "항상 동기화"의 현실적 형태는
**로그인된 헤드리스 브라우저를 스케줄로 돌리는 배치**입니다(매일 새벽 1회 → 다음날 아침 최신).
업종 특성(다음날 케어)에는 이걸로 충분합니다.

```
[항상 켜진 머신] ── cron(새벽) ──▶ handsos_sync.py
  매장별: 로그인(회사코드+id+pw) → 매출상세목록 → harvest.js 수확
        → CSV(_raw, 감사용) → import_handsos(카르테·관계 보존) → build_app
        → 실패(0행·로그인) 시 알림
```

매 실행마다 **새로 로그인**합니다(세션 유지 X) — 여러 매장을 각자 계정으로 깔끔하게 관리하기 위해서.

---

## 1. 하드웨어 (24시간 켜둘 머신)

| 후보 | 가격(대략) | 전력 | 비고 |
|---|---|---|---|
| **Intel N100 미니PC** ⭐ | 15~20만원 | idle 6~10W | x86라 Playwright 호환 안정적·헤드룸 충분. **다중 매장 1순위** |
| 라즈베리파이 5 (8GB) | 12~15만원(+케이스·전원) | ~5W | 저전력·저가. ARM Chromium 동작. 소수 매장에 적합 |
| 안 쓰는 노트북 | 0원 | 가변 | 배터리가 UPS 역할. 있으면 테스트용으로 충분 |

권장: **N100 미니PC + Ubuntu/Debian**. 전기료 월 몇백 원, 매장 수십 곳도 무난.
클라우드 VM은 비권장 — 데이터센터 IP 차단 가능 + 로그인 자격증명/고객 PII가 외부 서버에 상주.

---

## 2. 설치

### Windows (지금 쓰는 경로)
1. **Python 3.11+** 설치 (python.org, 설치 시 "Add python.exe to PATH" 체크)와 **Git** 설치.
2. PowerShell 에서:
   ```powershell
   git clone <이 저장소> mirrorball
   cd mirrorball
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install playwright pyyaml
   playwright install chromium
   ```
   (`Activate.ps1` 이 막히면 한 번만: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`)

### Ubuntu/Debian (전용 미니PC/파이)
```bash
sudo apt update && sudo apt install -y python3 python3-venv git
git clone <이 저장소> mirrorball && cd mirrorball
python3 -m venv .venv && . .venv/bin/activate
pip install playwright pyyaml
playwright install --with-deps chromium
```

## 3. 매장 설정

```bash
cp secrets/stores.example.yaml secrets/stores.yaml   # secrets/ 는 git 제외됨
```
`stores.yaml` 에 매장별 **회사코드·아이디·비번**과 **로그인 화면 셀렉터**를 채웁니다.
셀렉터는 한 번만 확인하면 됩니다(아래 4번).

매장 실데이터(`clients/<slug>/`)는 PII이므로 `.gitignore` 에 한 줄 추가:
```
clients/<slug>/
```

## 4. 매출상세목록 위치 잡기 (최초 1회 / 매장당)

**로그인 셀렉터는 핸드SOS 공통이라 이미 채워져 있습니다**(`#companyID`/`#userID`/`#userPWD`/`#sendLogin`).
남은 건 로그인 후 "매출상세목록" 화면의 위치(URL)를 한 번 잡는 것뿐:

```bash
python scripts/handsos_sync.py --only <slug> --headed --debug
```
- 자동으로 로그인됩니다. 창에서 **매출분석 → 매출상세목록**으로 이동하고, 기간을
  '전체'로 조회해 표가 보이면 **Enter**.
- 그러면 콘솔에 **현재 URL 과 frame URL 목록**이 찍힙니다. 그중 매출상세목록이 든
  주소를 `stores.yaml` 의 `report.url` 에 넣으면 다음부터 자동으로 그 화면을 엽니다.
- 직접 URL이 프레임 구조라 안 통하면 `report.nav` 에 메뉴 클릭 시퀀스를 넣습니다
  (창에서 메뉴 우클릭 → 검사 → 셀렉터 확인).

잡은 뒤 실제 동기화 테스트:
```bash
python scripts/handsos_sync.py --only <slug> --headed   # 눈으로 확인(자동 수확)
python scripts/handsos_sync.py --only <slug>            # 헤드리스
```

## 5. 스케줄 (매일 새벽 1회)

### Windows — 한 줄로 등록
관리자 PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\win\register_task.ps1          # 매일 03:10
powershell -ExecutionPolicy Bypass -File scripts\win\register_task.ps1 -Time 02:30
```
- 등록되는 작업 이름: **Mirrorball-HandSOS-Sync** (`scripts\win\run_sync.bat` 실행, 로그 `sync.log`).
- 즉시 테스트: `schtasks /Run /TN Mirrorball-HandSOS-Sync`
- **전원 설정**: 제어판 → 전원 옵션에서 **절전 안 함**(또는 절전이라도 `-WakeToRun`이 깨움).
  완전 종료 상태면 안 도니, 상시 켜두거나 절전까지만.
- 로그인 없이 돌리려면 작업 스케줄러 GUI에서 "사용자 로그온 여부와 관계없이 실행"으로 변경.

### Linux(cron) — 전용 미니PC/파이
```cron
10 3 * * * cd /home/<user>/mirrorball && /home/<user>/mirrorball/.venv/bin/python scripts/handsos_sync.py >> /home/<user>/mirrorball/sync.log 2>&1
```
머신이 새벽에 꺼져 있으면 안 됩니다(상시 ON 권장).

## 6. 모니터링

- `handsos_sync.py` 는 매장별 결과를 출력하고, **실패가 있으면 종료코드 1** + `notify_url`
  (슬랙/디스코드 webhook)로 알림을 보냅니다.
- 실패 신호: **0행 수확**(로그인 만료 또는 핸드SOS UI 변경), 로그인 단계 예외.
- UI가 바뀌면 셀렉터/수확이 깨질 수 있으니, 알림이 오면 `--headed --debug`로 점검하세요.
- 수확 원본은 `clients/<slug>/_raw/handsos_*.csv` 에 타임스탬프로 남습니다(감사·복구용).

## 7. 데이터 안전 & 약관

- 자격증명·고객 PII는 **이 머신 로컬에만** 존재(secrets/, clients/, _raw/ 모두 git 제외).
- 가져오는 데이터는 **그 매장 자신의 데이터**지만, 자동 스크래핑은 핸드SOS 약관에
  저촉될 수 있습니다. 미용사 본인의 **자격증명 공유 동의**를 받고 진행하세요.
  공식 내보내기(스케줄 export)가 생기면 그쪽이 더 안전합니다.

## 8. 증분 동기화(선택)

매 실행 전체를 긁으면 매장 서버에 부담이 됩니다. `report.date_range_days: 30` 처럼
최근 N일만 가져오고, 주 1회 정도 `0`(전체)로 보정하면 가볍습니다.
import 는 고객번호+날짜로 **중복 제거**하고 기존 카르테(메모·가족관계)를 **보존**하므로,
겹쳐 가져와도 안전합니다.
