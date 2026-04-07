@echo off
REM Best-effort hidden launcher wrapper.
REM Primary path: VBS -> .pyw association (no extra python console).
cd /d "%~dp0"
if exist "%~dp0START_PNEUMO_APP.vbs" (
  start "" wscript.exe //nologo "%~dp0START_PNEUMO_APP.vbs"
  exit /b
)
if exist "%~dp0START_PNEUMO_APP.pyw" (
  start "" "%~dp0START_PNEUMO_APP.pyw"
  exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%~dp0START_PNEUMO_APP.py"
) else (
  where pyw >nul 2>nul
  if %errorlevel%==0 (
    start "" pyw "%~dp0START_PNEUMO_APP.py"
  ) else (
    start "" python "%~dp0START_PNEUMO_APP.py"
  )
)
exit /b
