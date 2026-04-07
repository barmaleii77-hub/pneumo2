@echo off
setlocal
if "%~1"=="" (
  echo Usage: DASK_START_WORKER_WINDOWS.bat tcp://HEAD_IP:8786
  exit /b 1
)
echo Starting Dask worker connecting to %~1 ...
dask worker %~1 --nthreads 1 --nworkers 4
