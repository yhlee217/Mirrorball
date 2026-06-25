# 음성 메모 자동 파이프라인 — 녹음만 하면 카르테에 들어가게

> 목표: 사람 손 최소. 녹음 시작할 때 **고객 이름 한마디**만 하면, 나머지는 자동.
> 핵심: **Claude 는 음성을 못 바꾼다(STT 불가)** → 변환은 무료 Whisper, 요약만 Claude.

## 흐름
```
폰 녹음(이름 한마디로 시작)
   │  ① iCloud Drive / Google Drive 폴더로 자동 동기화 (1회 설정)
   ▼
Mac 의 watcher (voicenote.py watch)
   │  ② Whisper 로컬 변환(무료·무제한)
   │  ③ Claude 요약·구조화 → {이름, 메모, 태그, 다음 할 일}
   │  ④ 고객 매칭 → 카르테 메모 누적 + 태그 병합 + 앱 데이터 재빌드
   ▼
앱 카르테에 자동 반영 (처리한 파일은 _done/ 으로 이동)
```

## 비용
- 녹음(폰 기본앱)·클라우드 동기화·STT(로컬 Whisper) = **0원**
- 요약 = **Claude**(쓰시는 그 AI). 메모 1건당 토큰 소량.

## 1회 설정 (Mac)
```bash
pip install faster-whisper          # 무료 로컬 STT
export ANTHROPIC_API_KEY=...        # Claude 요약용 (없으면 prompt 모드로 수동)
# 폰 녹음이 떨어지는 클라우드 폴더를 Mac 에서 동기화해 두기 (iCloud Drive 추천)
```

## 운영
```bash
# 폴더 감시 — 새 녹음이 오면 자동 처리
python voicenote.py watch ~/Library/Mobile\ Documents/.../VoiceNotes --client clients/hayewoni

# 한 파일만 처리
python voicenote.py process 메모.m4a --client clients/hayewoni

# 이미 텍스트면(예: iOS18 음성메모 자동 텍스트) 변환 건너뛰고 반영
python voicenote.py apply transcript.txt --client clients/hayewoni

# 키 없이 수동: 프롬프트만 받아 Claude 에 붙여넣기
python voicenote.py prompt transcript.txt
```

## "매번 STT 돌리는" 불편 없애기 — 상시 자동
`watch` 는 **한 번 켜두면 끝**. 새 녹음이 폴더에 들어오는 즉시 자동 변환·요약·반영된다(매 파일 수동 실행 X).
- **속도**: Whisper 모델은 시작 때 한 번만 로드 → 이후 각 녹음은 추론만(짧은 메모 몇 초). 동기화 지연 포함 보통 1분 이내.
- **항상 켜두기(로그인 시 자동 시작·죽으면 재시작)**: `scripts/voicenote.launchd.plist` 의 `{PROJECT}/{FOLDER}/{SLUG}/{ANTHROPIC_API_KEY}` 를 채워
  `~/Library/LaunchAgents/` 로 복사 후 `launchctl load`. → Mac 이 켜져 있는 동안 늘 감시.

## 사람이 하는 일 (최소)
1. 시술 끝나고 **녹음 시작 → "김문규님, 오늘 다운펌 …"** 처럼 이름부터 말하기
2. 끝. (launchd 로 watcher 를 등록해두면 STT 를 **단 한 번도 직접 돌리지 않는다**)

> "녹음하자마자 즉시"는 아니다(동기화+처리 수초~1분). 진짜 즉시가 필요하면 → 앱의 🎤 실시간 받아쓰기(클라우드·Mac 불필요).

## 매칭·안전장치
- 말한 이름으로 고객 **자동 매칭**(정확→부분 일치). 못 찾으면 건너뛰고 사유 출력(임의 기입 안 함).
- 요약은 **사실만**(없는 내용 생성 금지). 메모는 날짜와 함께 **누적**, 태그는 취향에 **중복 없이 병합**.
- 오디오 원본은 폰·클라우드에만. 카르테엔 텍스트만.

## 대안 (Mac 상시 가동이 어려우면)
- **iOS 18 음성 메모**가 자체적으로 텍스트를 만들어 줌 → 그 텍스트를 `apply` 로 넣으면 Whisper 불필요.
- 또는 우리 앱의 실시간 받아쓰기(🎤)로 즉석 메모 — 클라우드·Mac 없이 가장 간단.
