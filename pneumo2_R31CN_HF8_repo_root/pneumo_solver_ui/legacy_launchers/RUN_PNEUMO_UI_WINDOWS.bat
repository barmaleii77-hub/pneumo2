@echo off
setlocal
cd /d %~dp0

set PYEXE=
if exist ".venv\Scripts\python.exe" set PYEXE=.venv\Scripts\python.exe

if "%PYEXE%"=="" (
  REM fallback
  set PYEXE=python
)

echo Using Python: %PYEXE%
echo.
%PYEXE% -m streamlit run pneumo_ui_app.py --browser.gatherUsageStats false --server.runOnSave false
pause
