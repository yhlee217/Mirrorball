# eval/ — 카피 엔진 루프 엔지니어링 평가 자산

자동 프로필/포트폴리오 카피 생성 엔진을 **자기 피드백 루프**로 고도화하기 위한
평가 기준과 데이터. (루프 지시문은 대화의 "루프 엔지니어링 지시문" 참고)

| 파일 | 역할 |
|---|---|
| `rubric.md` | 품질 5축(SEO·전환·노하우충실도·진정성·사실정합성) 1·3·5점 기준 + 가드레일 + 평가자 출력 JSON 스키마 |
| `golden_set.yaml` | 입력만으로 생성→채점할 케이스 + 노하우 보유자가 쓴 '5점 정답' 카피 + RAG 원칙·가드레일 항목 |
| `LOOP_PROMPT.md` | 실제 파일·함수를 가리키는 **실행형 루프 지시문**(에이전트에 붙여넣기) |

## 실행 코드 (저장소 루트)

| 파일 | 역할 |
|---|---|
| `copygen.py` | 카피 생성 엔진 — `generate_copy(case, kb_path=...)` (루프가 깎는 핵심) |
| `prompts/copy.md.j2` | 생성 프롬프트 = 노하우 룰 인코딩 (주 개선 표적) |
| `prompts/judge.md.j2` | 평가자 프롬프트 (루브릭 기반 JSON 채점) |
| `eval_loop.py` | 하니스 — `load_golden`/`judge`/`aggregate`/`run_baseline` + `python eval_loop.py` baseline |
| `rag.py` + `kb/knowledge.yaml` | 영업 노하우 RAG — 케이스 상황에 맞는 검증 원칙을 검색해 주입 |

> **노하우 주입 2경로**: 골든 세트는 `rag_principles` 를 **명시**(C축 재현성 테스트용).
> 실전 케이스(원칙 미기재)는 `generate_copy(case, kb_path="kb/knowledge.yaml")` 로
> KB 에서 **자동 검색**해 주입한다. (`copygen.resolve_principles` 가 분기)

```bash
python eval_loop.py        # golden_set 전체 baseline 채점 (실행엔 .env 키 필요)
python copygen.py eval/golden_set.yaml balayage_gangnam_damage   # 한 케이스 카피 생성
```

## 루프가 이걸 쓰는 흐름

```
golden_set.yaml 의 case.input  ──▶  카피 생성 엔진  ──▶  생성 카피
                                                          │
        rubric.md + case.reference_output ──▶ 평가자(LLM-judge, 다른 모델)
                                                          │
                                  scores(5축) + weakest_axis + 가드레일 + pairwise
                                                          │
                              약점 진단 → 코드 1곳 변경 → 재생성 → 재채점
                                       (총점 오르고 회귀 없을 때만 채택)
```

- **baseline**: 먼저 현재 엔진으로 golden_set 전체를 채점해 출발점 점수를 기록.
- **정지**: 전 케이스 5축 평균 ≥ 4.5 + 가드레일 0, 또는 3회 연속 개선 없음(플래토).
- **RAG ablation**: 지식베이스 on/off 출력을 비교해 노하우(C축)가 실제 기여하는지 증명.

## 케이스 추가

`golden_set.yaml` 의 `TEMPLATE_...` 블록을 복사해 채운다. 좋은 케이스는
**서로 다른 약점을 스트레스 테스트**한다 — 가격 민감 고객, 남성 컷, 펌 재시술 불안,
손상모, 첫 방문 vs 단골 등. `reference_output`(5점 정답)은 가능하면
**노하우 보유자가 직접** 써서 주관 품질의 기준선을 고정한다.
