# Playwright + Python(브라우저 포함) 베이스
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app
COPY worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY worker/ ./worker/
# v1 스크레이프 재사용(scrape.py 가 import) — 브라우저 자동화·셀렉터·예약 파서
COPY scripts/handsos_sync.py scripts/handsos_harvest.js scripts/handsos_selectors.yaml ./scripts/
COPY handsos_reserve.py ./
# Playwright 브라우저는 베이스 이미지에 포함(mcr playwright/python)

CMD ["python", "worker/run.py"]
