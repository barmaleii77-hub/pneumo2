# -*- coding: utf-8 -*-
"""Reserve PySide6 main window aligned with the desktop GUI canon."""

from __future__ import annotations

import os
import sys


def _show_missing_pyside6_message(exc: Exception) -> int:
    message = (
        "PySide6 не установлен. Панель восстановления окон требует PySide6.\n\n"
        "Установите зависимость и повторите запуск.\n"
        f"Подробность: {exc}"
    )
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("PneumoApp", message)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--open" in args:
        index = args.index("--open")
        if index + 1 < len(args):
            os.environ["PNEUMO_GUI_SPEC_SHELL_OPEN_WORKSPACE"] = args[index + 1]
    try:
        from pneumo_solver_ui.desktop_spec_shell.main_window import main as run_shell
    except Exception as exc:
        return _show_missing_pyside6_message(exc)
    return run_shell()


if __name__ == "__main__":
    raise SystemExit(main())
