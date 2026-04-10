@echo off
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" -m pneumo_solver_ui.tools.write_codex_handoff %*
if errorlevel 1 exit /b %errorlevel%

echo.
echo Handoff snapshot updated:
echo   docs\context\CODEX_HANDOFF_LATEST.md
echo   docs\context\CODEX_HANDOFF_LATEST.json
echo.
echo Review the snapshot, then sync it with:
echo   git add docs/context/CODEX_HANDOFF_LATEST.md docs/context/CODEX_HANDOFF_LATEST.json docs/context/CODEX_GITHUB_SYNC.md SAVE_CODEX_CONTEXT_TO_GITHUB.cmd
echo   git commit -m "Update Codex handoff"
echo   git push

endlocal
