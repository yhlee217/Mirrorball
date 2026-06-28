@echo off
REM Discoverability(exposure) runner: AI + Naver discovery/rank + Place reviews/photos.
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

echo === measure exposure (AI + Naver + Place + Map rank) : %SLUG% ===
"%PY%" expose.py clients\%SLUG% --measure --place --rank --show
echo === build app data ===
"%PY%" build_app.py clients\%SLUG%
echo === done: clients\%SLUG%\exposure.yaml ===
