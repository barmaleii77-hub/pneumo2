# -*- coding: utf-8 -*-
"""desktop_control_center.py

Unified desktop launcher for the existing non-web GUI tools.

Goal
----
Provide a single operator-facing entrypoint for the desktop tools that already
exist in the project, so common workflows can be opened without going through
the Streamlit UI.

Intentionally included:
- Test Center GUI
- Full Diagnostics GUI
- Send Results GUI
- Compare Viewer (Qt)
- Desktop Animator (PySide6)

Intentionally excluded:
- Desktop Mnemo
  It is handled separately and should not be coupled into this launcher.
"""

from __future__ import annotations

import os
import subprocess
import sys
import traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from pneumo_solver_ui.desktop_ui_core import build_scrolled_text, build_status_strip
from pneumo_solver_ui.desktop_shell.external_launch import repo_root as shell_repo_root
from pneumo_solver_ui.desktop_shell.external_launch import spawn_module
from pneumo_solver_ui.desktop_shell.launcher_catalog import (
    DesktopLaunchCatalogItem,
    build_desktop_launch_catalog,
)

try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


def _repo_root() -> Path:
    return shell_repo_root()


def _spawn_module(module: str) -> subprocess.Popen:
    return spawn_module(module)


class DesktopControlCenter:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"Центр запуска инженерных окон — {RELEASE}")
        self.root.geometry("860x540")
        self.root.minsize(820, 500)
        self.launch_targets = build_desktop_launch_catalog(include_mnemo=False)

        self.status_var = tk.StringVar(value="Готово. Выберите нужное инженерное окно.")
        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Центр запуска инженерных окон",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text=(
                "Единая точка входа для инженерных окон проекта. "
                "Этот центр запуска работает без web-интерфейса и не включает отдельную мнемосхему."
            ),
            wraplength=780,
            justify="left",
        ).pack(anchor="w", pady=(6, 14))

        cards = ttk.Frame(outer)
        cards.pack(fill="x", expand=False)
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        for idx, target in enumerate(self.launch_targets):
            row = idx // 2
            col = idx % 2
            box = ttk.LabelFrame(cards, text=target.title, padding=12)
            box.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            ttk.Label(
                box,
                text=target.description,
                wraplength=320,
                justify="left",
            ).pack(anchor="w", fill="x")

            ttk.Button(
                box,
                text=f"Открыть: {target.title}",
                command=lambda t=target: self._launch(t),
            ).pack(anchor="w", pady=(10, 0))

        footer = build_status_strip(outer, primary_var=self.status_var, reserve_columns=1)
        footer.pack(fill="x", pady=(14, 8))
        ttk.Button(
            footer,
            text="Открыть папку проекта",
            command=self._open_repo_root,
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        log_frame = ttk.LabelFrame(outer, text="Журнал запуска", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(8, 0))

        log_body, self.log = build_scrolled_text(log_frame, height=12, wrap="word")
        log_body.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        self._append_log("Центр запуска готов. Для этих окон web-интерфейс не требуется.")

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _open_repo_root(self) -> None:
        root = _repo_root()
        try:
            if os.name == "nt":
                os.startfile(str(root))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(root)])
            else:
                subprocess.Popen(["xdg-open", str(root)])
            self.status_var.set(f"Открыта папка проекта: {root}")
            self._append_log(f"[open] repo: {root}")
        except Exception as exc:
            messagebox.showerror("Центр запуска инженерных окон", f"Не удалось открыть папку проекта:\n{exc}")
            self._append_log("[error] open repo\n" + traceback.format_exc())

    def _launch(self, target: DesktopLaunchCatalogItem) -> None:
        try:
            proc = _spawn_module(target.module)
            self.status_var.set(f"Запущено: {target.title}")
            self._append_log(
                f"[spawn] {target.title}\n"
                f"  module: {target.module}\n"
                f"  pid: {getattr(proc, 'pid', 'n/a')}"
            )
        except Exception as exc:
            messagebox.showerror(
                "Центр запуска инженерных окон",
                f"Не удалось запустить «{target.title}»:\n{exc}",
            )
            self.status_var.set(f"Ошибка запуска: {target.title}")
            self._append_log("[error] spawn\n" + traceback.format_exc())

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    app = DesktopControlCenter()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
