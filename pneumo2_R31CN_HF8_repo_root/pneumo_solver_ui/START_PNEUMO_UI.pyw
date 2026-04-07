# -*- coding: utf-8 -*-
"""START_PNEUMO_UI.pyw

Двойной клик -> запускает Streamlit UI без необходимости писать команды в консоли.

ВАЖНО (Windows):
В прошлых запусках встречалась типовая проблема: зависимости ставились в один Python,
а UI запускался из другого Python, из-за чего появлялось сообщение вида
"Plotly не установлен" и/или падали компоненты.

Решение:
- если рядом есть локальная виртуальная среда .venv (создаётся INSTALL_DEPENDENCIES_WINDOWS.bat),
  то запускаем Streamlit именно из неё (так гарантируется наличие plotly/streamlit и т.п.).
- если .venv отсутствует, используем текущий Python (sys.executable).

Запуск из консоли:
    python -m streamlit run pneumo_ui_app.py
"""
import os
import sys
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE / "pneumo_ui_app.py"


def pick_python() -> str:
    """Prefer local venv if exists."""
    if os.name == "nt":
        cand = HERE / ".venv" / "Scripts" / "python.exe"
    else:
        cand = HERE / ".venv" / "bin" / "python"
    if cand.exists():
        return str(cand)
    return sys.executable


def main():
    if not APP.exists():
        raise FileNotFoundError(f"Не найден {APP}")

    py = pick_python()
    cmd = [
        py,
        "-m",
        "streamlit",
        "run",
        str(APP),
        "--browser.gatherUsageStats",
        "false",
        "--server.runOnSave",
        "false",
    ]

    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        # Hide console window
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]

    subprocess.Popen(cmd, cwd=str(HERE), creationflags=creationflags, startupinfo=startupinfo)


if __name__ == "__main__":
    main()
