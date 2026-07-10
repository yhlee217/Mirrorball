#!/usr/bin/env python3
"""앱 데이터 암호화 — build_app_site 가 배포 전 data/{slug}.json 을 '봉투'로 암호화한다.

앱(app/index.html 의 <appcrypto>)이 비밀번호로 복호화한다. 표준
PBKDF2-SHA256(키유도) + AES-256-GCM(암호화)이라 브라우저 Web Crypto 와 상호호환.
비밀번호는 로컬 전용(secrets/deploy.env, gitignore) — 배포물엔 암호문만 나가므로
공개 URL 을 알아도 비밀번호 없이는 아무것도 못 읽는다.

봉투 형식(JSON): {v, alg:"AES-GCM", kdf:"PBKDF2-SHA256", iter, salt, iv, ct} (salt/iv/ct 는 base64).
AES-GCM 암호문(ct)은 끝에 16바이트 인증태그가 붙는다 — Web Crypto decrypt 가 그대로 받는 형식.
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

# OWASP 권장선(PBKDF2-HMAC-SHA256). 폰에서 최초 잠금해제 시 ~1초 내외.
DEFAULT_ITER = 600_000


def encrypt_bytes(plaintext: bytes, passphrase: str, iterations: int = DEFAULT_ITER) -> dict:
    """평문 바이트 → 봉투 dict. salt/iv 는 매번 랜덤(같은 입력도 매번 다른 암호문)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    if not passphrase:
        raise ValueError("passphrase 가 비어있음 — 앱 비밀번호를 설정하세요")
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations, dklen=32)
    iv = os.urandom(12)                                 # GCM 표준 96-bit nonce
    ct = AESGCM(key).encrypt(iv, plaintext, None)       # ct = 암호문 || 16바이트 태그
    enc = base64.b64encode
    return {"v": 1, "alg": "AES-GCM", "kdf": "PBKDF2-SHA256", "iter": iterations,
            "salt": enc(salt).decode("ascii"), "iv": enc(iv).decode("ascii"),
            "ct": enc(ct).decode("ascii")}


def encrypt_text(text: str, passphrase: str, iterations: int = DEFAULT_ITER) -> dict:
    return encrypt_bytes(text.encode("utf-8"), passphrase, iterations)


def decrypt_envelope(env: dict, passphrase: str) -> bytes:
    """봉투 → 평문 바이트. 비밀번호가 틀리면 GCM 인증 실패로 예외(InvalidTag)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = base64.b64decode(env["salt"])
    iv = base64.b64decode(env["iv"])
    ct = base64.b64decode(env["ct"])
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt,
                              int(env.get("iter", DEFAULT_ITER)), dklen=32)
    return AESGCM(key).decrypt(iv, ct, None)


def is_envelope(obj) -> bool:
    return isinstance(obj, dict) and all(k in obj for k in ("ct", "iv", "salt", "kdf"))


def load_passphrase(root: str | Path) -> str | None:
    """앱 비밀번호 조회 — 환경변수 MIRRORBALL_APP_PASSPHRASE 우선, 없으면 secrets/deploy.env 파싱.

    둘 다 gitignore(로컬 전용). 런너는 deploy.env 를 source 하므로 환경변수로 들어온다."""
    pw = os.environ.get("MIRRORBALL_APP_PASSPHRASE")
    if pw:
        return pw
    envf = Path(root) / "secrets" / "deploy.env"
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("MIRRORBALL_APP_PASSPHRASE="):
                val = line.split("=", 1)[1].strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                    val = val[1:-1]                      # 따옴표로 감쌌으면 벗김
                return val or None
    return None
