@echo off
REM 핸드SOS 동기화 실행기 (Windows). Task Scheduler 가 이걸 호출.
REM 한글 깨짐 방지 위해 UTF-8 강제.
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM 이 배치 위치(scripts\win) 기준으로 저장소 루트로 이동
cd /d "%~dp0\..\.."

REM 가상환경 있으면 그걸, 없으면 시스템 python
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
