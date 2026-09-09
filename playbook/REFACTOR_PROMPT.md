# 리팩토링 킥오프 프롬프트 (코드 품질)

> 새 세션에 **아래 블록을 그대로 붙여넣어** 시작한다.
> 짝이 되는 문서: `playbook/UX_PROMPT.md`(고객 UI/UX). 둘을 한 세션에서 섞지 말 것 —
> 리팩토링은 "동작을 바꾸지 않는" 작업이고 UX 는 "동작을 바꾸는" 작업이라, 섞으면
> 회귀가 났을 때 원인을 가릴 수 없다.

---

너는 Mirrorball(미용실 고객관리 앱) 코드베이스를 정리하는 Claude다.
리포 `yhlee217/Mirrorball`, 작업 브랜치 `claude/charming-planck-hmgazi`.

## 0. 이 작업의 성격 — 겉보기 동작은 바뀌지 않는다

**리팩토링의 성공 기준은 "화면과 숫자가 이전과 똑같다"이다.** 더 나은 구조를 위해 동작을
슬쩍 바꾸고 싶어지면 멈추고, 그건 별도 항목으로 적어 사용자에게 보고하라.

작업 전 반드시:
1. `git fetch` 로 최신 확인 후 시작(다른 세션이 밀어넣었을 수 있다).
2. `python3 -m pytest -q` (현재 412 passed) 와 `cd web && npx tsc --noEmit` (0 errors) 를 먼저 돌려
   **출발점이 초록불인지** 확인. 여기서 깨져 있으면 그것부터 보고.
3. 한 덩어리 고칠 때마다 위 둘을 다시 돌린다. 커밋도 덩어리 단위로.

## 1. 이 코드베이스에서 실제로 아픈 곳 (측정치)

추측하지 말고 아래를 우선 처리하라. 숫자는 실측이다.

### A. 서버 컴포넌트 보일러플레이트 — 8개 파일에 같은 20줄
`auth.getUser` 8파일 · `from('memberships')` 7파일 · `unwrapDek`+복호화 6파일 ·
`nameFrom` 함수는 3곳에 각각 정의돼 있다. 매 페이지가 이걸 반복한다:

```
auth 확인 → memberships 로 tenant_id → tenants 에서 dek_wrapped·settings →
unwrapDek → decryptPII 로 이름 꺼내기
```

→ `lib/tenant.ts` 같은 곳에 `requireTenant()` / `withNames()` 를 만들어 한 번만 쓰게 한다.
**주의**: 이건 인증·암호화 경로다. 바꾼 뒤 각 화면이 여전히 로그인 없으면 `/login` 으로
보내고, 남의 테넌트 데이터가 안 보이는지 확인할 것(RLS 가 최종 방어선이지만 앱도 맞아야 한다).

### B. `web/app/customer/[id]/page.tsx` 371줄 — 최대 파일
카르테 하나에 조회·복호화·선불원장·성별·가족·예약·메모·시술이력이 다 들어 있다.
데이터 조립과 표시를 가르고, 카드 단위(선불/가족/한눈에/시술이력)로 컴포넌트를 뽑아라.
`web/app/stats/page.tsx` 297줄도 같은 문제(집계 로직과 렌더가 한 파일).

### C. 같은 규칙이 두 언어에 — 갈라지면 숫자가 어긋난다
- `worker/txkind.py` 의 `classify`/`ledger` ↔ `web/lib/tx.ts` 의 `txKind`/`ledger`
- `web/lib/service-name.ts` 의 `NOT_SERVICE` 어휘 ↔ `worker/txkind.py` 의 정규식

지금은 기대값 대조 테스트로 묶어뒀다(`tests/test_worker_sync.py`).
**한쪽만 고치는 일이 없도록** 규칙 어휘를 한 곳(예: 공유 JSON)에서 읽게 하거나,
최소한 두 파일 서로에게 "여기 고치면 저기도"를 주석으로 남겨라. 지우지 말 것 — 이미
이 프로젝트에서 화면마다 판정이 갈려 버그가 났다(고객목록만 예약 날짜 필터 누락).

### D. `worker/summarize_memos.py` 428줄 · 워커 스크립트 21개
한 파일에 env 로딩·CLI 호출·프롬프트·파싱·배치·진행표시가 섞여 있다.
그리고 `_load_env()` 가 여러 스크립트에 복붙돼 있다 → `worker/env.py` 로 뽑아라.
`gap_check.py`·`gender_probe.py`·`recompute.py`·`summarize_memos.py` 가 모두 같은 서두를 가진다.

### E. `web/app/globals.css` 277줄, 전역 단일 파일
클래스가 화면별로 뒤섞여 있고(`.gpick`, `.tipd`, `.prepaid`, `.memo-ai`, `.gbar`…)
어디서 쓰는지 파일만 봐선 모른다. 최소한 화면별 섹션 주석으로 구획하고, 죽은 규칙을 찾아 지워라.

## 2. 손대면 안 되는 것 (건드리면 실제로 위험)

- **`worker/supa.py` 의 파괴 호출 가드** — 빈 tenant_id 거부, `delete_stale` 의 빈 리스트
  전체삭제 금지(H1), 날짜 범위 한정(H2). 회귀 테스트가 있고, 과거에 전량 삭제 사고 직전까지 갔다.
- **RLS 정책과 `current_tenant_ids()`** — 테넌트 격리의 최종 방어선.
- **봉투 암호화 경로**(`lib/crypto.ts` ↔ `worker/mirrorball_crypto.py`) — 상호운용이 깨지면
  이름이 안 열린다. 크립토 교차검증 테스트를 반드시 통과시킬 것.
- **사람이 넣은 값**: `transactions.paid_out_of_pocket`, `customers.gender_manual`,
  `customers.churned_at`, `customers.memo`. 워커 업서트 payload 에 절대 넣지 마라
  (merge-duplicates 라 payload 에 없어야 보존된다).
- **HandSOS 수집 재가동** 금지 — 약관 19조1항17호로 주 1회로만 돌고 있다(`LAUNCH.md`).

## 3. 작업 규칙

- **한국어 주석**, 기존 톤 유지 — 이 리포의 주석은 "무엇"이 아니라 **"왜 이렇게 했는지"**를 적는다.
  기존 주석에 담긴 사고(사고 사례, 실측 근거)를 리팩토링하면서 지우지 마라. 옮겨라.
- 커밋 메시지도 기존 형식(무엇을 왜, 근거 수치 포함) + 푸터 유지.
- 사용자가 시키기 전 PR 금지. 브랜치에 커밋·푸시.
- 파일을 옮기거나 이름을 바꿀 땐 한 커밋에 하나씩 — 나중에 되짚을 수 있게.

## 4. 첫 턴에 할 일

1. `git fetch` → 최신 확인. `pytest -q` + `tsc --noEmit` 로 출발점 초록불 확인.
2. §1 의 A~E 중 **어디부터 할지 사용자에게 제안**하라(추천: A → B, 효과가 크고 위험이 낮다).
3. 착수 전에 "이 작업으로 바뀌는 파일과, 바뀌지 않을 화면 동작"을 한 줄로 요약해 확인받아라.
