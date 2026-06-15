# Mirrorball — 미용사 AI 노출 진단

헤어 디자이너 1명이 AI 검색(ChatGPT·Gemini·Perplexity)에서 어떻게 노출되는지
진단하는 1인 컨시어지용 내부 CLI 스크립트. SaaS 아님, 파일 기반.

## 설치 / 실행 (3줄)

```bash
pip install -r requirements.txt
cp .env.example .env   # 키 채우기 (키 있는 엔진만 자동 활성화)
python diagnose.py targets/example.yaml
```

## 초기 무료 구성 (권장)

비용 0으로 시작하려면 **Gemini 무료 티어**만 쓰면 됩니다.

1. Google AI Studio 에서 API 키 발급 → `.env` 의 `GOOGLE_API_KEY` 에 입력
2. 나머지(`OPENAI_API_KEY`, `PERPLEXITY_API_KEY`)는 비워둠 → 자동 비활성화
3. `REPORT_PROVIDER=gemini` (기본값) — 리포트 생성도 Gemini 로

→ 실행하면 `활성 엔진: gemini / 리포트: gemini` 로 동작합니다.
OpenAI/Perplexity 는 크레딧·키가 생겼을 때 `.env` 에 키만 넣으면 자동으로 합류합니다(엔진 1~3개 유연).
로컬 모델(Ollama 등)은 다루지 않습니다 — 무료 크레딧/무료 티어 API만 사용.

## 동작

1. `targets/{slug}.yaml` 의 질문을 질문×(활성 엔진)×sampling 만큼 병렬 질의
   (동시 3, 타임아웃 60s, 1회 재시도, 429는 백오프)
2. 각 답변에서 디자이너/매장 언급·맥락·인용·경쟁 후보를 추출
3. 원본을 `runs/{slug}/{YYYYMMDD_HHMM}/raw.json` 에 저장 (중간 실패해도 성공분 저장)
4. `REPORT_PROVIDER` 로 고객용 `report.md` 생성 (프롬프트는 `prompts/report.md.j2`)

질문은 사람이 yaml 에 직접 넣습니다. 자동 생성하지 않습니다.

## 파일

- `diagnose.py` — 엔트리(엔진 자동감지, 비용가드, 병렬 질의, 저장, 요약)
- `engines.py` — provider 어댑터 + 자동 활성화 + 디스패처
- `extract.py` — 언급/맥락/인용/경쟁 추출 (substring)
- `report.py` — raw.json → 리포트 마크다운
- `prompts/report.md.j2` — 리포트 프롬프트 템플릿
- `tests/` — 추출/엔진/파이프라인/리포트 단위 테스트

## 테스트

```bash
python -m pytest tests/ -q
```

---

# 미용사 프로필 생성기 (build.py)

YAML 입력으로 호스팅 프로필 정적 HTML을 찍어내는 빌드 도구. 기준 디자인
(`templates/profile.html.j2`)은 손으로 만든 원본 HTML을 그대로 옮긴 것이고,
값만 변수화한다. 디자인 변경 없음.

## 설치 · 빌드 · 배포 (3줄)

```bash
pip install -r requirements.txt
python build.py designers/hayewoni.yaml      # 빌드 → dist/hayewoni/index.html
# dist/ 를 Netlify drop 또는 GitHub Pages에 수동 업로드
```

- 전부 빌드: `python build.py --all` (designers/*.yaml)
- 입력: `designers/{slug}.yaml` (스키마는 `designers/hayewoni.yaml` 참고)
- 출력: `dist/{slug}/index.html` (순수 정적, 런타임 서버 불필요, `.gitignore`)

## 동작

1. YAML 로드·검증 → `core.render(data)` → `dist/{slug}/index.html`
2. schema.org JSON-LD 2종(Person·FAQPage)을 입력값에서 자동 생성해 삽입
3. `<title>`·`<meta description>`도 입력값에서 자동 생성
4. 빌드 후 JSON-LD 유효성(파싱) 검증

## 선택 모듈 (있으면 나타나고, 없으면 기존 디자인 그대로)

데이터가 있을 때만 렌더되는 선택 필드. 없으면 출력이 원본과 byte-identical 로 유지됩니다.

```yaml
# 헤어 메뉴판 — Specialties 다음에 "시술 안내" 섹션 추가
menu:
  - name: "여성 커트"
    desc: "얼굴형 맞춤 디자인 커트"   # 선택
    price: "3만원"
    time: "약 50분"                  # 선택
    signature: true                  # 선택, 배지 표시

# Before/After 갤러리 — Portfolio 자리를 드래그 비교 슬라이더로 교체
# (없으면 기존 portfolio_labels 라벨 그리드로 폴백)
portfolio:
  - before: "https://.../before.jpg"   # 사진은 사람이 넣음 (크롤링 없음)
    after: "https://.../after.jpg"
    caption: "단발 + 발레아주"          # 선택

# 고객 후기 — Portfolio 다음에 "고객 후기" 섹션 (평균·개수는 자동 계산)
reviews:
  - stars: 5                           # 1~5 정수
    text: "발레아주 색이 너무 예뻐요..."
    by: "이○○"
    service: "발레아주"                 # 선택

# 어울리는 스타일 찾기 — Specialties 다음에 인터랙티브 진단(순수 정적 JS)
# 각 보기의 style 태그를 집계해 가장 많은 결과를 추천 → 예약 CTA
style_quiz:
  intro: "세 가지만 답하면 어울리는 스타일을 추천해드려요"   # 선택
  questions:
    - q: "얼굴형이 어떻게 되세요?"
      options:
        - { label: "계란형", style: "layered" }
        - { label: "둥근 편", style: "perm" }
  results:
    layered: { title: "레이어드컷", desc: "자연스러운 흐름", cta_label: "상담받기" }
    perm:    { title: "디지털펌", desc: "볼륨과 컬", cta_label: "상담받기" }
```

`designers/minji.yaml` 이 두 모듈을 모두 채운 예시입니다(`python build.py designers/minji.yaml`).

## 검증·경고

- 필수 필드(slug, display_name, korean_name, role, salon, instagram, specialties,
  faq, knows_about) 누락 시 빌드 중단
- (선택) menu 항목은 name/price, portfolio 항목은 before/after 가 있어야 함
- 값에 `[ ]` 가 남아있으면 "미입력 추정" 경고 (발행 사고 방지)
- photo_url / booking_url 비면 경고만 하고 진행(플레이스홀더 동작)

## 구조 (입력-코어 분리)

- `build.py` — CLI 엔트리 (YAML → core)
- `core.py` — `render(data: dict) -> str` (입력 방식 무관 재사용 코어)
- `schema.py` — data → Person/FAQPage JSON-LD
- `validate.py` — 검증 + placeholder 경고
- `templates/profile.html.j2` — 원본 디자인(값만 변수화)

`core.render(data)`가 dict만 받으므로, 나중에 웹 폼이 같은 dict를 넘기면
그대로 재사용된다 (웹 폼은 이번 범위 아님).
