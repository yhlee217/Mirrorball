# Playwright + Python(브라우저 포함) 베이스
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app
COPY worker/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY worker/ ./worker/
# 스크레이프 통합 시 v1 모듈도 함께 복사(README §스크레이프 통합):
#   COPY scrape_handsos.py import_handsos.py handsos_reserve.py ./
#   COPY scripts/handsos_selectors.yaml ./scripts/

CMD ["python", "worker/run.py"]
