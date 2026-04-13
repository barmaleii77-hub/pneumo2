@echo off
REM Best-effort hidden launcher wrapper for the desktop optimizer center.
cd /d "%~dp0"
if exist "%~dp0START_DESKTOP_OPTIMIZER_CENTER.vbs" (
  start "" wscript.exe //nologo "%~dp0START_DESKTOP_OPTIMIZER_CENTER.vbs"
  exit /b
)
if exist "%~dp0START_DESKTOP_OPTIMIZER_CENTER.pyw" (
  start "" "%~dp0START_DESKTOP_OPTIMIZER_CENTER.pyw"
  exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%~dp0START_DESKTOP_OPTIMIZER_CENTER.py"
) else (
  where pyw >nul 2>nul
  if %errorlevel%==0 (
    start "" pyw "%~dp0START_DESKTOP_OPTIMIZER_CENTER.py"
  ) else (
    start "" python "%~dp0START_DESKTOP_OPTIMIZER_CENTER.py"
  )
)
exit /b
