# -*- coding: utf-8 -*-
"""Shared desktop diagnostics entrypoint.

This wrapper keeps the historical module/class API for hosted shell launchers,
but the actual UI now lives in the unified desktop diagnostics/send center.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import Tk

from pneumo_solver_ui.tools.desktop_diagnostics_center import DesktopDiagnosticsCenter

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent


def _guess_python_exe() -> Path:
    if sys.platform.startswith("win"):
        venv = ROOT / ".venv" / "Scripts"
        pyw = venv / "pythonw.exe"
        py = venv / "python.exe"
        if pyw.exists():
            return pyw
        if py.exists():
            return py
    return Path(sys.executable)


def _open_in_explorer(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])  # noqa: S603,S607
        else:
            subprocess.Popen(["xdg-open", str(path)])  # noqa: S603,S607
    except Exception:
        pass


class App(DesktopDiagnosticsCenter):
    def __init__(self, root: tk.Misc, hosted: bool = False) -> None:
        super().__init__(
            root,
            hosted=hosted,
            initial_tab="diagnostics",
            auto_build_bundle=False,
        )
        if not self._hosted:
            self.root.title("Full Diagnostics (GUI) — Pneumo Solver UI")

    def on_close(self) -> None:
        super().on_close()

    def on_host_close(self) -> None:
        self._host_closed = True
        super().on_host_close()


def main() -> int:
    root = Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
