# v2 코드리뷰 — 결과 및 후속 (2026-07)

멀티테넌트 SaaS(web/Next.js · worker/수집 · Supabase RLS · 봉투암호화) 전면 리뷰.
RLS·워커 HIGH↑는 실행 검증(임시 Postgres 하네스 / pytest)으로 확증. 아래는 요약과,
이번에 **고친 것**·**의도적으로 미룬 것(근거 포함)**.

## 고침 (커밋됨, 테스트 포함)

| ID | 심각도 | 내용 | 수정 | 검증 |
|----|--------|------|------|------|
| **C1** | CRITICAL | 멤버십 self-insert → 남의 테넌트 가입·장악(+profiles anon read 로 tenant_id 유출) | `0007`: memberships FOR SELECT, profile_public_read 제거 | `tests/rls/run_rls_test.sh`(취약 재현→차단) |
| **H1** | HIGH | 예약 수확 1회 실패 → 테넌트 예약 전량 삭제(30분마다·조용히) | delete_stale 빈-리스트 전체삭제 금지 + reservations_ok 게이트 | `tests/test_worker_sync.py` |
| **H2** | HIGH | 거래 스테일 미정리 → 매출·집계 영구 과대계상 | 수집 날짜 범위 내에서만 스테일 거래 정리(창 밖 불가침) | 〃 |
| **M1** | MEDIUM | tenants FOR ALL → 멤버가 plan·dek_wrapped·slug 직접 수정 | `0008`: FOR SELECT, /api/settings 는 화이트리스트 컬럼만 service_role | RLS 하네스 |
| **M3** | MEDIUM | 365일 창 분할이 경계일 공유 → 이중 집계 | `_windows` 비중복 분할 | `tests/test_worker_sync.py` |
| **M4** | MEDIUM | relink `split("-",1)` → 고객번호에 '-' 시 오연결 | `custno_of()` 접미(-날짜-순번)만 제거 | 〃 |
| **M6** | MEDIUM | 동시 수집 레이스(스케줄+수동) | collect.yml `concurrency` 직렬화 | — |
| LOW | LOW | dry-run 이 로그인ID·회사코드 평문 로그 | 3요소 전부 마스킹 | — |
| LOW | LOW | 파괴적 호출 빈 tenant_id 무가드 | delete/delete_stale 빈 tid → ValueError | `tests/test_worker_sync.py` |

## 해소됨(추가 조치 불필요)
- **M2**(공개 노출 과다): C1 에서 `profile_public_read` 제거로 tenant_id 유출 차단. 공개 페이지
  `p/[slug]` 는 service_role 로 비-PII 필드만 읽고 `published` 게이트 → 정상. (이제 anon 의
  profiles 직접 read 는 아예 불가.)

## 미룸 — 설계/롤아웃 필요(맹목 구현 시 파일럿 데이터 손상 위험)

각 항목 **왜 지금 안 고쳤는지 + 권장 접근**. 결정 주시면 계획대로 진행.

### M5 — 고객번호 없는 고객을 이름으로 키잉 → 동명이인 병합 (MEDIUM)
`scrape.py:normalize` 의 `ext = 고객번호 or 고객명`. 워크인 동명이인 2명이 한 고객으로 합쳐짐.
- **왜 미룸**: 키 스킴을 바꾸면(예: 이름+전화) 기존 행의 ext_id 가 전부 바뀌어 **재키잉 churn**
  (옛 행 고아화·집계 흔들림)이 발생. 파일럿 실데이터가 이미 있어 무중단 마이그레이션 설계가 필요.
- **권장**: 폴백 키를 `고객번호 → 이름+전화(있으면) → 이름` 순으로. 배포 시 1회 재매핑 스크립트로
  기존 이름-키 행을 새 키로 이관(고아 방지). 별도 PR + 검증 후 적용.

### M7 — wipe_tenant 후 재수집 비원자적 (MEDIUM, 가용성)
`wipe_tenant`(삭제) → 수동 전체 재수집 흐름에서 재수집이 실패하면 테넌트가 빈 채 남음.
- **왜 미룸**: HTTP(PostgREST) 경유라 진짜 트랜잭션/스왑이 어려움. 안전한 스테이징-스왑은
  스키마·워커 구조 변경이 필요.
- **완화(이미 반영)**: 파괴적 호출에 빈 tenant_id 가드. `wipe_tenant` 는 프리뷰+CONFIRM 게이트 유지.
- **권장**: 재구축을 "새 스냅샷 수집 성공 → 원자 스왑" 로. 또는 wipe 전에 로그인/1창 수집을
  선검증해 실패 시 중단.

### M8 — 봉투암호화에 AAD 없음 (MEDIUM, 무결성)
같은 테넌트 DEK 라 `pii_enc` 를 행 간 복사해도 복호·인증 통과(이름/전화 뒤섞기 가능).
- **왜 미룸**: worker(py)·web(ts) 양쪽 encrypt/decrypt 를 동시에 바꾸고 **기존 암호문 재암호화**가
  필요(AAD 불일치 시 복호 실패). 롤아웃(키드 버전 + 이중복호 기간) 설계 요.
- **권장**: `pii_kid` 를 살려 v2 도입 — encrypt 시 AAD=`tenant_id|customer_id`(예약은 `tenant_id|ext_id`),
  decrypt 는 kid 로 v1(무AAD)/v2 분기, 백필로 재암호화 후 v1 폐기.

### M9 — 단일 글로벌 KEK·로테이션 경로 없음 (MEDIUM, 키관리)
`MIRRORBALL_KEK` 하나가 전 테넌트 DEK·자격증명을 감쌈. 유출 시 전부 노출. `pii_kid:"v1"` 는
쓰지만 읽는 경로가 없어 로테이션 미작동.
- **왜 미룸**: 키 관리(Vault/KMS)·재래핑 잡·kid 분기 복호가 얽힌 운영 설계.
- **권장**: (1) kid 기반 복호 분기부터 도입(코드), (2) 이후 KEK 로테이션 잡(DEK 재래핑) + 자격증명
  재암호화. M8 과 함께 "kid 살리기"로 묶으면 효율적.

### M10 — tenant_rw 가 role 무시 (LOW→MEDIUM, 확장 함정)
`customers/transactions/bookings` 정책이 멤버면 전부 RW. 파일럿(1인 owner)은 무해하나,
staff/viewer 멤버가 생기면 전원이 거래·PII 조작 가능.
- **왜 미룸**: 지금은 1테넌트 1owner 라 익스플로잇 불가. 역할 모델(뷰어 읽기전용 등)이 확정돼야
  정책 설계 가능.
- **권장**: 멤버 추가 기능 도입 전, `role` 을 보는 정책(쓰기는 owner/manager 만)으로 강화.

### 잔여 LOW(관측·문서)
- `supa._check` 가 PostgREST 응답 본문(비-PII 구조)을 에러로 노출 — 디버깅 유용성과 트레이드오프.
  로그 수집처가 민감하면 스크럽 고려.
- `middleware.ts` 는 세션 리프레시만, 인가는 페이지·라우트별 self-guard 관례. 신규 라우트가
  가드 누락 시 조용히 공개될 수 있음 → 중앙 가드로 강화 권장.
- `0002` 의 `enc_blob` 만 `nullif` 누락 — 빈 자격증명 시 복호 예외로 sync 중단. 신규 마이그레이션으로
  `''`→NULL 정규화 가능(낮은 값).

## 확인된 견고성(리뷰가 통과시킨 것)
- 암호화 자체는 정확(AES-256-GCM, 레코드별 IV, 테넌트 DEK, 태그검증, **평문 폴백 없음**, 하드코딩 키
  없음). worker↔web 바이트 호환.
- IDOR 없음(고객 상세는 RLS 가 차단). 시크릿 커밋 없음(service_role/KEK 서버 전용).
- 워커 테넌트 스코프 정상(모든 쓰기 on_conflict tenant_id,ext_id / 읽기 tenant_id=eq).
