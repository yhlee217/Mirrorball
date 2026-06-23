# 운영 런북 — 컨시어지용 (한 명 온보딩 → 운영)

> 모든 스크립트는 로컬(Mac)에서 실행. 손님용 발행물은 공개, 고객 데이터(PII)는 로컬·gitignore.
> 자동 발송은 절대 하지 않는다 — 시스템은 *누구를·왜·뭐라고*만, 보내는 건 디자이너가 직접.

## 0. 한눈에 (데이터 흐름)
```
designers/_briefs/{slug}.yaml ──gen_profile──▶ designers/{slug}.yaml ──build──▶ dist/{slug}/  (공개 프로필, KO/EN)
targets/{slug}.yaml ───────────diagnose──────▶ clients/{slug}/exposure.yaml ┐
네이버 예약 CSV ──import_naver──▶ records.yaml ─stats─┐                        │
clients/{slug}/customers/*.yaml ─────────────────────┼──build_app──▶ dist_app/{slug}.json ──▶ app/  (디자이너 앱, 게이트)
                                                      └ bookings.yaml(오늘 예약)
```

## 1. 새 디자이너 온보딩
```bash
# (a) 프로필 카피 생성 — 얇은 facts 만 채운 brief 로
#     키 있으면 자동 / 없으면 --prompt 받아 Claude 로 생성
python gen_profile.py designers/_briefs/{slug}.yaml            # → designers/{slug}.yaml
python gen_profile.py designers/_briefs/{slug}.yaml --prompt   # (키 없을 때) 프롬프트 출력

# (b) 발행 — KO + (en 블록 있으면) EN, SEO·JSON-LD 포함
python build.py designers/{slug}.yaml        # 또는 --all
# push 하면 GitHub Actions 가 자동 배포 (Settings→Pages: GitHub Actions)
```

## 2. AI 노출 진단 (월 1회 등)
```bash
# targets/{slug}.yaml 에 손님이 AI에 칠 질문 10개(사람이 작성). 키 필요.
python diagnose.py targets/{slug}.yaml
#  → runs/{slug}/.../report.md  +  clients/{slug}/exposure.yaml (앱 노출 탭)
```

## 3. 예약·통계 (주기적 — 매일 아침 또는 주 1회)
```bash
# 네이버 예약 파트너센터에서 '예약자 목록' CSV 내보내기 → 가져오기
python import_naver.py {export.csv} --slug {slug} --date {YYYY-MM-DD}
#  → clients/{slug}/bookings.yaml(오늘) + records.yaml(누적 장부)
python stats.py clients/{slug}            # 재방문율·인기시술·객단가 확인
```

## 4. 디자이너 앱 데이터 빌드
```bash
python build_app.py clients/{slug}        # → dist_app/{slug}.json
python ops.py app {slug}                  # 로컬 미리보기 (데이터 주입)
python ops.py app                         # 데이터 없이 빈 상태 MVP
```
앱이 주입하는 것: 오늘 예약 · 오늘 챙길 고객(생일/재방문 + 추천 문구) · 고객 카르테(이력·취향·**애프터케어 팁**) · 통계 · AI 노출.

## 5. 원커맨드 래퍼
```bash
python ops.py status         # 디자이너·빌드 현황
python ops.py build --all    # 프로필 전체 빌드
python ops.py check          # 테스트 전체
```

## 보안·개인정보 (PIPA)
- 손님용 프로필: PII 없음 → 공개 OK.
- 고객 데이터(`clients/*/customers`, `bookings.yaml`, `records.yaml`): **연락처 포함 → gitignore, 로컬·비공개**.
  build_app 은 연락처를 출력 JSON에서 **항상 제외**(테스트로 보장).
- 디자이너 앱(`app/`)에 실제 고객 데이터를 올릴 땐 **Cloudflare Access 등으로 접근 게이트 필수**.

## 안 하는 것 (원칙)
- 손님에게 자동 메시지 발송 ✕  · 스크래핑·비공식 접근 ✕  · 사실에 없는 카피(환각) ✕
