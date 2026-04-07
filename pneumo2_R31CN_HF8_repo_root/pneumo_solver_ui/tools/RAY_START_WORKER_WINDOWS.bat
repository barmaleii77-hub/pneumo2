@echo off
setlocal
if "%~1"=="" (
  echo Usage: RAY_START_WORKER_WINDOWS.bat HEAD_IP:6379
  pause
  exit /b 1
)
echo Starting Ray worker connecting to %~1 ...
ray start --address=%~1
echo Ray worker started.
pause
