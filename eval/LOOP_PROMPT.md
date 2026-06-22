# 루프 엔지니어링 실행 지시문 (코드 고정형)

> 아래 블록을 AI 코딩 에이전트(Claude Code 등)에 붙여넣으면, 이 저장소의 실제
> 파일·함수를 대상으로 카피 엔진 자기개선 루프를 돈다.

````text
[루프 엔지니어링 — 미용사 자동 프로필 카피 엔진 고도화 / 코드 고정형]

# 대상 코드 (이 저장소)
- 생성 엔진: copygen.py  →  generate_copy(case)  (네가 깎을 핵심)
- 생성 프롬프트(주 표적): prompts/copy.md.j2     (프롬프트 룰 = 노하우 (a) 인코딩)
- 평가자: eval_loop.py    →  judge(case, generated)  /  prompts/judge.md.j2
- 채점 로직(순수): eval_loop.py  →  case_overall / case_pass / aggregate
- 루브릭: eval/rubric.md   (5축 1·3·5점 + 가드레일 + 출력 JSON 스키마)
- 골든 세트: eval/golden_set.yaml  (input → reference_output, RAG 원칙, 가드레일 항목)
- provider 오케스트레이션: engines.py (complete). 생성=COPY_PROVIDER, 평가=JUDGE_PROVIDER(다른 모델 권장).

# 미션
prompts/copy.md.j2 (+필요 시 copygen.py 의 RAG/오케스트레이션)을 반복 개선해,
golden_set 전 케이스에서 루브릭 5축이 한계까지 오르게 한다. 출력 한 번이 아니라
'생성 코드'를 고도화한다.

# 루프 절차
0. baseline: `python eval_loop.py` 로 전 케이스 채점 → 축 평균·종합·pass·최약축 기록.
1. 진단: aggregate 의 weakest_axis 와 각 case verdict 의 failures/guardrail_violations 인용을 읽어
   근본 원인을 한 곳으로 특정한다:
     - 프롬프트 룰 문제(prompts/copy.md.j2) /
     - RAG 원칙 주입·검색 문제(copygen.render_prompt 의 rag_principles 처리) /
     - 오케스트레이션 부재(생성→자기재작성 패스 등).
2. 변경: 원인에 대해 **한 번에 하나만** 수정한다(주로 prompts/copy.md.j2).
3. 재채점: `python eval_loop.py` 다시 실행.
4. 채택/롤백: 종합 점수가 오르고 **다른 축 회귀가 없을 때만** 변경을 남긴다. 아니면 되돌린다.
5. 로그: 이터레이션마다 "변경 → 축별 점수 변화 → 채택/롤백"을 한 줄로 보고.
6. RAG ablation: rag_principles 를 비운 출력과 채운 출력의 C축을 비교해 노하우가
   실제로 점수에 기여하는지 증명. 기여 없으면 주입 방식부터 고친다.

# 가드레일 (eval/rubric.md 와 동일 — judge 가 fail 처리)
사실 정합성 / 일반론 금지 / 키워드 스터핑 금지 / RAG 원칙 반영 / AI 슬롭 금지.
가드레일 위반이 있는 한 종합 점수는 0 으로 취급된다(case_overall).

# 정지 조건
golden_set 전 케이스에서 5축 평균 ≥ 4.5 + 가드레일 0, 또는 3회 연속 개선 없음(플래토).

# 산출물
개선된 prompts/copy.md.j2 (+필요 시 copygen.py) / 이터레이션별 점수 추이 /
"어느 변경이 가장 큰 향상을 냈는지" 요약.

# 시작
먼저 `python eval_loop.py` 로 baseline 을 찍고, 최약축부터 한 변경씩 루프를 돌려라.
(실 LLM 호출엔 .env 의 GOOGLE_API_KEY 등 필요. 평가자는 JUDGE_PROVIDER 로 생성기와 분리.)
````

## 메모
- **왜 prompts/copy.md.j2 가 주 표적인가**: 노하우 (a) 인코딩이 거기 있고, 코드 변경 없이
  안전하게 반복 가능. 구조적 한계(예: 재작성 패스 필요)에 부딪히면 copygen.py 를 건드린다.
- **평가자 분리**: 생성 `COPY_PROVIDER` 와 평가 `JUDGE_PROVIDER` 를 다른 모델로 두어 자기편향을 줄인다.
- **회귀 방지**가 핵심: 한 축을 올리려다 다른 축을 깎는 변경은 채택하지 않는다(aggregate 로 감시).
