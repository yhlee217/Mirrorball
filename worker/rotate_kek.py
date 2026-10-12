"""마스터 키(KEK) 교체 — 테넌트 키(DEK)·HandSOS 접속 정보·백업 파일만 새 KEK로 다시 감싼다(개선 계획 v5 P0).

봉투 암호화라 손님 이름·전화(테넌트 DEK로 암호화)는 그대로 두고, DEK를 감싼 껍데기만 바꾼다.
그래서 빠르고(매장 수만큼), 손님 데이터를 건드리지 않는다.

준비(playbook/KEY_ROTATION.md):
    맥 web/.env.local · Cloudflare · GitHub 비밀값에 MIRRORBALL_KEK=새 키, MIRRORBALL_KEK_OLD=지금 키.
    웹·워커가 둘 다 읽으므로 그 사이에도 이름이 '고객'으로 보이는 순간이 없다.
사용:
    .venv/bin/python worker/rotate_kek.py            # 미리 보기 — 아무것도 바꾸지 않는다
    .venv/bin/python worker/rotate_kek.py --apply    # 바꾸기 — 하나씩 다시 감싸고 바로 다시 풀어 확인
끝나면 세 곳에서 MIRRORBALL_KEK_OLD 를 지운다. 키 값은 화면에 찍지 않는다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from cryptography.exceptions import InvalidTag

from env import load_env

load_env()

import mirrorball_crypto as mc  # noqa: E402

SAMPLE = 20  # 매장마다 이름이 풀리는지 볼 손님 수


class KeyMismatch(RuntimeError):
    """새 키로도 옛 키로도 안 풀린다 — 다른 키로 감싸인 값이다. 건드리지 않는다."""


def rewrap(blob: str, new: bytes, old: bytes) -> tuple[str, str]:
    """('already', blob) — 이미 새 키 / ('rewrap', 새 blob) — 옛 키로 풀어 새 키로 감쌈.

    다시 감싼 값은 새 키로 바로 풀어 원문과 같은지 확인한다(어긋나면 예외 — 저장하지 않는다).
    """
    try:
        mc.open_with(new, blob)
        return "already", blob
    except InvalidTag:
        pass
    try:
        plain = mc.open_with(old, blob)
    except InvalidTag as exc:
        raise KeyMismatch("새 키로도 옛 키로도 풀리지 않는다") from exc
    out = mc.seal_with(new, plain)
    if mc.open_with(new, out) != plain:
        raise RuntimeError("다시 감싼 값이 원문과 다르다")
    return "rewrap", out


def sample_ok(dek: bytes, blobs: list[str]) -> int:
    """이 DEK로 이름이 풀리는 손님 수 — 다시 감싼 뒤에도 같아야 한다."""
    n = 0
    for b in blobs:
        try:
            mc.decrypt_pii(b, dek)
            n += 1
        except Exception:  # noqa: BLE001 — 깨진 행 하나가 확인을 막지 않게
            pass
    return n


def _keys() -> tuple[bytes, bytes]:
    new_b64 = os.environ.get("MIRRORBALL_KEK")
    old_b64 = os.environ.get("MIRRORBALL_KEK_OLD")
    if not new_b64 or not old_b64:
        raise SystemExit("MIRRORBALL_KEK(새 키)와 MIRRORBALL_KEK_OLD(지금 키)를 둘 다 web/.env.local 에 넣어 주세요 "
                         "— playbook/KEY_ROTATION.md")
    new, old = mc.key_from_b64(new_b64), mc.key_from_b64(old_b64, "MIRRORBALL_KEK_OLD")
    if new == old:
        raise SystemExit("새 키와 옛 키가 같습니다 — 새 키를 만들어 MIRRORBALL_KEK 에 넣어 주세요")
    return new, old


def main() -> int:
    import supa  # 네트워크는 실행할 때만

    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제로 바꾼다(없으면 미리 보기)")
    a = ap.parse_args()
    new, old = _keys()
    mode = "바꾸기" if a.apply else "미리 보기(아무것도 바꾸지 않음)"
    print(f"KEK 교체 — {mode}\n")
    bad = 0

    # ① 테넌트 키(DEK) — 이름·전화를 푸는 열쇠. 다시 감싼 뒤 같은 손님 이름이 풀리는지 본다.
    for t in supa._get("/tenants", {"select": "id,slug,dek_wrapped", "order": "slug"}):
        slug, wrapped = t.get("slug") or t["id"][:8], t.get("dek_wrapped")
        if not wrapped:
            print(f"  [{slug}] 테넌트 키 없음 — 건너뜀")
            continue
        try:
            status, out = rewrap(wrapped, new, old)
        except KeyMismatch:
            print(f"X [{slug}] 테넌트 키가 두 키 어느 쪽으로도 안 풀립니다 — 건드리지 않음")
            bad += 1
            continue
        dek = mc.open_with(new, out)
        rows = supa._get("/customers", {"tenant_id": f"eq.{t['id']}", "select": "pii_enc",
                                        "pii_enc": "not.is.null", "limit": str(SAMPLE)})
        blobs = [r["pii_enc"] for r in rows if r.get("pii_enc")]
        ok = sample_ok(dek, blobs)
        if status == "already":
            print(f"  [{slug}] 이미 새 키 · 이름 {ok}/{len(blobs)} 풀림")
            continue
        if not a.apply:
            print(f"  [{slug}] 다시 감쌀 예정 · 이름 {ok}/{len(blobs)} 풀림")
            continue
        supa.patch("tenants", {"id": f"eq.{t['id']}"}, {"dek_wrapped": out})
        back = supa._get("/tenants", {"id": f"eq.{t['id']}", "select": "dek_wrapped"})[0]["dek_wrapped"]
        after = sample_ok(mc.open_with(new, back), blobs)
        flag = "" if after == ok else "  X 확인 불일치 — 멈추고 살펴보세요"
        print(f"  [{slug}] 다시 감쌈 · 이름 {after}/{len(blobs)} 풀림{flag}")
        bad += after != ok

    # ② HandSOS 접속 정보 — KEK 로 바로 감싸 둔 값(수집이 로그인할 때 쓴다)
    for c in supa._get("/pos_credentials", {"select": "tenant_id,enc_blob,session_cookie"}):
        tid = c["tenant_id"][:8]
        fields = {}
        try:
            for col in ("enc_blob", "session_cookie"):
                if c.get(col):
                    status, out = rewrap(c[col], new, old)
                    if status == "rewrap":
                        fields[col] = out
        except KeyMismatch:
            print(f"X [접속 정보 {tid}] 두 키 어느 쪽으로도 안 풀립니다 — 건드리지 않음")
            bad += 1
            continue
        if not fields:
            print(f"  [접속 정보 {tid}] 이미 새 키")
        elif a.apply:
            supa.patch("pos_credentials", {"tenant_id": f"eq.{c['tenant_id']}"}, fields)
            print(f"  [접속 정보 {tid}] 다시 감쌈({', '.join(fields)})")
        else:
            print(f"  [접속 정보 {tid}] 다시 감쌀 예정({', '.join(fields)})")

    # ③ 백업 파일(worker/backup.py) — 옛 키로 남은 백업도 새 키로. 안 하면 옛 키를 버린 뒤 못 푼다.
    import backup
    done, already, failed = backup.rewrap_files(Path(backup.backup_dir()), new, old, apply=a.apply)
    print(f"  [백업 파일] {'다시 감쌈' if a.apply else '다시 감쌀 예정'} {done}개 · 이미 새 키 {already}개"
          + (f" · X 안 풀림 {failed}개" if failed else ""))
    bad += failed

    print()
    if bad:
        print(f"X 문제 {bad}건 — 위 X 줄을 확인하세요. MIRRORBALL_KEK_OLD 는 아직 지우지 마세요.")
        return 1
    if a.apply:
        print("끝 — 앱에서 손님 이름이 보이는지 확인한 뒤, 세 곳(맥 web/.env.local · Cloudflare · GitHub)에서 "
              "MIRRORBALL_KEK_OLD 를 지우세요.")
    else:
        print("미리 보기 끝 — 문제 없으면 --apply 로 바꾸세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
