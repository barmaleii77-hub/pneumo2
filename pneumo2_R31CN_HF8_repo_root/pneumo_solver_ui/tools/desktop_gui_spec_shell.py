# -*- coding: utf-8 -*-
"""Canonical PySide6 desktop shell aligned with GUI-spec (17/18)."""

from __future__ import annotations

import sys


def _show_missing_pyside6_message(exc: Exception) -> int:
    message = (
        "PySide6 не установлен. Канонический desktop shell по GUI-spec требует PySide6.\n\n"
        "Установите зависимость и повторите запуск.\n"
        f"Подробность: {exc}"
    )
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("PneumoApp Desktop Shell", message)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    _ = argv
    try:
        from pneumo_solver_ui.desktop_spec_shell.main_window import main as run_shell
    except Exception as exc:
        return _show_missing_pyside6_message(exc)
    return run_shell()


if __name__ == "__main__":
    raise SystemExit(main())
