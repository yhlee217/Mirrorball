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

키는 **git 에 올라가는 `targets/` 에 넣지 말 것.** 환경변수로 준다:

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

## 4. 지금 측정되는 것 / 아직인 것

| 차원 | 방법 | 상태 |
|---|---|---|
| AI 발견(언급·경쟁사) | Claude CLI | ✓ 키 0 |
| 네이버 발견·순위 | 지역검색 OpenAPI | ✓ 무료 키 |
| 플레이스 리뷰·사진 수 | (공식 API 없음) | 미측정 — 플레이스 페이지 스크랩 필요(후속) |
| 블로그 후기 수 | (후속) | 미측정 |

플레이스 리뷰·사진은 공식 API 가 주지 않아, 정확 수치는 플레이스 페이지 스크랩(온머신, 후속)
또는 사람이 `targets/{slug}.yaml` 의 `place: {reviews, photos, comp_reviews_median}` 에 직접 적어도 된다.

## 5. 매일/주간 자동화

핸드SOS 동기화 옆에 같이 걸면 된다(예: 주 1회):
```
python expose.py clients\hayewoni --measure
python build_app.py clients\hayewoni
```
추세(history)가 쌓여 '발견 점수가 오르는지' 가 곧 컨시어지의 성과 증명이 된다.
