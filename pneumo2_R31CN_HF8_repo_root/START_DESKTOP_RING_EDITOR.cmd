@echo off
REM Best-effort hidden launcher wrapper for the desktop ring scenario editor.
cd /d "%~dp0"
if exist "%~dp0START_DESKTOP_RING_EDITOR.vbs" (
  start "" wscript.exe //nologo "%~dp0START_DESKTOP_RING_EDITOR.vbs"
  exit /b
)
if exist "%~dp0START_DESKTOP_RING_EDITOR.pyw" (
  start "" "%~dp0START_DESKTOP_RING_EDITOR.pyw"
  exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%~dp0START_DESKTOP_RING_EDITOR.py"
) else (
  where pyw >nul 2>nul
  if %errorlevel%==0 (
    start "" pyw "%~dp0START_DESKTOP_RING_EDITOR.py"
  ) else (
    start "" python "%~dp0START_DESKTOP_RING_EDITOR.py"
  )
)
exit /b
