"""열쇠 한 부 확인 · 백업 다시 읽기(개선 계획 v15 P1) — 네트워크 없이.

열쇠를 다시 읽을 수 있는 곳이 맥 한 곳뿐이라 비밀번호 관리자에 한 부 둔다. 옮겨 적다 한 글자만 틀려도 그 한 부는
쓸모가 없다 — '같다 · 다르다'만 말하고 값은 찍지 않는다. 백업은 쓰자마자 다시 열어 풀리는지 본다.
"""

from __future__ import annotations

import base64
import os
import sys
import types
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import backup  # noqa: E402
import kek_check as kc  # noqa: E402
import mirrorball_crypto as mc  # noqa: E402

KEY = os.urandom(32)
OTHER = os.urandom(32)
B64 = lambda k: base64.b64encode(k).decode()  # noqa: E731


def test_same_key_ignores_spaces_and_tells_only_same_or_not():
    assert kc.same_key(B64(KEY), KEY) == "same"
    assert kc.same_key(f"  {B64(KEY)}\n", KEY) == "same"                 # 붙여 넣을 때 딸려 오는 빈칸 · 줄바꿈
    assert kc.same_key(B64(OTHER), KEY) == "different"
    assert kc.same_key(B64(KEY)[:-4], KEY) == "not_a_key"               # 끝 몇 글자가 빠짐
    assert kc.same_key(B64(os.urandom(16)), KEY) == "not_a_key"
    assert kc.same_key("비밀번호 아님!", KEY) == "not_a_key"
    assert kc.same_key("", KEY) == "skip" and kc.same_key("   ", KEY) == "skip"


def test_tenant_lines_use_only_the_current_key():
    dek = os.urandom(32)
    tenants = [{"slug": "hayewoni", "dek_wrapped": mc.seal_with(KEY, dek)},
               {"slug": "juhwan", "dek_wrapped": mc.seal_with(OTHER, dek)},
               {"slug": "demo-1a2b3c4d", "dek_wrapped": None}]
    lines, bad = kc.tenant_lines(tenants, KEY)
    assert bad == 1
    assert lines[0] == "  [hayewoni] 매장 열쇠 풀림" and lines[1].startswith("X [juhwan] 지금 열쇠로 안 풀림")
    assert "매장 열쇠 없음" in lines[2]


def _run(monkeypatch, capsys, tenants, answer, old=None):
    monkeypatch.setenv("MIRRORBALL_KEK", B64(KEY))
    if old:
        monkeypatch.setenv("MIRRORBALL_KEK_OLD", B64(old))
    else:
        monkeypatch.delenv("MIRRORBALL_KEK_OLD", raising=False)
    monkeypatch.setitem(sys.modules, "supa", types.SimpleNamespace(_get=lambda path, params: tenants))
    code = kc.main(["x"], ask=lambda prompt: answer)
    return code, capsys.readouterr().out


def test_main_says_same_or_different_and_never_prints_the_key(monkeypatch, capsys):
    ok = [{"slug": "hayewoni", "dek_wrapped": mc.seal_with(KEY, os.urandom(32))}]
    code, out = _run(monkeypatch, capsys, ok, B64(KEY))
    assert code == 0 and "같아요" in out and "[hayewoni] 매장 열쇠 풀림" in out
    assert B64(KEY) not in out and B64(KEY)[:12] not in out                    # 값은 어디에도 안 찍힌다
    code, out = _run(monkeypatch, capsys, ok, B64(OTHER))
    assert code == 1 and "달라요" in out and B64(OTHER) not in out
    code, out = _run(monkeypatch, capsys, ok, "")
    assert code == 0 and "건너뜀" in out
    bad = [{"slug": "juhwan", "dek_wrapped": mc.seal_with(OTHER, os.urandom(32))}]
    code, out = _run(monkeypatch, capsys, bad, B64(KEY))
    assert code == 1 and "X [juhwan]" in out                                    # 맥의 열쇠가 DB 와 다르면 실패
    code, out = _run(monkeypatch, capsys, ok, B64(KEY), old=OTHER)
    assert "열쇠 교체 중" in out


def test_backup_is_read_back_right_after_writing(tmp_path):
    payload = {"v": 1, "tenant": {"slug": "hayewoni"}, "customers": [{"ext_id": "101", "memo": "단골 · 짧게"}],
               "pocket": ["tx2"], "contacts": []}
    path = tmp_path / "hayewoni.json.enc"
    path.write_text(backup.seal(payload, KEY), encoding="utf-8")
    backup.verify_written(path, KEY, payload)                                    # 풀리고 같다 — 조용히 지나간다
    with pytest.raises(InvalidTag):
        backup.verify_written(path, OTHER, payload)                              # 다른 열쇠로는 안 풀린다
    with pytest.raises(RuntimeError):
        backup.verify_written(path, KEY, {**payload, "pocket": []})              # 담은 것과 다르면 실패
    path.write_text(backup.seal(payload, KEY)[:-8] + "AAAAAAAA", encoding="utf-8")
    with pytest.raises(InvalidTag):
        backup.verify_written(path, KEY, payload)                                # 깨진 파일


def test_run_backup_checks_each_file_and_records_it():
    src = (ROOT / "worker" / "backup.py").read_text(encoding="utf-8")
    body = src[src.index("def run_backup"):src.index("def run_restore")]
    assert body.index("path.write_text(seal(payload, key)") < body.index("verify_written(path, key, payload)")
    assert body.index("verify_written(path, key, payload)") < body.index('"checked": True')
    assert body.index('"checked": True') < body.index('supa.insert("ops_events"')   # 확인한 뒤에만 '백업됨'
