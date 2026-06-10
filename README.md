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
