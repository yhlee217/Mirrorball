@echo off
REM Discoverability(노출) 측정 실행기 (Windows). AI + 네이버 발견/순위 + 플레이스 리뷰·사진.
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0\..\.."

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

set "SLUG=%~1"
if "%SLUG%"=="" set "SLUG=hayewoni"

echo === %SLUG% 노출 측정 (AI + 네이버 + 플레이스) ===
"%PY%" expose.py clients\%SLUG% --measure --place --show
echo === 앱 데이터 빌드 ===
"%PY%" build_app.py clients\%SLUG%
echo === 완료: clients\%SLUG%\exposure.yaml ===
