@echo off
REM HandSOS sync runner (Windows). Task Scheduler calls this. UTF-8 forced for Korean output.
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM Move to repo root (this .bat lives in scripts\win)
cd /d "%~dp0\..\.."

REM Use venv python if present, else system python
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo [%date% %time%] sync start >> sync.log
"%PY%" scripts\handsos_sync.py %* >> sync.log 2>&1
set RC=%errorlevel%
echo [%date% %time%] sync end (exit %RC%) >> sync.log
exit /b %RC%
