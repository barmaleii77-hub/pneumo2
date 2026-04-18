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

from pneumo_solver_ui.desktop_ui_core import build_scrolled_text, build_scrolled_treeview, build_status_strip
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
        self.target_by_iid: dict[str, DesktopLaunchCatalogItem] = {}

        self.status_var = tk.StringVar(value="Готово. Выберите нужное инженерное окно.")
        self.details_var = tk.StringVar(
            value="Слева список инженерных окон, справа описание выбранного окна и журнал запуска."
        )
        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 10))
        title_box = ttk.Frame(header)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(
            title_box,
            text="Центр запуска инженерных окон",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            textvariable=self.details_var,
            wraplength=620,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        header_actions = ttk.Frame(header)
        header_actions.pack(side="right", anchor="ne")
        ttk.Button(header_actions, text="Открыть проект", command=self._open_repo_root).pack(side="left")

        workspace = ttk.Panedwindow(outer, orient="horizontal")
        workspace.pack(fill="both", expand=True)

        left = ttk.Frame(workspace, padding=(0, 0, 8, 0))
        right = ttk.Frame(workspace)

        list_box = ttk.LabelFrame(left, text="Инженерные окна", padding=8)
        list_box.pack(fill="both", expand=True)
        tree_frame, self.tree = build_scrolled_treeview(
            list_box,
            columns=("kind",),
            show="tree headings",
            height=14,
        )
        self.tree.heading("#0", text="Окно")
        self.tree.heading("kind", text="Тип")
        self.tree.column("#0", width=250, anchor="w")
        self.tree.column("kind", width=90, anchor="w")
        tree_frame.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_target)
        self.tree.bind("<Double-1>", self._on_open_selected_target)

        left_actions = ttk.Frame(list_box)
        left_actions.pack(fill="x", pady=(8, 0))
        ttk.Button(left_actions, text="Запустить GUI", command=self._launch_selected_target).pack(side="left")
        ttk.Button(left_actions, text="Папка проекта", command=self._open_repo_root).pack(side="left", padx=(8, 0))

        right_split = ttk.Panedwindow(right, orient="vertical")
        right_split.pack(fill="both", expand=True)

        detail_box = ttk.LabelFrame(right_split, text="Описание", padding=10)
        ttk.Label(
            detail_box,
            textvariable=self.details_var,
            wraplength=520,
            justify="left",
        ).pack(anchor="w")
        detail_actions = ttk.Frame(detail_box)
        detail_actions.pack(fill="x", pady=(10, 0))
        ttk.Button(detail_actions, text="Запустить этот GUI", command=self._launch_selected_target).pack(side="left")

        log_frame = ttk.LabelFrame(right_split, text="Журнал запуска", padding=8)
        log_body, self.log = build_scrolled_text(log_frame, height=12, wrap="word")
        log_body.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        right_split.add(detail_box, weight=1)
        right_split.add(log_frame, weight=3)
        workspace.add(left, weight=2)
        workspace.add(right, weight=3)

        footer = build_status_strip(outer, primary_var=self.status_var, reserve_columns=1)
        footer.pack(fill="x", pady=(14, 8))
        ttk.Button(
            footer,
            text="Открыть папку проекта",
            command=self._open_repo_root,
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        self._populate_targets()
        self._append_log("Центр запуска готов. Для этих окон web-интерфейс не требуется.")

    def _populate_targets(self) -> None:
        self.target_by_iid.clear()
        self.tree.delete(*self.tree.get_children())
        for idx, target in enumerate(self.launch_targets):
            iid = f"target_{idx}"
            self.target_by_iid[iid] = target
            self.tree.insert("", "end", iid=iid, text=target.title, values=("Окно",))
        if self.target_by_iid:
            first_iid = next(iter(self.target_by_iid))
            self.tree.selection_set(first_iid)
            self.tree.focus(first_iid)
            self._render_selected_target(first_iid)

    def _render_selected_target(self, iid: str) -> None:
        target = self.target_by_iid.get(iid)
        if target is None:
            self.details_var.set(
                "Слева список инженерных окон, справа описание выбранного окна и журнал запуска."
            )
            return
        self.details_var.set(
            f"{target.title}\n\n{target.description}\n\nМодуль запуска: {target.module}"
        )

    def _selected_target(self) -> DesktopLaunchCatalogItem | None:
        iid = next(iter(self.tree.selection() or ()), "")
        return self.target_by_iid.get(iid)

    def _on_select_target(self, _event=None) -> None:
        iid = next(iter(self.tree.selection() or ()), "")
        if iid:
            self._render_selected_target(iid)

    def _on_open_selected_target(self, _event=None) -> None:
        self._launch_selected_target()

    def _launch_selected_target(self) -> None:
        target = self._selected_target()
        if target is None:
            return
        self._launch(target)

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
