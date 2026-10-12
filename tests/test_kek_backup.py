"""키 교체(worker/rotate_kek.py) · 옛 키 함께 읽기 · 앱 데이터 백업(worker/backup.py) — 개선 계획 v5 P0·P1.

키를 바꾸는 동안 이름이 '고객'으로 보이면 안 되고(웹·워커 둘 다 옛 키로도 읽는다), 바꾼 뒤에는 새 키로만
풀려야 한다. 백업은 담고 → 감싸고 → 풀고 → 되살릴 일까지 왕복해 같은지 본다. 네트워크 없이 계산만.
웹(lib/crypto.ts)은 tsc → node(tests/tsnode.py)로 파이썬이 감싼 값을 푼다 — 두 구현이 같은 형식이라서다.
"""

from __future__ import annotations

import base64
import datetime as dt
import os
import sys
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag

from tsnode import run_ts

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

import backup  # noqa: E402
import mirrorball_crypto as mc  # noqa: E402
import rotate_kek  # noqa: E402

OLD = os.urandom(32)
NEW = os.urandom(32)
OTHER = os.urandom(32)
B64 = lambda k: base64.b64encode(k).decode()  # noqa: E731
DEK = os.urandom(32)


@pytest.fixture
def rotating(monkeypatch):
    """교체 중 — 새 키가 지금 키, 옛 키를 함께 둔다."""
    monkeypatch.setenv("MIRRORBALL_KEK", B64(NEW))
    monkeypatch.setenv("MIRRORBALL_KEK_OLD", B64(OLD))


def test_worker_reads_old_key_while_rotating(rotating, monkeypatch):
    wrapped = mc.seal_with(OLD, DEK)                       # 아직 옛 키로 감싸인 테넌트 키
    assert mc.unwrap_dek(wrapped) == DEK
    creds = mc.seal_with(OLD, b'{"id": "x"}')
    assert mc.kek_decrypt_json(creds) == {"id": "x"}
    monkeypatch.delenv("MIRRORBALL_KEK_OLD")               # 옛 키를 지우면 더는 안 풀린다
    with pytest.raises(InvalidTag):
        mc.unwrap_dek(wrapped)


def test_new_wraps_use_the_current_key(rotating):
    assert mc.open_with(NEW, mc.wrap_dek(DEK)) == DEK


def test_rewrap_moves_old_to_new_and_is_idempotent():
    status, out = rotate_kek.rewrap(mc.seal_with(OLD, DEK), NEW, OLD)
    assert status == "rewrap" and mc.open_with(NEW, out) == DEK
    with pytest.raises(InvalidTag):
        mc.open_with(OLD, out)                             # 바꾼 뒤엔 옛 키로 안 풀린다
    assert rotate_kek.rewrap(out, NEW, OLD) == ("already", out)
    with pytest.raises(rotate_kek.KeyMismatch):
        rotate_kek.rewrap(mc.seal_with(OTHER, DEK), NEW, OLD)


def test_sample_counts_names_that_open():
    good = [mc.encrypt_pii({"name": f"손님{i}"}, DEK) for i in range(3)]
    assert rotate_kek.sample_ok(DEK, good + [mc.encrypt_pii({"name": "x"}, OTHER), "깨진값"]) == 3


# ── 백업 ──────────────────────────────────────────────────────────────────

TENANT = {"id": "t1", "slug": "demo", "salon_name": "살롱", "designer_name": "하예원",
          "settings": {"off_weekdays": [1]}, "dek_wrapped": "담지 않는다"}
CUSTOMERS = [
    {"id": "c1", "ext_id": "101", "memo": "두피 예민", "prefer_tags": ["볼륨"], "churned_at": None, "gender_manual": None},
    {"id": "c2", "ext_id": "102", "memo": None, "prefer_tags": [], "churned_at": "2026-09-01T00:00:00Z", "gender_manual": "F"},
    {"id": "c3", "ext_id": "103", "memo": None, "prefer_tags": [], "churned_at": None, "gender_manual": None},  # 앱 기록 없음
    {"id": "c4", "ext_id": "104", "memo": "앞머리 짧게 싫어함", "prefer_tags": [], "churned_at": None, "gender_manual": None},
]
CONTACTS = [{"customer_id": "c1", "why": "sms", "sent_at": "2026-10-12T01:00:00Z"},
            {"customer_id": "c3", "why": "call", "sent_at": "2026-10-12T02:00:00Z"}]


def payload():
    return backup.collect(TENANT, CUSTOMERS, ["tx9", "tx2"], CONTACTS, {"tagline": "안녕하세요"},
                          [{"user_id": "u1", "role": "owner"}], {"enc_blob": "감싼값"}, "2026-10-18T05:00:00Z")


def test_collect_keeps_only_app_data():
    p = payload()
    assert [c["ext_id"] for c in p["customers"]] == ["101", "102", "104"]   # 앱 기록 없는 손님은 빼고
    assert "dek_wrapped" not in p["tenant"] and "name" not in p["customers"][0]   # 이름·키는 담지 않는다
    assert p["pocket"] == ["tx2", "tx9"]
    assert p["contacts"] == [{"ext_id": "101", "why": "sms", "sent_at": "2026-10-12T01:00:00Z"},
                             {"ext_id": "103", "why": "call", "sent_at": "2026-10-12T02:00:00Z"}]


def test_seal_round_trip_and_old_key():
    text = backup.seal(payload(), OLD)
    assert backup.unseal(text, [NEW, OLD]) == payload()    # 교체 중엔 옛 키로도
    with pytest.raises(InvalidTag):
        backup.unseal(text, [NEW])


def test_plan_restore_maps_by_ext_id():
    # 다시 수집해 손님 id 가 바뀐 DB — 104 는 아직 없다. c1 의 연락은 이미 있다.
    ids = {"101": "n1", "102": "n2", "103": "n3"}
    plan = backup.plan_restore(payload(), ids, existing={("n1", "2026-10-12T01:00:00Z")})
    assert [c["id"] for c in plan["customers"]] == ["n1", "n2"] and plan["missing"] == 1
    assert plan["customers"][1]["gender_manual"] == "F"
    assert plan["contacts"] == [{"customer_id": "n3", "why": "call", "sent_at": "2026-10-12T02:00:00Z"}]
    assert plan["pocket"] == ["tx2", "tx9"]


def test_prune_keeps_eight_weeks(tmp_path):
    for d in ("2026-08-01", "2026-08-30", "2026-10-11", "메모"):
        (tmp_path / d).mkdir()
    assert backup.prune(tmp_path, dt.date(2026, 10, 18)) == ["2026-08-01"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["2026-08-30", "2026-10-11", "메모"]


def test_rewrap_backup_files(tmp_path):
    day = tmp_path / "2026-10-18"
    day.mkdir()
    (day / "a.json.enc").write_text(backup.seal(payload(), OLD))
    (day / "b.json.enc").write_text(backup.seal(payload(), NEW))
    (day / "c.json.enc").write_text(backup.seal(payload(), OTHER))
    assert backup.rewrap_files(tmp_path, NEW, OLD, apply=False) == (1, 1, 1)
    assert backup.unseal((day / "a.json.enc").read_text(), [OLD]) == payload()   # 미리 보기는 그대로
    assert backup.rewrap_files(tmp_path, NEW, OLD, apply=True) == (1, 1, 1)
    assert backup.unseal((day / "a.json.enc").read_text(), [NEW]) == payload()


# ── 웹도 옛 키로 읽는다 ─────────────────────────────────────────────────────

def test_web_reads_old_key_while_rotating():
    wrapped = mc.seal_with(OLD, DEK)
    got = run_ts(["lib/crypto.ts"], """
const C = require('./crypto.js');
(async () => {
  process.env.MIRRORBALL_KEK = D.new;
  process.env.MIRRORBALL_KEK_OLD = D.old;
  const a = Buffer.from(await C.unwrapDek(D.wrapped)).toString('base64');
  delete process.env.MIRRORBALL_KEK_OLD;
  let after = 'opened';
  try { await C.unwrapDek(D.wrapped); } catch { after = 'rejected'; }
  out({ a, after });
})();
""", {"new": B64(NEW), "old": B64(OLD), "wrapped": wrapped})
    if got is None:
        pytest.skip("node/npx 또는 web/node_modules 가 없다 — TS 실행 생략")
    assert got == {"a": B64(DEK), "after": "rejected"}
