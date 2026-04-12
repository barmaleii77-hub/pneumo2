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
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


@dataclass(frozen=True)
class LaunchTarget:
    title: str
    module: str
    description: str


LAUNCH_TARGETS: tuple[LaunchTarget, ...] = (
    LaunchTarget(
        title="Исходные данные и расчёт",
        module="pneumo_solver_ui.tools.desktop_input_editor",
        description="Редактор исходных параметров модели: геометрия, пневматика, механика и настройки расчёта.",
    ),
    LaunchTarget(
        title="Центр проверок",
        module="pneumo_solver_ui.tools.test_center_gui",
        description="Автотесты, полная диагностика и быстрый переход к отправке результатов.",
    ),
    LaunchTarget(
        title="Полная диагностика",
        module="pneumo_solver_ui.tools.run_full_diagnostics_gui",
        description="Собрать полный диагностический архив и проверить состояние окружения.",
    ),
    LaunchTarget(
        title="Отправка результатов",
        module="pneumo_solver_ui.tools.send_results_gui",
        description="Собрать SEND bundle и открыть окно копирования архива без WEB UI.",
    ),
    LaunchTarget(
        title="Сравнение NPZ (Qt)",
        module="pneumo_solver_ui.qt_compare_viewer",
        description="Desktop viewer для сравнения прогонов, графиков и NPZ-трасс.",
    ),
    LaunchTarget(
        title="Desktop Animator",
        module="pneumo_solver_ui.desktop_animator.app",
        description="Открыть PySide6-аниматор для последней выгрузки или локального сценария.",
    ),
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _python_gui_exe() -> str:
    if os.name != "nt":
        return sys.executable

    try:
        exe = Path(sys.executable)
        if exe.name.lower() == "python.exe":
            pyw = exe.with_name("pythonw.exe")
            if pyw.exists():
                return str(pyw)
    except Exception:
        pass
    return sys.executable


def _spawn_module(module: str) -> subprocess.Popen:
    cmd = [_python_gui_exe(), "-m", module]
    kwargs: dict[str, object] = {
        "cwd": str(_repo_root()),
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(cmd, **kwargs)


class DesktopControlCenter:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"Pneumo Desktop Control Center — {RELEASE}")
        self.root.geometry("860x540")
        self.root.minsize(820, 500)

        self.status_var = tk.StringVar(value="Готово. Выберите desktop-инструмент.")
        self._build_ui()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text="Pneumo Desktop Control Center",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w")

        ttk.Label(
            outer,
            text=(
                "Единая точка входа для desktop-инструментов проекта. "
                "Этот launcher не использует WEB UI и не включает Desktop Mnemo."
            ),
            wraplength=780,
            justify="left",
        ).pack(anchor="w", pady=(6, 14))

        cards = ttk.Frame(outer)
        cards.pack(fill="x", expand=False)
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        for idx, target in enumerate(LAUNCH_TARGETS):
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

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(14, 8))

        ttk.Label(footer, textvariable=self.status_var).pack(side="left", anchor="w")

        ttk.Button(
            footer,
            text="Открыть папку проекта",
            command=self._open_repo_root,
        ).pack(side="right")

        log_frame = ttk.LabelFrame(outer, text="Журнал launcher", padding=8)
        log_frame.pack(fill="both", expand=True, pady=(8, 0))

        self.log = tk.Text(log_frame, height=12, wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        self._append_log("Launcher готов. WEB UI для этих инструментов не требуется.")

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
            messagebox.showerror("Desktop Control Center", f"Не удалось открыть папку проекта:\n{exc}")
            self._append_log("[error] open repo\n" + traceback.format_exc())

    def _launch(self, target: LaunchTarget) -> None:
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
                "Desktop Control Center",
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
