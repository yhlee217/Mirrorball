"""열쇠(KEK) 한 부 확인 — 맥에서(개선 계획 v15 P1). 열쇠 값은 어디에도 찍지 않는다.

열쇠는 맥 web/.env.local · Cloudflare · GitHub 세 곳에 있지만, Cloudflare · GitHub 는 넣기만 되고 다시 볼 수 없다.
맥이 고장 나거나 없어지면 모든 매장의 손님 이름 · 번호와 HandSOS 접속 정보를 풀 수 없다 — 그래서 비밀번호 관리자
(아이폰 '암호' 앱 · 1Password 등)에 한 부 둔다. 채팅 · 문서 · 메신저엔 여전히 붙여 넣지 않는다.

이 스크립트는 둘만 본다:
    1) 지금 열쇠로 매장마다 열쇠(DEK)가 풀리나 — 맥의 열쇠가 DB 와 맞는 열쇠인가
    2) 비밀번호 관리자에 적은 값이 지금 열쇠와 같은가 — 붙여 넣으면(화면에 안 보임) '같아요 / 달라요'만

사용:
    .venv/bin/python worker/kek_check.py
"""

from __future__ import annotations

import base64
import binascii
import getpass
import hmac
import sys

from cryptography.exceptions import InvalidTag

from env import load_env

load_env()

import mirrorball_crypto as mc  # noqa: E402


def same_key(copied: str, current: bytes) -> str:
    """'same' · 'different' · 'not_a_key'(열쇠 모양이 아님) · 'skip'(빈 값). 앞뒤 빈칸 · 줄바꿈은 무시한다."""
    text = "".join((copied or "").split())
    if not text:
        return "skip"
    try:
        key = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        return "not_a_key"
    if len(key) != 32:
        return "not_a_key"
    return "same" if hmac.compare_digest(key, current) else "different"


def tenant_lines(tenants: list[dict], key: bytes) -> tuple[list[str], int]:
    """매장마다 지금 열쇠로 매장 열쇠가 풀리나 — (출력 줄, 안 풀린 매장 수). 옛 열쇠로 대신 풀지 않는다."""
    lines, bad = [], 0
    for t in tenants:
        slug, wrapped = t.get("slug") or str(t.get("id", ""))[:8], t.get("dek_wrapped")
        if not wrapped:
            lines.append(f"  [{slug}] 매장 열쇠 없음 — 손님 이름을 아직 담지 않은 매장")
            continue
        try:
            mc.open_with(key, wrapped)
            lines.append(f"  [{slug}] 매장 열쇠 풀림")
        except (InvalidTag, ValueError, binascii.Error):
            lines.append(f"X [{slug}] 지금 열쇠로 안 풀림 — 맥의 열쇠가 DB 와 다른 열쇠다")
            bad += 1
    return lines, bad


SAY = {
    "same": "같아요 — 맥이 없어져도 이 값으로 되살릴 수 있어요",
    "different": "X 달라요 — 비밀번호 관리자에 다시 복사해 넣으세요(앞뒤 글자가 빠지기 쉽다)",
    "not_a_key": "X 열쇠 모양이 아니에요(base64 32바이트) — 비밀번호 관리자에 다시 복사해 넣으세요",
    "skip": "(비밀번호 관리자 값 비교는 건너뜀)",
}


def main(argv: list[str], ask=getpass.getpass) -> int:
    import supa

    key = mc._kek()
    if mc._kek_old() is not None:
        print("! 열쇠 교체 중이에요(MIRRORBALL_KEK_OLD 가 남아 있다) — 교체를 끝낸 뒤 새 열쇠를 적어 두세요")
    tenants = supa._get("/tenants", {"select": "id,slug,dek_wrapped", "order": "slug"})
    lines, bad = tenant_lines(tenants, key)
    print("지금 열쇠(맥 web/.env.local 의 MIRRORBALL_KEK)\n" + "\n".join(lines))
    result = same_key(ask("\n비밀번호 관리자에 적은 열쇠를 붙여 넣으세요(화면에 안 보여요 · 건너뛰려면 엔터): "), key)
    print(SAY[result])
    return 1 if bad or result in ("different", "not_a_key") else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
