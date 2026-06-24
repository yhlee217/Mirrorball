#!/usr/bin/env python3
"""고객 간 관계(가족·친구·소개) 해석.

고객 yaml 에 선언한 관계를 양방향으로 풀어 앱 카르테에 띄운다.
  relations:           # 상호 관계
    - to: park         # 다른 고객 id
      type: 친구        # 가족 | 친구 | 자매 | 모녀 ...
  referred_by: park    # 이 고객을 소개한 사람(단방향) → 소개해준 단골에게 감사

소개는 관리의 핵심: '누가 누구를 데려왔나'를 보면 감사·로열티로 이어진다.
"""

from __future__ import annotations

from collections import defaultdict


def resolve(customers: list[dict]) -> dict[str, dict]:
    """{id: {relations:[{id,name,type}], referred_by:{id,name}|None, referred:[{id,name}]}}"""
    by_id = {c.get("id"): c for c in customers if c.get("id")}

    def name_of(cid: str) -> str:
        c = by_id.get(cid)
        return (c.get("name") if c else None) or cid

    # 역방향: 내가 소개한 사람들
    brought = defaultdict(list)
    for c in customers:
        rb = c.get("referred_by")
        if rb:
            brought[rb].append(c.get("id"))

    out: dict[str, dict] = {}
    for c in customers:
        cid = c.get("id")
        if not cid:
            continue
        rels = [
            {"id": r.get("to"), "name": name_of(r.get("to")), "type": r.get("type", "지인")}
            for r in (c.get("relations") or [])
            if r.get("to")
        ]
        rb = c.get("referred_by")
        referred_by = {"id": rb, "name": name_of(rb)} if rb and rb in by_id else None
        referred = [{"id": i, "name": name_of(i)} for i in brought.get(cid, [])]
        out[cid] = {"relations": rels, "referred_by": referred_by, "referred": referred}
    return out
