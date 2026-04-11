@echo off
chcp 65001 > nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d %~dp0\..\..\..
echo Reproducing autotest...
if exist .venv\Scripts\activate (call .venv\Scripts\activate)
python pneumo_solver_ui\tools\run_autotest.py --level quick
pause
