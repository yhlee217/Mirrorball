"""워커용 봉투 암호화 — web/lib/crypto.ts 와 완전 상호운용.

형식: base64( iv(12) || ciphertext || GCM태그(16) ).
KEK(마스터, env MIRRORBALL_KEK) → 테넌트별 DEK(랜덤 32B, KEK로 래핑) → PII 필드 암호화.
파이썬 cryptography.AESGCM 의 ct 는 ciphertext||tag 라 노드(iv||ct||tag)와 바이트가 동일.
"""

from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _kek() -> bytes:
    b64 = os.environ.get("MIRRORBALL_KEK")
    if not b64:
        raise RuntimeError("MIRRORBALL_KEK 미설정")
    k = base64.b64decode(b64)
    if len(k) != 32:
        raise RuntimeError("MIRRORBALL_KEK 는 base64(32 bytes) 여야 함")
    return k


def _seal(key: bytes, plaintext: bytes) -> str:
    iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, plaintext, None)  # ct = ciphertext || tag(16)
    return base64.b64encode(iv + ct).decode("ascii")


def _open(key: bytes, blob_b64: str) -> bytes:
    raw = base64.b64decode(blob_b64)
    iv, ct = raw[:12], raw[12:]
    return AESGCM(key).decrypt(iv, ct, None)


def generate_dek() -> bytes:
    return os.urandom(32)


def wrap_dek(dek: bytes) -> str:
    return _seal(_kek(), dek)


def unwrap_dek(wrapped_b64: str) -> bytes:
    return _open(_kek(), wrapped_b64)


def encrypt_pii(obj, dek: bytes) -> str:
    return _seal(dek, json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def decrypt_pii(blob_b64: str, dek: bytes):
    return json.loads(_open(dek, blob_b64).decode("utf-8"))


def kek_encrypt_json(obj) -> str:
    """POS 자격증명 등 KEK로 직접 암호화(테넌트 DEK 없이 워커가 복호화)."""
    return _seal(_kek(), json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def kek_decrypt_json(blob_b64: str):
    return json.loads(_open(_kek(), blob_b64).decode("utf-8"))
