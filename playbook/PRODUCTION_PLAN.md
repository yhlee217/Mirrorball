# Mirrorball 운영 개발 계획 (프로토타입 → 실서비스)

> 1인 컨시어지가 1인 미용실 원장·샵인샵 디자이너를 대상으로 운영하는 **done-for-you** 서비스.
> 원칙: ① 무료·로컬 우선 ② 고객 관계는 자동화하지 않는다(원장 무장) ③ 디자인 바이트 동일 보존 ④ 컨시어지 1명이 다수 원장을 운영할 수 있는 구조.

---

## 0. 지금 가진 것 / 운영에 빠진 것

| 영역 | 지금 (프로토타입) | 운영에 빠진 것 |
|---|---|---|
| 손님용 프로필 | `build.py --all` → `dist/{slug}/index.html` (정적, SEO·JSON-LD 포함) | **호스팅·도메인·검색 등록·방문 측정** |
| AI 노출 진단 | `diagnose.py` 로컬 CLI (멀티 LLM) | **정기 실행·결과 보관·원장 리포트 전달 루틴** |
| 카피 생성 엔진 | `copygen.py` + 루프(`run_loop.py`/Claude CLI) | **운영 입력→출력 파이프라인, 품질 게이트 자동화** |
| 원장용 CRM | `mockups/app_prototype.html` (목업, 데이터 하드코딩) | **실데이터 연결, 접근 제어(PII), 디자이너별 인스턴스** |
| 운영 토대 | 단일 repo, 수동 실행 | **클라이언트 데이터 분리, 배포 자동화, 백업, 온보딩 체크리스트** |

→ 운영 버전의 핵심 격차는 **(a) 배포·호스팅, (b) 고객 PII 안전한 데이터 계층, (c) 컨시어지 1인이 반복 운영할 워크플로** 셋.

---

## 1. 운영 아키텍처 (목표 구조)

```
mirrorball/                  (공개 toolkit repo — 코드만, PII 없음)
  build.py / core.py ...     프로필·카드·진단·카피 엔진
  designers/{slug}.yaml      디자이너 "공개" 정보 (이름·소개·갤러리 등)

mirrorball-clients/          (★ 별도 비공개 repo — 고객 PII 격리)
  {slug}/customers/*.yaml    고객 카드 (이름·연락처·시술이력·메모)
  {slug}/config.yaml         디자이너별 운영 설정

배포:
  손님용 프로필   → Cloudflare Pages (공개)         예: hayewoni.mirrorball.kr
  원장용 CRM/알림 → Cloudflare Pages + Access(게이트)  예: app.mirrorball.kr/{slug}
  진단·카피 엔진  → 컨시어지 로컬(Mac mini)에서 실행, 결과만 배포물에 반영
```

**판단 근거**
- 백엔드 없이 시작: 클라이언트 수가 적은 1인 운영. 정적 + 게이트로 PII까지 커버 가능 → 서버 운영비·보안 부담 0.
- **PII는 코드 repo에 두지 않는다**: 고객 연락처·시술이력은 별도 비공개 repo로 격리(한국 개인정보보호법 대비). 손님용 프로필엔 PII 없음 → 공개 OK.
- 원장용 화면은 **Cloudflare Access(무료, 이메일 OTP)** 로 게이트 → 정적이지만 원장 본인만 열람.

---

## 2. 단계별 로드맵

### Phase 0 — 운영 토대 (1~2일) · *지금 착수*
- [ ] `scripts/deploy.sh` + `.github/workflows/pages.yml`: push 시 `build.py --all` → Pages 배포
- [ ] `mirrorball-clients` 비공개 repo 생성, 데이터 스키마 확정(`customers/*.yaml`)
- [ ] 시크릿 관리: API 키는 로컬 `.env`만(이미 그러함), CI엔 배포 토큰만
- [ ] `MAKEFILE`/`Makefile` 또는 `ops.py`: `diagnose`·`build`·`cards`·`copy` 원커맨드 래퍼
- **완료 기준**: 빈 커밋 push → 프로필 사이트가 URL로 뜬다.

### Phase 1 — 손님용 프로필 라이브 (2~3일) · *가장 먼저 돈이 되는 단계*
- [ ] Cloudflare Pages 연결 + 와일드카드 서브도메인(`{slug}.mirrorball.kr`)
- [ ] 검색 등록: 네이버 서치어드바이저·구글 서치콘솔에 sitemap 제출(빌더가 이미 `sitemap.xml`/`robots.txt` 생성)
- [ ] 방문 측정: 가벼운 비쿠키 분석(Cloudflare Web Analytics, 무료·개인정보 안전)
- [ ] 인스타 바이오 링크 동선 점검(인앱 브라우저 → 프로필은 정상, 설치 불필요)
- **완료 기준**: 원장 1명의 실제 프로필이 도메인으로 공개되고 색인 요청 완료.

### Phase 2 — 원장용 컨시어지 앱 실데이터화 (1~2주)
- [ ] `app_prototype.html` → 데이터 주입형으로 분리: `app/index.html` + `app/data/{slug}.json`
- [ ] 빌더 추가(`build_app.py`): `mirrorball-clients/{slug}/customers/*.yaml` → `{slug}.json`
- [ ] 화면별 실데이터 연결: 예약 브리핑·다음시술 추천·오늘 챙길 고객(원장 알림, **자동발송 X**)
- [ ] Cloudflare Access 게이트 + PWA 설치 안내(이미 배너 구현)
- [ ] AI 노출 진단 결과(`diagnose.py`)를 원장 화면 "노출 케어" 탭에 주입
- **완료 기준**: 원장이 본인 URL 로그인 → 본인 고객 데이터로 동작하는 설치형 앱 사용.

### Phase 3 — 컨시어지 운영 자동화 (지속)
- [ ] 주간 배치(`ops.py weekly --slug`): 진단 재실행 → 변화 감지 → 원장 리포트(마크다운/카드) 생성
- [ ] 카피 품질 게이트: 새 카피는 `eval_loop.py` 루브릭 통과분만 배포(사람 1차 검수 유지)
- [ ] "오늘 챙길 고객" 다이제스트: `customers/*.yaml`의 생일·리터치 주기 → 원장에게 **알림만**
- [ ] 백업: clients repo 일일 스냅샷, 배포물 버전 태깅
- **완료 기준**: 원장 1명당 주 30분 이하 운영 손길로 유지.

### Phase 4 — 셀프서브 전환 (스케일 시 선택)
- 원장이 직접 예약·메모 입력할 때만 필요 → 그 시점에 경량 백엔드(Supabase/Cloudflare D1) 도입.
- 트리거: 동시 운영 원장 10명 초과 또는 실시간 입력 요구 발생 전까지 **만들지 않는다**.

---

## 3. 데이터 모델 (운영 확정안)

```yaml
# mirrorball-clients/{slug}/customers/{id}.yaml  (비공개)
id: kim-0312
name: 김○○                 # 표시용(원장 화면에서만)
contact: "010-..."          # 원장 직접 연락용 — 공개 배포물엔 절대 미포함
first_visit: 2025-03-12
prefer: ["밝은 톤", "어깨 길이 유지"]
history:
  - date: 2026-04-02
    service: 발레아주
    notes: 손상 신경 씀, 다음엔 클리닉 묶기 제안
care_cycle_days: 70         # 리터치 주기 → 알림 산출
birthday: 03-15
```
- **공개/비공개 경계**: 손님용 프로필 빌드는 `designers/{slug}.yaml`만 사용(PII 없음). 원장용 앱 빌드만 clients repo 접근.
- **최소 수집**: 연락처는 원장이 직접 연락하기 위한 것 — 시스템은 발송하지 않음(원칙 ②).

---

## 4. 보안·법무 체크리스트 (한국 PIPA)
- [ ] 고객 PII는 비공개 repo + Access 게이트, 공개 배포물 0
- [ ] 수집 항목 최소화·이용 목적 고지(원장↔고객 동의는 원장 책임, 컨시어지는 처리위탁)
- [ ] 처리위탁 계약서 1장(컨시어지=수탁자) — `playbook/`에 템플릿화
- [ ] 분석은 비쿠키(Cloudflare) → 동의배너 부담 최소화
- [ ] 백업 암호화, 이탈 원장 데이터 파기 절차

## 5. 비용 (월, 원장 5명 기준)
| 항목 | 선택 | 비용 |
|---|---|---|
| 호스팅·CDN | Cloudflare Pages | 0 |
| 접근 게이트 | Cloudflare Access (≤50인) | 0 |
| 분석 | Cloudflare Web Analytics | 0 |
| 도메인 | mirrorball.kr 1개 | ~2만/년 |
| LLM(진단·카피) | 로컬 무료티어 우선, 유료 보조 | ~0~소액 |
→ **사실상 도메인비만으로 운영 가능.**

## 6. 지금 바로 하는 일 (이번 세션)
1. `.github/workflows/pages.yml` + `scripts/deploy.sh` 작성 → Phase 0/1 배포 파이프라인
2. `ops.py` 원커맨드 운영 래퍼 스캐폴딩
3. 테스트 통과 확인 후 커밋·푸시

> 이후 매 단계는 표준 지침대로 **묻지 않고** 추천 방향으로 진행하고, 결과만 보고한다.
