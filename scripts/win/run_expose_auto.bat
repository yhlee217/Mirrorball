@echo off
REM Weekly exposure measurement (HEADLESS, logged). Task Scheduler calls this.
REM Unlike run_expose.bat, no --show: browser stays headless for background runs.
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

set "SLUG=%~1"
if "%SLUG%"=="" set "SLUG=hayewoni"

echo [%date% %time%] expose start (%SLUG%) >> expose.log
"%PY%" expose.py clients\%SLUG% --measure --place --rank >> expose.log 2>&1
set RC=%errorlevel%
"%PY%" build_app.py clients\%SLUG% >> expose.log 2>&1
echo [%date% %time%] expose end (exit %RC%) >> expose.log
exit /b %RC%
