#!/usr/bin/env python3
"""HandSOS 가족고객 현황(c_Family.asp) 파싱 → 고객번호(ext_id)→가족번호 매핑.

가족번호(6자리) 행이 그룹 헤더, 이어지는 행은 같은 가족(carry-forward).
고객번호는 7자리(0으로 패딩, 우리 customers.ext_id 와 동일). 순수 함수(테스트 가능).
"""
from __future__ import annotations

import html
import re


def _cells(tr: str) -> list[str]:
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(td))).strip()
            for td in re.findall(r"<td\b[^>]*>(.*?)</td>", tr, re.S | re.I)]


def parse_families(htmls: list[str]) -> dict[str, str]:
    """[페이지 HTML...] → {고객번호(7자리): 가족번호(6자리)}.

    한 페이지 안에서 가족번호(6자리) 셀을 만나면 현재 가족을 갱신하고, 이후 행의
    고객번호(7자리)를 그 가족에 귀속시킨다. 6자리=가족번호, 7자리=고객번호로 구분(날짜·금액은
    하이픈·콤마가 있어 미매치)."""
    mp: dict[str, str] = {}
    for h in htmls:
        cur: str | None = None
        for tr in re.findall(r"<tr\b.*?</tr>", h or "", re.S | re.I):
            cs = _cells(tr)
            fno = next((c for c in cs if re.fullmatch(r"\d{6}", c)), None)
            if fno:
                cur = fno
            cust = next((c for c in cs if re.fullmatch(r"\d{7}", c)), None)
            if cust and cur:
                mp[cust] = cur
    return mp
