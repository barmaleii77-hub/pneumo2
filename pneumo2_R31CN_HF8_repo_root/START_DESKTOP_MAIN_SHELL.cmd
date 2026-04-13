@echo off
REM Best-effort hidden launcher wrapper for the classic desktop shell.
cd /d "%~dp0"
if exist "%~dp0START_DESKTOP_MAIN_SHELL.vbs" (
  start "" wscript.exe //nologo "%~dp0START_DESKTOP_MAIN_SHELL.vbs"
  exit /b
)
if exist "%~dp0START_DESKTOP_MAIN_SHELL.pyw" (
  start "" "%~dp0START_DESKTOP_MAIN_SHELL.pyw"
  exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%~dp0START_DESKTOP_MAIN_SHELL.py"
) else (
  where pyw >nul 2>nul
  if %errorlevel%==0 (
    start "" pyw "%~dp0START_DESKTOP_MAIN_SHELL.py"
  ) else (
    start "" python "%~dp0START_DESKTOP_MAIN_SHELL.py"
  )
)
exit /b
