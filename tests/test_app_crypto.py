"""app_crypto — 데이터 암호화 봉투 라운드트립·비밀번호 조회 회귀(브라우저 불필요).

배포 데이터 보호의 파이썬 절반: 암호화→복호화 왕복, 틀린 비번 실패, 랜덤 salt/iv,
빈 비번 거부, 비밀번호 로컬 조회(env / deploy.env). JS 절반은 test_app_crypto_interop.py.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app_crypto


def test_roundtrip_unicode():
    env = app_crypto.encrypt_text("안녕 hayewoni 🎈", "pw-strong-123", iterations=20000)
    assert app_crypto.decrypt_envelope(env, "pw-strong-123").decode("utf-8") == "안녕 hayewoni 🎈"


def test_envelope_shape():
    env = app_crypto.encrypt_text("x", "pw", iterations=1000)
    assert env["alg"] == "AES-GCM" and env["kdf"] == "PBKDF2-SHA256"
    for k in ("v", "iter", "salt", "iv", "ct"):
        assert k in env
    assert app_crypto.is_envelope(env)


def test_wrong_passphrase_raises():
    env = app_crypto.encrypt_text("secret", "right-pass", iterations=1000)
    with pytest.raises(Exception):
        app_crypto.decrypt_envelope(env, "wrong-pass")


def test_random_salt_iv_each_time():
    a = app_crypto.encrypt_text("same", "pw", iterations=1000)
    b = app_crypto.encrypt_text("same", "pw", iterations=1000)
    assert a["ct"] != b["ct"] and a["salt"] != b["salt"] and a["iv"] != b["iv"]


def test_empty_passphrase_raises():
    with pytest.raises(ValueError):
        app_crypto.encrypt_text("x", "")


def test_is_envelope_false_for_plain():
    assert not app_crypto.is_envelope({"slug": "hayewoni", "clients": []})


def test_load_passphrase_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MIRRORBALL_APP_PASSPHRASE", "from-env-pw")
    assert app_crypto.load_passphrase(tmp_path) == "from-env-pw"


def test_load_passphrase_from_deploy_env(monkeypatch, tmp_path):
    monkeypatch.delenv("MIRRORBALL_APP_PASSPHRASE", raising=False)
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "deploy.env").write_text(
        'NETLIFY_SITE_ID=abc\nMIRRORBALL_APP_PASSPHRASE="quoted pass 12"\n', encoding="utf-8")
    assert app_crypto.load_passphrase(tmp_path) == "quoted pass 12"


def test_load_passphrase_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.delenv("MIRRORBALL_APP_PASSPHRASE", raising=False)
    assert app_crypto.load_passphrase(tmp_path) is None
