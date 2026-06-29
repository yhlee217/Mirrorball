# 인스타그램 Graph API 셋업 안내서 (따라하기)

> 목표: 살롱 **기존 인스타 계정**으로 Graph API 토큰을 발급해 `secrets/instagram.yaml` 을 채운다.
> 새 인스타 계정은 안 만든다. 전부 무료. 소요: 약 40~60분(대부분 1회성).
> 설계·지표 설명은 `scripts/INSTAGRAM.md`(보고서) 참고.

준비물: 살롱 인스타 계정 · 페이스북 계정(없으면 무료 생성) · PC 브라우저
※ Meta 화면·메뉴 이름은 수시로 바뀜 — 이름이 다르면 비슷한 항목을 찾으면 된다.

---

## STEP 1. 인스타를 '비즈니스 계정'으로 전환 (폰, 5분)

1. 인스타 앱 → 내 프로필 → 우상단 **☰ (메뉴)** → **설정 및 개인정보**
2. **계정 유형 및 도구** → **프로페셔널 계정으로 전환**
3. 카테고리: **미용실/헤어살롱(Hair Salon)** 선택 → **비즈니스(Business)** 선택
   - (크리에이터도 되지만, 살롱은 **비즈니스** 권장)
4. 완료. 게시물·팔로워 그대로. 언제든 개인계정으로 되돌릴 수 있음.

> 이미 비즈니스/크리에이터면 STEP 1 건너뜀.

---

## STEP 2. 페이스북 페이지 연결 (10분)

Graph API는 보통 **인스타 비즈니스 계정 ↔ 페이스북 페이지** 연결을 요구한다.

1. 페이스북 페이지가 없으면 생성: <https://www.facebook.com/pages/create> → 살롱 이름으로 페이지 생성(무료)
2. 인스타에 연결: 인스타 앱 → 설정 → **비즈니스/계정 센터(Account Center)** → **계정 연결** → 해당 페이스북 페이지 연결
   - 또는 **Meta Business Suite**(business.facebook.com)에서 인스타·페이지를 한 비즈니스에 묶음
3. 확인: Meta Business Suite 에 인스타 계정과 페이지가 같이 보이면 OK

---

## STEP 3. Meta 개발자 앱 만들기 (10분)

1. <https://developers.facebook.com> → 우상단 **로그인**(살롱 페이스북 계정) → 최초면 **개발자 등록**(무료)
2. **내 앱(My Apps)** → **앱 만들기(Create App)**
3. 앱 유형: **비즈니스(Business)** 선택 → 앱 이름(예: `Mirrorball-Insta`) 입력 → 생성
4. 좌측 **제품 추가**에서 **Instagram**(또는 "Instagram Graph API") **설정(Set up)** 추가
5. **앱 설정 → 기본 설정**에서 **앱 ID(App ID)** 와 **앱 시크릿(App secret)** 확인 → `secrets/instagram.yaml` 의 `app_id`/`app_secret` 에 기록
   - 앱 시크릿은 비밀번호급. 절대 공개·커밋 금지(우리는 secrets/ 로 git 제외).

---

## STEP 4. 액세스 토큰 + 인스타 계정 ID 받기 (15분)

### 4-1. Graph API 탐색기로 단기 토큰
1. <https://developers.facebook.com/tools/explorer> (Graph API Explorer)
2. 우측 **Meta App**: STEP 3 의 앱 선택
3. **User or Page**: *User Token* → **Add Permissions** 에서 아래 권한 체크:
   - `instagram_basic`
   - `instagram_manage_insights`
   - `instagram_manage_comments`
   - `pages_show_list`
   - `pages_read_engagement`
   - `business_management`
4. **Generate Access Token** → 페이스북 로그인·동의 → 단기 토큰 생성

### 4-2. 인스타 비즈니스 계정 ID 찾기
탐색기 주소창(또는 GET 요청)에 순서대로:

```
GET /me/accounts
   → 결과에서 살롱 페이지의 "id"(page-id) 확인

GET /{page-id}?fields=instagram_business_account
   → 결과의 instagram_business_account.id  ←  이게 ig_user_id
```

→ `ig_user_id` 를 `secrets/instagram.yaml` 에 기록.

### 4-3. 단기 → 장기(60일) 토큰 교환
브라우저 주소창에 (값 채워서):

```
https://graph.facebook.com/v23.0/oauth/access_token?grant_type=fb_exchange_token&client_id={app_id}&client_secret={app_secret}&fb_exchange_token={단기토큰}
```

→ 반환된 `access_token`(장기, 60일)을 `secrets/instagram.yaml` 의 `access_token` 에 기록.
※ 무기한이 필요하면 **시스템 유저 토큰**(Business Settings → System Users)을 발급 — 갱신 부담 없음(후속).

---

## STEP 5. secrets/instagram.yaml 채우기

```powershell
copy secrets\instagram.example.yaml secrets\instagram.yaml
notepad secrets\instagram.yaml
```

```yaml
ig_user_id: "1784xxxxxxxxxxx"
access_token: "EAAG...(장기 토큰)"
app_id: "1234567890"
app_secret: "abcd...(공개 금지)"
hashtags: ["영등포미용실", "영등포레이어드컷", "레이어드펌", "살롱톤", "하예원", ...]   # 7일당 30개 한도
competitors: ["경쟁살롱username1", "경쟁살롱username2"]                                  # 비즈니스 계정만
```

`secrets/` 는 git 에서 제외됨(토큰 안전). 템플릿만 추적됨.

---

## STEP 6. 연결 테스트 (1분)

토큰이 살아있는지 확인:

```powershell
curl "https://graph.facebook.com/v23.0/{ig_user_id}?fields=username,followers_count,media_count&access_token={access_token}"
```

→ `{"username":"salontone_...","followers_count":1234,"media_count":567,...}` 가 나오면 성공.

해시태그 검색 동작 확인(선택):
```
GET /ig_hashtag_search?user_id={ig_user_id}&q=영등포레이어드컷
   → 해시태그 id 반환되면 OK (이 id 로 recent_media/top_media 조회)
```

---

## 자주 막히는 곳

| 증상 | 원인·해결 |
|---|---|
| `instagram_business_account` 가 비어있음 | 인스타가 비즈니스 계정이 아니거나 페이지 연결 안 됨 → STEP 1·2 재확인 |
| 권한 오류(#10, #200) | 토큰에 해당 권한 미포함 → 4-1 권한 다시 체크해 재발급 |
| 경쟁사 조회 시 빈 결과 | 상대가 **개인/비공개 계정** → Graph API 로는 안 보임(해시태그 언급으로만 포착) |
| 토큰 60일 후 만료 | 4-3 재교환 또는 시스템 유저 토큰으로 무기한 발급 |
| 해시태그 조회 막힘 | 7일당 30개 한도 초과 → 추적 해시태그 줄이기 |
| 타 계정 공개데이터 접근 거부 | 앱이 개발 모드 → 본인 계정만이면 OK, 확장 시 Meta **앱 검수** 필요 |

---

## 다음

`secrets/instagram.yaml` 이 채워지고 STEP 6 테스트가 통과하면 → `insta_collect.py`(수집) + `insta.py`(지표)
를 붙여 **인스타 발견 점수(언급·점유율·트렌드·인게이지먼트)** 를 주간 추세로 만든다.
