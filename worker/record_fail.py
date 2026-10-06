"""수집이 '시작조차 못 했다'는 사실을 DB 에 남긴다.

record_sync 는 sync_tenant.py 안에서만 불린다. 그래서 run_mac.sh 가 사전 점검
(크로미움 없음·시크릿 없음)에서 빠져나가면 sync_jobs 에 성공도 실패도 안 남는다.
앱은 '마지막 성공'만 읽으니 '며칠 전' 숫자만 커지고, 왜 그런지는 아무 데도 없다.

실제로 이것 때문에 5주를 날렸다(2026-09-02 ~ 10-06): 크로미움이 사라져 매주
프리플라이트에서 exit 1 했는데, 그 사실이 로그 파일에만 있었다.

쓰기 실패가 원래의 실패를 덮어쓰지 않도록 예외는 모두 삼키고 0 으로 끝낸다.

사용:
    .venv/bin/python worker/record_fail.py "크로미움 없음"
"""

from __future__ import annotations

import sys

from env import load_env

load_env()


import supa  # noqa: E402


def _salon_tenants() -> list:
    """미용실 테넌트만. industry 컬럼은 0016 미적용 DB 에는 없다(gap_check 와 같은 폴백)."""
    try:
        rows = supa._get("/tenants", {"select": "id,slug,industry", "order": "slug"})
        return [t for t in rows if (t.get("industry") or "salon") == "salon"]
    except RuntimeError as exc:
        if "industry" not in str(exc):
            raise
        return supa._get("/tenants", {"select": "id,slug", "order": "slug"})


def main() -> int:
    msg = " ".join(sys.argv[1:]).strip() or "수집 실패(사유 미기록)"
    try:
        tenants = _salon_tenants()
    except Exception as exc:  # noqa: BLE001
        print(f"  (실패 기록 못 함 — 수집 실패 자체는 유효: {exc})")
        return 0
    for t in tenants:
        try:
            supa.record_sync(t["id"], None, error=msg)
        except Exception as exc:  # noqa: BLE001
            print(f"  ({t.get('slug')} 실패 기록 못 함: {exc})")
    print(f"  수집 실패를 sync_jobs 에 기록: {msg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
