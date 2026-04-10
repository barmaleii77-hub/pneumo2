@echo off
setlocal
cd /d "%~dp0"

set "PROJECT_ROOT=%CD%"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" -m pneumo_solver_ui.tools.write_codex_handoff --repo-root "%PROJECT_ROOT%" %*
if errorlevel 1 exit /b %errorlevel%

echo.
echo Handoff snapshot updated:
echo   docs\context\CODEX_HANDOFF_LATEST.md
echo   docs\context\CODEX_HANDOFF_LATEST.json
echo.
echo Validate the workflow contract with:
echo   pytest tests\test_codex_github_handoff_contract.py
echo.
echo Review the snapshot, then sync it from the git root with:
echo   git add pneumo2_R31CN_HF8_repo_root
echo   git commit -m "Update Codex handoff"
echo   git push

endlocal
