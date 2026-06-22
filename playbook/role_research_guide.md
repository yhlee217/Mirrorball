# 미용사 마케팅 자동화 — 담당자별 실행 리서치 보고서

각 담당자가 **자기 파트를 채울 때 바로 쓰도록**, 핵심 두 축(① AI·로컬 검색 노출,
② 전환되는 영업·카피 노하우)을 외부 리서치로 보완해 정리했다. 모든 섹션은
**[할 일] → [리서치 핵심·근거] → [지금 프로젝트에 반영]** 순서다. 출처는 맨 끝.

> 한눈에 — ① **AI는 "첫 40~60자의 명확한 답 + 데이터 + Q&A 구조"를 인용한다** (LLM 인용의 44.2%가 글 앞 30%에서 나옴).
> ② **단골 1명 = 연 $150~250 × 4~6회**, 첫방문 평균 재방문은 45%뿐 — *선예약 한 줄*이 재방문을 40%→80%로 바꾼다.
> ③ 이 리서치는 우리 설계(질문형 카피·재방문 각인·번들·정직 카피·JSON-LD)를 **검증**했다. 빈 곳은 "실데이터"다.

---

## 1. 노하우 담당 (원장·실무자) — KB와 정답 카피 채우기

**[할 일]** `kb/knowledge.yaml`의 `example`·`verified`와 `eval/golden_set.yaml`의
`reference_output`을 *검증된 실제 노하우*로 채운다. (지금은 합성 초안)

**[리서치 핵심 — 이 숫자·원칙을 노하우로 인코딩]**

객단가(업셀):
- **번들 = 앵커링.** "Color + Cut" 대신 *"시그니처 컬러 트랜스포메이션"*(컬러+딥컨디셔닝+스타일)처럼 **가치 네이밍 패키지**로 묶으면 높은 가격대에 먼저 고정된다.
- **"팔지 말고 진단하라."** 최고 디자이너는 *"오늘 목표가 뭐예요?"*로 시작한다. 컬러 손님 업셀 1순위는 **본드 빌더·글로스/토너·두피 디톡스** — 15분 내, 모발 보호·컬러 수명 연장으로 ROI 높음.
- **메뉴는 가격표가 아니라 판매도구**: 시그니처·고수익 번들을 시각적으로 강조, 애드온은 별도 섹션에 묻지 말고 **메인에 배치**.
- 효과 감각: 객단가 **+$5~10 × 월 200명 = +$2,000/월(+$24,000/년)**.

리텐션(단골 전환):
- **첫방문 평균 재방문 45%** (Boulevard, 2,500만 예약 분석). **첫방문자 ~70%는 다시 안 옴.** best-in-class는 **70%**.
- **선예약의 힘**: 첫 방문에 다음을 *예약하고 간* 손님은 **80%+** 재방문, *"전화할게요"*는 **40% 미만**. 체어사이드(의자에서) 리북은 프런트 위임 대비 **재방문 20~30%↑**.
- **재방문 5%↑ → 이익 25~95%↑**. 단골 42%가 매출 80%를 만든다.
- **시술 2일 뒤 안부 문자**(케어)가 신뢰를 만든다 → 우리 `cards` 애프터케어·재방문 알림의 근거.

> KB에 이미 있는 원칙(재방문 시점 각인·번들 앵커·투명가격·정직한 거절·기대 조정)이
> 위 리서치와 정확히 일치한다. **남은 건 `example`을 "진짜 전환된 멘트"로, `verified`를
> "내가 낸 실제 성과(객단가/재방문율)"로 교체**하는 것.

**[지금 반영 체크리스트]**
- [ ] KB 각 엔트리 `example`을 *실제로 통한 멘트*로 교체
- [ ] KB `verified`에 *본인 실측치*(예: "재방문율 45→65%") 기입
- [ ] 골든 `reference_output`을 *본인이 쓴 5점 카피*로 교체 → 루프 기준선 상승
- [ ] 번들 1~2개를 **가치 네이밍**으로 정의해 `menu`/KB에 반영

---

## 2. 콘텐츠·카피 담당 — AI가 인용하는 글쓰기

**[할 일]** `prompts/copy.md.j2`(프로필 카피)와 `prompts/content.md.j2`(블로그·플레이스 글)가
*검색·AI가 인용하기 좋은* 출력을 내게 한다.

**[리서치 핵심 — AEO/GEO 인용 규칙]**
- **"SEO는 클릭, GEO는 인용."** 검색의 **60%+가 클릭 없이** AI 답변으로 끝나고, 사용자 44%(McKinsey)는 AI를 1차 정보원으로 본다 → *노출 = 인용되는 것*.
- **앞 40~60자에 핵심 답**: LLM 인용의 **44.2%가 글의 앞 30%**에서 나온다. → 질문을 던지고 **답을 즉시**.
- **150~200자마다 구체 수치·데이터 1개**(출처 포함): AI는 *하드 데이터*가 든 글을 우선 인용.
- **전문가/자격 신호**: 자격을 단 인용·소개는 AI 신뢰 신호를 **최대 41%** 높임.
- **구조화 포맷이 3배 더 인용됨**(문단만 있는 글 대비). **질문형 헤딩·Q&A 쌍**을 AI가 특히 신뢰.
- **시맨틱 청킹**: AI는 페이지가 아니라 *섹션 단위*로 읽는다 → 각 문단이 한 개념을 자립적으로.

> 우리 카피 엔진의 A축("질문형 도입 + 첫 문장에 명확한 답")은 **위 1순위 규칙과 정확히 일치**한다.
> 다만 리서치가 가리키는 **추가 레버 2개**가 아직 약하다: (a) *구체 수치/데이터*, (b) *전문가·자격 신호*.

**[지금 반영 체크리스트]**
- [ ] `content.md.j2`(블로그·플레이스): "150~200자마다 사실 기반 **수치 1개**(유지기간·소요시간·가격 등)를 넣어라" 규칙 추가
- [ ] 블로그는 **질문형 제목 + 첫 줄에 답** 강제(이미 부분 반영) → "답을 첫 40~60자에"로 명시
- [ ] 자격·경력이 *사실에 있으면* 자연스럽게 1회 노출(과장 금지는 유지) — 신뢰 신호
- [ ] 한 글 = 한 질문(시맨틱 청킹) 원칙 명시
- [ ] (선택) 루프 루브릭 A축 기준에 "수치·자격 신호 포함" 항목 추가해 자동 채점

---

## 3. 노출·발행 담당 (로컬 SEO·운영) — Google & 네이버

**[할 일]** 만든 프로필을 올리고, Google·네이버에서 실제로 노출되게 운영한다.

**[리서치 핵심 — Google 로컬]**
- 순위 3요소: **적합도(Relevance)·거리(Distance)·권위(Authority)**.
- **리뷰**: 대부분 도시에서 **50개+면 안정적 노출**, 유지엔 **월 5개+**. 체크아웃 때 요청 + 시술 후 자동 문자 + **리뷰 직링크**.
- **사진**: 매주 업로드(주 5장이 1년에 50장보다 낫다). **50장+면 순위 유리**. 비포·애프터·내부·팀 사진.
- **NAP 일관성**: 상호·주소·전화가 모든 채널에서 **정확히 일치**해야 신뢰·순위↑.
- 타임라인: GBP 개선은 수 주, 전반 순위는 **4~8주~3~6개월**.

**[리서치 핵심 — 네이버(한국 시장)]**
- 스마트플레이스 로직 = **적합도·인기도·신뢰도**. *초기 세팅이 기초공사* — 처음에 제대로.
- **사진 리뷰 100개↑ → 방문자 +115.6, 길찾기 +79, 저장 +55** (상관). 미용실은 **시술 정보 사진 최대 300장**.
- **검색 키워드 직접 등록 10~15개**: 업종+지역+서비스 조합("강남 헤어샵", "강남역 파마", "강남 남자 커트").
- **비포·애프터 사진 리뷰 유도**(무료 시술 이벤트 등) → 우리 ③ 전후 갤러리·후기 위젯과 직결.
- **사업자 인증 배지** = 신뢰도·알고리즘 우대. 네이버 예약·페이·저장하기 활성화.

**[지금 반영 체크리스트]**
- [ ] GBP/네이버 플레이스 **초기 세팅** 완비(카테고리=헤어살롱+서비스별 보조, NAP 일치)
- [ ] **리뷰 루틴**: 체크아웃 요청 + 2일 후 문자(케어 겸) + 직링크 → 월 5개+ 목표
- [ ] **사진 주간 업로드** 루틴(전후·내부·작업) → 50장+/300장
- [ ] 네이버 **검색 키워드 10~15개** 등록, **사업자 인증**
- [ ] 우리 빌더의 `content.py` 산출물을 **블로그/플레이스 글감**으로 주간 발행

---

## 4. 기술 담당 — 구조화 데이터(JSON-LD)

**[할 일]** `schema.py`가 만드는 구조화 데이터로 검색·AI가 매장/디자이너를 *엔티티로* 인식하게.

**[리서치 핵심]**
- `HairSalon`은 `LocalBusiness`의 하위 타입 → 업종을 정확히 전달.
- 구조화 데이터는 **직접 순위 요인은 아니지만**, 리치 결과·**AI Overview 인용**·Knowledge Graph **엔티티 인식**의 핵심 레버.
- ⚠️ **FAQ 리치 결과는 Google에서 사실상 폐지**(보도 기준 2026): 단, **FAQ 콘텐츠 자체는 사용자·AI에게 여전히 유효** — *Google 리치스니펫 용도로 기대하지 말되, AI 인용·가독성용으로 유지*.

**[지금 반영 체크리스트]**
- [ ] 현재 `Person`+`HairSalon`+`FAQPage` JSON-LD 유지(AI 인용·엔티티용)
- [ ] FAQ는 *Google 리치 기대 대신* AI 인용·본문 가독성 목적임을 문서화
- [ ] `address_locality/region` 등 NAP를 플레이스와 **정확히 일치**시켜 엔티티 신뢰↑
- [ ] (선택) `LocalBusiness`에 영업시간·`sameAs`(인스타·플레이스 URL) 보강

---

## 5. 사업·영업 담당 — 숫자로 본 우선순위

**[리서치가 뒷받침하는 우선순위]**
- **리텐션이 돈이다**: 단골 42%가 매출 80%, 재방문 5%↑ → 이익 25~95%↑. → 구독(①)·재방문 카드(③)·선예약이 1순위.
- **신규 1명 가치 $150~250×4~6회** → 무료 진단 영업(④)의 *획득 비용 한도*를 이 LTV로 잡는다.
- **AI 노출은 지금이 기회**: AI 트래픽 전년比 +527%, 1차 정보원화 44% — 경쟁이 아직 비어 있을 때 선점(독점권 ⑦).

**[지금 반영]** `playbook/`의 가격(①)·영업(④)·살롱(③) 실행안에 위 LTV·리텐션 숫자를
*근거 멘트*로 삽입(영업·가격 설득력↑).

---

## 부록 · 출처

GEO/AEO(AI 검색 인용):
- [GEO Definitive Guide — Geoptie](https://geoptie.com/blog/generative-engine-optimization)
- [GEO Playbook 2025 — SEOTuners](https://seotuners.com/blog/seo/generative-engine-optimization-geo-in-2025-the-complete-playbook-to-win-ai-overviews-chatgpt-copilot-perplexity/)
- [AEO Complete Guide — Frase](https://www.frase.io/blog/what-is-answer-engine-optimization-the-complete-guide-to-getting-cited-by-ai)
- [AEO Best Practices — HubSpot](https://blog.hubspot.com/marketing/answer-engine-optimization)
- [Optimize for AI Answer Engines — Contentstack](https://www.contentstack.com/blog/ai/how-to-optimize-content-for-ai-answer-engines-aeo)

로컬 SEO(미용실)·스키마:
- [Local SEO for Hair Salons — Hashmeta](https://hashmeta.com/blog/local-seo-for-hair-salons-complete-beauty-industry-marketing-guide/)
- [How to Rank Your Salon on Google — The Local Gem](https://www.thelocalgem.com/blog/how-to-rank-salon-on-google)
- [GBP Optimisation for Salons — Salon Guru](https://www.salonguru.net/google-my-business/)
- [LocalBusiness Schema How-to — Schema App](https://www.schemaapp.com/schema-markup/how-to-do-schema-markup-for-local-business/)
- [Structured Data for SEO, LLMs & AI (GEO/AEO) — Opace](https://opace.agency/blog/structured-data-schema-for-seo/)

네이버(한국):
- [네이버 스마트플레이스 상위노출 Tip — Hoonlog](https://hoonhooon.com/entry/%EC%8A%A4%EB%A7%88%ED%8A%B8%ED%94%8C%EB%A0%88%EC%9D%B4%EC%8A%A4-%EC%83%81%EC%9C%84-%EB%85%B8%EC%B6%9C-%EB%85%B8%ED%95%98%EC%9A%B0-Tip)
- [네이버 플레이스 세팅 체크리스트 30 — Marketing Chef](https://marketingchef.net/naver-place-ranking-setting/)
- [스마트플레이스 상위노출 로직(적합도·인기도·신뢰도) — QnA](https://qna.ac/%EB%84%A4%EC%9D%B4%EB%B2%84%ED%94%8C%EB%A0%88%EC%9D%B4%EC%8A%A4/)

객단가·업셀·리텐션:
- [Increase Salon Average Ticket — Dingg](https://dingg.app/blogs/increase-salon-average-ticket-upsell-cross-sell-packages)
- [5 Ways to Increase Average Ticket — Mindbody](https://www.mindbodyonline.com/business/education/blog/5-ways-increase-average-ticket-your-salon-or-spa)
- [Increase Average Ticket — Booksy](https://biz.booksy.com/en-us/blog/how-to-increase-your-salons-average-ticket)
- [Client Retention After First Visit — HairSalonPro](https://hairsalonpro.com/salon-client-retention-after-first-visit/)
- [Client Retention Statistics & Strategies — Salon Today](https://www.salontoday.com/salon-management/1093720/7-client-retention-statistics-strategies-for-your-salon)
- [Calculating Client Retention Rate — Meevo](https://www.meevo.com/blog/calculating-client-retention-rate/)

> 주의: 수치 다수는 업계 마케팅 자료 기반이라 출처별로 차이가 있을 수 있다.
> 의사결정 전 본인 데이터로 재확인 권장. (예: 재방문율은 매장·시술별 편차 큼)
