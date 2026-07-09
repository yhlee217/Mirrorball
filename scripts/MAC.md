# macOS 설치·실행 가이드

Windows 와 **Python 코드는 동일**(크로스플랫폼). 다른 건 러너/스케줄뿐이라 이 문서만 따르면 된다.
명령의 백슬래시(`\`)는 Mac 에선 슬래시(`/`).

## 0. 준비 (1회)
```bash
git clone <repo> Mirrorball && cd Mirrorball
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # 없으면: pip install playwright pyyaml
python -m playwright install chromium   # 스크래핑 브라우저
# (AI 측정·자가치유용) Claude CLI 설치 후 로그인해두면 좋음
```

## 1. 자격증명 (Windows 와 동일 파일)
```bash
cp secrets/stores.example.yaml secrets/stores.yaml   # 회사코드·아이디·비번 + designers 매핑
cp secrets/naver.example.yaml  secrets/naver.yaml     # 발견케어용(선택)
```

## 2. 수동 실행 (돌아가는지 눈으로)
```bash
python scripts/handsos_sync.py --only hayewoni --headed --all-designers   # 화면 보며
python scripts/handsos_sync.py --only hayewoni --all-designers            # 창 없이
python onboard.py --salon 살롱톤 --region 영등포시장역                       # 디자이너 서비스 세팅
```

## 3. 매일/매주 자동 (launchd)
```bash
chmod +x scripts/mac/*.sh
scripts/mac/install_schedule.sh            # 핸드SOS(매일 03:10) + 노출(매주 월 09:00)
scripts/mac/install_schedule.sh handsos    # 핸드SOS만
scripts/mac/install_schedule.sh uninstall  # 해제
```
- 확인: `launchctl list | grep mirrorball`
- 즉시 1회: `launchctl start com.mirrorball.handsos`
- 로그: `sync.log`, `runs/handsos.err.log`
- 시각 변경: `scripts/mac/com.mirrorball.handsos.plist` 의 `Hour/Minute`(핸드SOS) ·
  `Weekday/Hour`(노출) 수정 후 `install_schedule.sh` 재실행.

## 참고
- **Mac 이 그 시각 깨어 있어야** 함. 잠자기(sleep)면 깨어난 뒤 밀린 작업을 실행하지만,
  완전 종료면 실행 안 됨. 항상 켜두기 어려우면 시각을 영업시간대로.
- launchd 가 `claude` CLI 를 못 찾으면(자가치유·AI측정) plist 의 `PATH` 에 설치 경로 추가
  (`which claude` 로 확인). CLI 인증이 launchd 에서 안 잡히면 **사용자 crontab** 대안:
  ```
  crontab -e
  10 3 * * *  /경로/Mirrorball/scripts/mac/run_sync.sh --all-designers
  0  9 * * 1  /경로/Mirrorball/scripts/mac/run_expose_auto.sh hayewoni
  ```
- 데이터·시크릿은 Windows 와 동일하게 로컬 전용(git 제외).
