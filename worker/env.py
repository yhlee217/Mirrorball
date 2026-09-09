"""워커 스크립트의 공통 시작점 — 시크릿 로딩.

같은 13줄이 워커 스크립트 10개에 복붙돼 있었다. 셋업이 바뀔 때(키 이름 추가 등)
열 군데를 고쳐야 하고, 한 곳을 빠뜨리면 그 스크립트만 조용히 다르게 동작한다.

값은 웹과 같은 파일(web/.env.local)에서 읽는다 — 워커와 앱이 같은 Supabase·같은 KEK 를
써야 암호문이 서로 열리기 때문에, 두 벌로 관리하면 어긋나는 순간 이름이 안 열린다.

사용:
    from env import load_env
    load_env()          # import 직후 한 번. supa 를 import 하기 전에 불러야 한다.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / "web" / ".env.local"


def load_env(path: Path | None = None) -> None:
    """web/.env.local 을 os.environ 에 주입한다.

    - 이미 환경에 있는 값은 덮지 않는다(setdefault) — 셸에서 준 값이 우선이라
      `SYNC_DAYS=60 ...` 처럼 일회성으로 바꿔 돌릴 수 있다.
    - 워커 코드는 SUPABASE_URL 을 쓰는데 웹은 NEXT_PUBLIC_SUPABASE_URL 로 두므로
      없을 때만 그쪽에서 채운다.
    """
    p = path or ENV_FILE
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    if not os.environ.get("SUPABASE_URL") and os.environ.get("NEXT_PUBLIC_SUPABASE_URL"):
        os.environ["SUPABASE_URL"] = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
