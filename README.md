# Mirrorball — 미용사 AI 노출 진단

헤어 디자이너 1명이 AI 검색(ChatGPT·Gemini·Perplexity)에서 어떻게 노출되는지
진단하는 1인 컨시어지용 내부 CLI 스크립트. SaaS 아님, 파일 기반.

## 설치 / 실행

```bash
pip install -r requirements.txt
cp .env.example .env   # API 키 채우기
python diagnose.py targets/example.yaml
```

## 동작

1. `targets/{slug}.yaml` 의 질문을 질문×엔진(3)×sampling 만큼 병렬 질의 (동시 3, 타임아웃 60s, 1회 재시도)
2. 각 답변에서 디자이너/매장 언급·맥락·인용·경쟁 후보를 추출
3. 원본을 `runs/{slug}/{YYYYMMDD_HHMM}/raw.json` 에 저장 (중간 실패해도 성공분 저장)
4. Anthropic API 로 고객용 `report.md` 생성 (프롬프트는 `prompts/report.md.j2`)

질문은 사람이 yaml 에 직접 넣습니다. 자동 생성하지 않습니다.

## 파일

- `diagnose.py` — 엔트리(CLI, 비용가드, 병렬 질의, 저장, 요약)
- `engines.py` — 엔진 어댑터 3개 + 디스패처
- `extract.py` — 언급/맥락/인용/경쟁 추출 (substring)
- `report.py` — raw.json → 리포트 마크다운
- `prompts/report.md.j2` — 리포트 프롬프트 템플릿
- `tests/test_extract.py` — 추출 로직 단위 테스트

## 테스트

```bash
python -m pytest tests/ -q
```
