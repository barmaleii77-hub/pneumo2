@echo off
REM Best-effort hidden launcher wrapper for the desktop control center.
cd /d "%~dp0"
if exist "%~dp0START_DESKTOP_CONTROL_CENTER.vbs" (
  start "" wscript.exe //nologo "%~dp0START_DESKTOP_CONTROL_CENTER.vbs"
  exit /b
)
if exist "%~dp0START_DESKTOP_CONTROL_CENTER.pyw" (
  start "" "%~dp0START_DESKTOP_CONTROL_CENTER.pyw"
  exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%~dp0START_DESKTOP_CONTROL_CENTER.py"
) else (
  where pyw >nul 2>nul
  if %errorlevel%==0 (
    start "" pyw "%~dp0START_DESKTOP_CONTROL_CENTER.py"
  ) else (
    start "" python "%~dp0START_DESKTOP_CONTROL_CENTER.py"
  )
)
exit /b
