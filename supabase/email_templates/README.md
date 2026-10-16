# 로그인 메일 양식 (개선 계획 v15 P0)

앱 로그인은 메일로 온 **6자리 코드**를 홈 화면 앱에 넣는 방식이다(`web/app/login`). Supabase 기본 양식엔 코드가 없고
링크만 있어서, 아래 두 양식으로 바꿔야 메일에 코드가 간다. 키가 아니라 문구라서 그대로 붙여 넣으면 된다.

| Supabase → Authentication → Emails → Templates | 제목 | 본문 |
|---|---|---|
| **Confirm signup** — 처음 로그인하는 이메일 | `[컨시어지] 로그인 코드` | `confirm_signup.html` 내용 |
| **Magic Link** — 이미 있는 계정 | `[컨시어지] 로그인 코드` | `magic_link.html` 내용 |

- `{{ .Token }}` 은 Supabase 가 6자리 코드로 바꿔 넣는다. 링크(`{{ .ConfirmationURL }}`)는 일부러 넣지 않았다 — 아이폰에서
  링크를 누르면 홈 화면 앱이 아니라 사파리에서 로그인되고, 앱은 로그아웃 상태로 남는다.
- 메일 설정(SMTP)을 따로 하지 않았다면 기본 메일은 **프로젝트 팀원 주소로만 · 한 시간에 2통** 간다. 그 전에는 디자이너님께
  메일이 가지 않으니, 맥에서 코드를 만든다: `worker/login_code.py`(`playbook/OPERATIONS_APP.md` §2).
