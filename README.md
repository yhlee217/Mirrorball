# Mirrorball — 미용사 1인 컨시어지 도구 모음

헤어 디자이너를 위한 1인 컨시어지 운영자용 **내부 도구**. SaaS가 아니라
파일 기반 CLI 스크립트 모음이며, 서버·DB·웹UI·스케줄러 없이 동작한다.

전부 **하나의 디자이너 데이터**에서 파생되고 **프로필 페이지를 허브**로 묶인다.
(구조 한눈에: `mockups/service_map.html` / 모바일: `mockups/service_map_mobile.html`)

| 시스템 | 무엇 | 핵심 산출물 |
|---|---|---|
| **① 프로필 빌더** | YAML → 호스팅 프로필 정적 사이트 | `dist/{slug}/index.html` |
| **② AI 노출 케어** | AI 검색 노출 진단·개선·증명 | `runs/`, `content/` 리포트·콘텐츠 |
| **③ 카드 생성기** | 손님용 공유 카드(애프터케어 등) | `dist/cards/{name}.html` |

## 설치

```bash
pip install -r requirements.txt
cp .env.example .env   # ② 진단/콘텐츠에 쓸 API 키 (① ③ 은 키 불필요)
```

Python 3.11+, Windows/WSL 동작. 출력물(`dist/`, `runs/`, `content/`)은 `.gitignore`.

---

## ① 프로필 빌더 — 호스팅 프로필 정적 사이트

기준 디자인(`templates/profile.html.j2`)은 손으로 만든 원본 HTML을 그대로 옮긴 것이고,
값만 변수화한다. 데이터가 있을 때만 나타나는 **선택 모듈**로 기능을 얹어, 모듈이 없으면
출력이 원본과 byte-identical 로 유지된다.

```bash
python build.py designers/hayewoni.yaml   # 한 명 → dist/hayewoni/index.html
python build.py --all                      # designers/*.yaml 전부 + sitemap/robots
```

- 입력: `designers/{slug}.yaml` (전체 예시: `designers/minji.yaml`)
- 자동: schema.org JSON-LD(Person·FAQPage), `<title>`/`description`, OG/Twitter 메타
- 선택 모듈: `portfolio`(전후 갤러리)·`menu`(메뉴판)·`reviews`(후기)·`style_quiz`(스타일 찾기)
- 배포: `dist/` 를 Netlify drop / GitHub Pages 에 수동 업로드 (자동배포 없음)

핵심 코드: `build.py`(CLI) · `core.py`(`render(data)->str`) · `schema.py` · `validate.py`

---

## ② AI 노출 케어 — 진단·개선·증명

디자이너가 AI 검색(ChatGPT·Gemini·Perplexity)에서 어떻게 노출되는지 측정하고 개선한다.
키가 있는 provider만 자동 활성화(`.env`), 리포트는 `REPORT_PROVIDER`(기본 gemini).

```bash
python diagnose.py targets/example.yaml    # 질의 → runs/{slug}/{시각}/raw.json + report.md
python compare.py  kimminji                 # 최근 두 측정 비교 → compare.md (발행 전후 변화)
python content.py  designers/minji.yaml     # 인용 콘텐츠 초안 → content/{slug}.md
python compete.py  targets/example.yaml     # 경쟁 노출 스캔(영업용) → compete.md
```

핵심 코드: `diagnose.py`·`engines.py`(provider 어댑터)·`extract.py`(추출)·`report.py`·`compare.py`·`content.py`·`compete.py`

초기 무료 구성: Google AI Studio 키만 `.env`의 `GOOGLE_API_KEY`에 넣으면 Gemini 무료 티어로 시작.

---

## ③ 카드 생성기 — 손님용 공유 카드

시술 후 손님에게 보내는 정적 HTML 카드. 같은 base 템플릿(`templates/cards/_base.html.j2`)에
type별 카드를 Jinja 상속으로 얹는다.

```bash
python cards.py cards/example_aftercare.yaml   # → dist/cards/{name}.html
python cards.py --all
```

- type 5종: `aftercare`(애프터케어) · `style`(퍼스널 스타일) · `booking`(예약 확정) · `referral`(친구 소개) · `loyalty`(단골 적립)
- 새 종류는 `templates/cards/{type}.html.j2` 추가 + `cards.py` `TYPES` 등록만

---

## 테스트

```bash
python -m pytest tests/ -q     # 103개
```

## 스코프 (의도적으로 안 만든 것)

- 서버·DB·웹UI·로그인·결제·스케줄러 — 전부 없음. 파일 기반 CLI만.
- 자동 배포·인스타 크롤링·이미지 자동수집 없음 (사진·질문은 사람이 넣는다).
- 챗봇·월간 알림·재방문 알림·적립/소개 추적 등 **서버가 필요한 기능은 범위 밖**.

## 구조

```
diagnose·engines·extract·report·compare·content·compete.py   ② 진단/케어
build·core·schema·validate.py + templates/profile.html.j2     ① 프로필 빌더
cards.py + templates/cards/*.html.j2                          ③ 카드 생성기
designers/*.yaml  targets/*.yaml  cards/*.yaml                입력
prompts/*.j2                                                  LLM 프롬프트
mockups/*.html                                               서비스 맵·기능 미리보기
tests/                                                       단위 테스트 103개
```
