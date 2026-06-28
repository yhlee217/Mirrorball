# 발견 케어(노출) 측정 가이드

손님이 "영등포 레이어드컷 잘하는 곳" 을 **AI 에 묻거나 네이버에 검색**할 때
하예원/살롱톤이 보이는가? 를 측정 → 발견 점수 → 이번 주 할 일 → 추세.

```
expose_collect.collect(target)
  ├─ AI:    질문을 Claude CLI(`claude -p`, 키 0)에 던져 언급/경쟁사 추출
  └─ 네이버: 지역검색 OpenAPI(무료 키, JSON) — 발견/순위. 키 없으면 스크랩 폴백.
       ▼
expose.build_exposure → clients/{slug}/exposure.yaml → 앱 '노출' 탭
```

**정직성 원칙**: 측정한 차원만 점수에 넣는다. 안 잰 것(플레이스 리뷰·사진 등)은
0 으로 단정하지 않고 **'미측정'** 으로 표시한다.

---

## 1. 네이버 지역검색 OpenAPI 키 (무료 · 5분)

스크래핑보다 안정적이라 이걸 1순위로 쓴다(셀렉터 깨짐·봇탐지 없음).

1. https://developers.naver.com → 로그인 → **Application > 애플리케이션 등록**
2. 사용 API: **검색** 선택, 환경: WEB(아무 URL) → 등록
3. **Client ID / Client Secret** 발급 (무료, 일 25,000회)

키는 **`secrets/naver.yaml`(git 제외)** 에 넣는 게 제일 쉽다:

```powershell
copy secrets\naver.example.yaml secrets\naver.yaml
notepad secrets\naver.yaml   # client_id / client_secret 채우기
```

또는 환경변수로 줘도 된다:

```powershell
# Windows (현재 세션)
$env:NAVER_CLIENT_ID="발급ID"
$env:NAVER_CLIENT_SECRET="발급Secret"
# 영구 등록:  setx NAVER_CLIENT_ID "발급ID"   (새 창부터 적용)
```
```bash
# Linux/Mac
export NAVER_CLIENT_ID=발급ID
export NAVER_CLIENT_SECRET=발급Secret
```

키가 없으면 자동으로 네이버 검색 스크랩으로 폴백(덜 안정적).

## 2. 질문 정하기

`targets/{slug}.yaml` 의 `questions` — **손님이 실제로 AI/검색에 칠 문장**(사람이 확정).
designer/salon 의 name·aliases(인스타 핸들 포함)도 정확히. 예: `targets/hayewoni.yaml`.

## 3. 측정 실행

```powershell
python expose.py clients\hayewoni --measure
```
- Claude CLI 가 깔려 있으면 AI 측정 자동, 네이버는 위 키로 측정.
- 결과: 발견 점수 + 이번 주 할 일이 콘솔과 `clients\hayewoni\exposure.yaml` 에.
- 점수 없이(기존 측정값으로 점수·처방만): `python expose.py clients\hayewoni`

빌드/앱 반영: `python build_app.py clients\hayewoni` → 노출 탭에서 확인.

## 4. 지금 측정되는 것

| 차원 | 방법 | 플래그 |
|---|---|---|
| AI 발견(샵·디자이너 언급·경쟁사) | Claude CLI | `--measure` |
| 네이버 발견·순위(지역×시술) | 지역검색 OpenAPI | `--measure` |
| **실제 지도 순위(콜드·미용실만)** | 플레이스 리스트 스크랩 | `--rank` |
| 플레이스 리뷰·사진·인기스타일 | 플레이스 페이지 스크랩 | `--place` |
| 키워드별 순위 변화(지난주 대비) | history 스냅샷 비교 | 자동 |

- `--rank`: 지역검색 API 는 상위 5곳만 줘서 '미노출'을 과장 → 실제 지도 리스트(40곳)에서
  미용실만 남겨 진짜 순위를 본다(8위면 8위로 정직하게). 느림.
- `--show`: 디버그(브라우저 보임 + 순위 리스트 출력). **자동 실행에는 쓰지 말 것**(headless 아님).

## 5. 주 1회 자동화 (Windows 작업 스케줄러)

변화 데이터(미노출→12위 같은)는 **꾸준히 측정해야** 쌓인다 → 주 1회 자동 측정을 건다.

```powershell
# 관리자 PowerShell 에서 1회 등록 (기본: 매주 월 09:00, hayewoni)
powershell -ExecutionPolicy Bypass -File scripts\win\register_expose_task.ps1
# 요일·시각·대상 바꾸려면:
powershell -ExecutionPolicy Bypass -File scripts\win\register_expose_task.ps1 -Day Monday -Time 09:00 -Slug hayewoni
```

- 스케줄러는 **`run_expose_auto.bat`**(headless, `--measure --place --rank`)을 돌리고 `expose.log` 에 기록.
- 끝나면 `clients\{slug}\kakao.txt` 에 그 주 카톡 문구가 갱신된다 → 그대로 디자이너께 전송.
- 확인: `schtasks /Query /TN Mirrorball-Expose-Weekly /V /FO LIST` · 즉시 실행: `schtasks /Run /TN Mirrorball-Expose-Weekly`
- PC 가 그 시각에 **켜져 있어야** 한다(절전은 깨우지만 완전 종료는 못 깨움).

수동 측정(브라우저 보면서)은 그대로 `scripts\win\run_expose.bat`.
