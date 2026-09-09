"""거래 종류 판정과 선불 잔액 계산 — 한 곳에서만.

화면마다 따로 판정하면 반드시 갈라진다(고객 목록만 예약 날짜 필터를 빠뜨렸던 것처럼).
분류는 여기서 하고 결과를 transactions.kind 에 저장해, 앱은 읽기만 한다.
어휘는 web/lib/service-name.ts 의 NOT_SERVICE 와 맞춘다.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# 판정 어휘는 웹과 공유한다 — 규칙이 두 언어에 복사돼 있으면 한쪽에만 메뉴를 추가하는 순간
# 화면과 집계가 어긋난다. 계산 방법(원장)만 각자 구현하고, '무엇으로 분류하는가'는 한 파일에서 읽는다.
_RULES_PATH = Path(__file__).resolve().parent.parent / "web" / "lib" / "tx-rules.json"
_RULES = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
_ORDER = _RULES["order"]
_RE = {k: re.compile("|".join(map(re.escape, v))) for k, v in _RULES["patterns"].items()}


def classify(service: str | None) -> str:
    """service | charge | product | refund. 시술명이 없으면 시술로 본다(대다수)."""
    s = service or ""
    for kind in _ORDER:          # 순서가 의미를 갖는다(환불이 충전보다 앞)
        if _RE[kind].search(s):
            return kind
    return "service"


def ledger(items: list[dict]) -> dict:
    """고객 한 명의 거래를 시간순으로 훑어 실매출과 선불 잔액을 낸다.

    items: [{date, amount, kind, out_of_pocket}] — 날짜 오름차순일 필요 없음(여기서 정렬).

    매출 정의(B안) = 고객이 실제로 낸 돈 = 충전액 + 사비로 결제한 시술·제품.
    충전금으로 결제한 시술은 이미 충전 시점에 계상됐으므로 다시 더하지 않는다.

    POS 에 결제수단이 없어 '충전금으로 냈는지'는 추정할 수밖에 없다. 다만 무한정 차감하지 않고
    **잔액이 남아 있는 동안만** 차감한다. 잔액이 바닥나면 그 뒤 시술은 사비로 보고 매출에 넣는다
    (그래서 추정이 스스로 교정된다). 사장님이 개별 건을 '사비'로 표시하면 잔액을 건드리지 않는다.
    """
    balance = 0          # 추정 선불 잔액
    revenue = 0          # 실제로 받은 돈
    charged = 0          # 충전 총액(표시용)
    covered = 0          # 잔액으로 결제된 것으로 본 금액(표시용)
    per_tx: dict = {}    # 거래 id → 잔액으로 결제된 금액. 통계가 월별로 합산할 때 쓴다

    # 같은 날 충전과 시술이 같이 있으면 순서가 결과를 바꾼다 — 시각까지 보고 정렬한다.
    for it in sorted(items, key=lambda x: (x.get("date") or "", x.get("time") or "", x.get("id") or "")):
        amt = int(it.get("amount") or 0)
        kind = it.get("kind") or "service"

        if kind == "charge":
            balance += amt
            charged += amt
            revenue += amt
            continue

        if kind == "refund":
            revenue += amt              # 환불은 보통 음수로 들어온다
            continue

        # 시술·제품
        if it.get("out_of_pocket"):     # 사람이 '사비'로 표시 → 잔액 건드리지 않음
            revenue += amt
            continue
        if balance <= 0:
            revenue += amt              # 잔액 없음 → 사비
            continue
        use = min(balance, amt)         # 잔액이 부족하면 부족분만 사비
        balance -= use
        covered += use
        revenue += amt - use
        if use and it.get("id"):
            per_tx[it["id"]] = use

    return {"revenue": revenue, "balance": balance, "charged": charged,
            "covered": covered, "per_tx": per_tx}
