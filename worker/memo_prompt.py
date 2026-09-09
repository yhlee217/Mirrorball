"""매장 메모 요약의 프롬프트와 응답 파싱.

무엇을 물어보고 무엇을 받아내는지만 모아 둔다. 문구를 다듬을 때 여기만 보면 되고,
호출 방식(claude_cli)이나 대상 선별(summarize_memos)과 섞이지 않는다.

프롬프트를 고치면 기존 요약은 형식이 달라 못 쓴다 → PROMPT_VERSION 을 올려
해시가 바뀌게 하면 다음 실행에서 자동으로 다시 만들어진다.
"""

from __future__ import annotations

from claude_cli import run_claude

# 프롬프트가 바뀌면 기존 요약은 형식이 달라 쓸 수 없다. 해시에 섞어 자동 재생성시킨다.
PROMPT_VERSION = "2-sections"

def build_batch_prompt(blocks: list[list[str]]) -> str:
    """여러 고객의 메모를 한 프롬프트로. blocks[i] = 그 고객의 '날짜 메모' 줄들."""
    body = "\n\n".join(
        f"--- 고객 {i + 1} ---\n" + "\n".join(lines) for i, lines in enumerate(blocks)
    )
    return (
        f"너는 미용실 디자이너를 돕는 조수다. 아래에 고객 {len(blocks)}명의 매장 메모가 있다"
        "(고객마다 날짜 오름차순). 각 고객을 두 덩이로 정리해라.\n\n"
        "[선호] — 시술에 계속 반영할 것\n"
        "- 반복되는 선호·주의사항, 모발·두피 상태.\n"
        "- 시간에 따라 뒤집히면 날짜를 보고 최근 것을 따르되 '최근에는 ~' 으로 적어라.\n"
        "- 2~4개. 각 줄 25자 내외.\n\n"
        "[근황] — 다음에 만나면 먼저 물어볼 이야기\n"
        "- 개인 근황·대화거리(가족, 일, 이사, 여행, 행사, 건강 등). 시술과 무관해도 좋다.\n"
        "- 한 번만 나온 이야기라도 담아라. 이게 이 항목의 목적이다.\n"
        "- 최근 것 위주로 최대 3개. 각 줄 앞에 (YYYY-MM) 을 붙여라.\n"
        "- 오래돼 지금 꺼내기 어색한 이야기는 빼라. 해당 없으면 아무 줄도 쓰지 마라.\n\n"
        "공통: 메모에 실제로 있는 내용만. 없는 사실을 지어내지 마라.\n"
        "고객 번호를 절대 섞지 마라 — 각자 자기 메모만 보고 정리한다.\n"
        "인사말·설명 없이 아래 형식 그대로, 고객 수만큼 반복해서 출력:\n"
        "### 1\n[선호]\n- ...\n[근황]\n- (2026-07) ...\n### 2\n[선호]\n- ...\n\n"
        f"{body}\n"
    )


def parse_batch(text: str, n: int) -> dict[int, tuple[str | None, str | None]]:
    """'### i' 로 나뉜 응답을 고객 번호별로 파싱. 일부가 깨져도 나머지는 살린다."""
    out: dict[int, tuple[str | None, str | None]] = {}
    cur: int | None = None
    buf: list[str] = []

    def flush() -> None:
        if cur is not None and 1 <= cur <= n:
            out[cur] = parse_sections("\n".join(buf))

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("###"):
            flush()
            digits = "".join(ch for ch in line if ch.isdigit())
            cur, buf = (int(digits) if digits else None), []
            continue
        buf.append(raw)
    flush()
    return out


def summarize_batch(jobs: list[dict]) -> list[tuple[str, str | None, str | None, str]]:
    """한 번의 호출로 여러 고객 처리. 반환은 고객별 (cid, 선호, 근황, 실패사유)."""
    out, why = run_claude(build_batch_prompt([j["memos"] for j in jobs]))
    if not out:
        return [(j["cid"], None, None, why) for j in jobs]
    parsed = parse_batch(out, len(jobs))
    res = []
    for i, j in enumerate(jobs, start=1):
        pref, recent = parsed.get(i, (None, None))
        res.append((j["cid"], pref, recent, "" if pref else "응답에서 이 고객 항목을 못 찾음"))
    return res


def parse_sections(text: str) -> tuple[str | None, str | None]:
    """모델 출력에서 [선호]/[근황] 두 덩이를 뽑는다. 서두·코드펜스는 버린다."""
    pref: list[str] = []
    recent: list[str] = []
    cur: list[str] | None = None
    for raw in text.splitlines():
        line = raw.strip().strip("`").strip()
        if not line:
            continue
        if line.startswith("[선호]"):
            cur = pref
            continue
        if line.startswith("[근황]"):
            cur = recent
            continue
        if line.startswith(("- ", "• ", "* ")) and cur is not None:
            cur.append("- " + line[2:].strip())
    return ("\n".join(pref[:4]) or None, "\n".join(recent[:3]) or None)


