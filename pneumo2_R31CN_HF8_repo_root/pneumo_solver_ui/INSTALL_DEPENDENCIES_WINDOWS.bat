@echo off
setlocal enabledelayedexpansion

REM Force UTF-8 console (avoid "krakozyabry" on RU/CP866 consoles)
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d %~dp0

REM ================================
REM  Pneumo Solver UI - Installer
REM  Creates local venv .venv and installs deps
REM ================================

set VENV_DIR=.venv
set PYEXE=

echo.
echo [1/4] Create / reuse virtual environment: %VENV_DIR%

if exist "%VENV_DIR%\Scripts\python.exe" (
    set PYEXE=%VENV_DIR%\Scripts\python.exe
) else (
    REM Try py launcher first
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3 -m venv "%VENV_DIR%" || goto :venv_fail
    ) else (
        python -m venv "%VENV_DIR%" || goto :venv_fail
    )
    set PYEXE=%VENV_DIR%\Scripts\python.exe
)

echo Using python: %PYEXE%

echo.
echo [2/4] Upgrade pip
"%PYEXE%" -m pip install --upgrade pip

echo.
echo [3/4] Install main requirements
"%PYEXE%" -m pip install -r requirements.txt
if %errorlevel% neq 0 goto :pip_fail

echo.
echo [3b/4] Desktop Animator extras (recommended on Windows)
if exist requirements_desktop_animator.txt (
    "%PYEXE%" -m pip install -r requirements_desktop_animator.txt
    if %errorlevel% neq 0 (
        echo WARNING: could not install requirements_desktop_animator.txt
        echo Desktop Animator may work slower without OpenGL_accelerate.
    )
)

echo.
echo [4/4] Optional: calibration requirements
if exist requirements_calibration.txt (
    "%PYEXE%" -m pip install -r requirements_calibration.txt
)

echo.
echo OK. Dependencies installed into .venv
echo Next: double-click START_PNEUMO_UI.pyw
pause
exit /b 0

:venv_fail
echo.
echo FAILED: could not create venv.
echo Check that Python is installed and available in PATH.
pause
exit /b 1

:pip_fail
echo.
echo FAILED: pip install -r requirements.txt
echo Try running this in a console for full output:
echo    %PYEXE% -m pip install -r requirements.txt
pause
exit /b 1
