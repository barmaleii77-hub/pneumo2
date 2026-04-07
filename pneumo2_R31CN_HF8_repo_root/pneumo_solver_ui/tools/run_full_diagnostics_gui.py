# -*- coding: utf-8 -*-
"""
run_full_diagnostics_gui.py

Небольшая GUI-оболочка (tkinter) над tools/run_full_diagnostics.py.

Цель: запускать диагностику "в один клик" и выбирать варианты тестирования
БЕЗ необходимости печатать команды в консоль.

Запуск:
  - Windows: двойной клик по RUN_FULL_DIAGNOSTICS_GUI_WINDOWS.bat
  - Или: python pneumo_solver_ui/tools/run_full_diagnostics_gui.py
"""

from __future__ import annotations

import os
import sys
import threading
import subprocess
from pathlib import Path
from tkinter import Tk, StringVar, BooleanVar, IntVar
from tkinter import ttk, filedialog, messagebox

ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = Path(__file__).resolve().parent


def _guess_python_exe() -> Path:
    """Prefer local .venv python if present, else sys.executable."""
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
        # If explorer open fails, just ignore
        pass


class App:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Full Diagnostics (GUI) — Pneumo Solver UI")
        self.root.geometry("820x620")

        self.level = StringVar(value="standard")
        self.skip_ui_smoke = BooleanVar(value=False)
        self.no_zip = BooleanVar(value=False)
        self.run_opt_smoke = BooleanVar(value=False)
        self.opt_minutes = IntVar(value=2)
        self.opt_jobs = IntVar(value=2)

        self.osc_dir = StringVar(value=str((ROOT / "workspace" / "osc").resolve()))
        self.out_root = StringVar(value=str((ROOT / "diagnostics").resolve()))

        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._last_zip: Path | None = None
        self._last_run_dir: Path | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        frm = ttk.Frame(self.root)
        frm.pack(fill="both", expand=True)

        # Top: level
        level_box = ttk.LabelFrame(frm, text="Уровень диагностики")
        level_box.pack(fill="x", **pad)

        for v, txt in [
            ("minimal", "minimal — быстро, только sanity"),
            ("standard", "standard — рекомендуется"),
            ("full", "full — максимально подробно"),
        ]:
            ttk.Radiobutton(level_box, text=txt, value=v, variable=self.level).pack(anchor="w", padx=10, pady=2)

        # Options
        opt_box = ttk.LabelFrame(frm, text="Опции")
        opt_box.pack(fill="x", **pad)

        ttk.Checkbutton(opt_box, text="Пропустить UI smoke-test (без запуска Streamlit)", variable=self.skip_ui_smoke).pack(anchor="w", padx=10, pady=2)
        ttk.Checkbutton(opt_box, text="Не создавать ZIP (оставить папку как есть)", variable=self.no_zip).pack(anchor="w", padx=10, pady=2)

        opt2 = ttk.Frame(opt_box)
        opt2.pack(fill="x", padx=10, pady=4)
        ttk.Checkbutton(opt2, text="Запустить Optimization smoke-test", variable=self.run_opt_smoke).grid(row=0, column=0, sticky="w")
        ttk.Label(opt2, text="minutes:").grid(row=0, column=1, sticky="e", padx=(12, 2))
        ttk.Spinbox(opt2, from_=1, to=60, textvariable=self.opt_minutes, width=6).grid(row=0, column=2, sticky="w")
        ttk.Label(opt2, text="jobs:").grid(row=0, column=3, sticky="e", padx=(12, 2))
        ttk.Spinbox(opt2, from_=1, to=32, textvariable=self.opt_jobs, width=6).grid(row=0, column=4, sticky="w")
        opt2.columnconfigure(5, weight=1)

        # Paths
        path_box = ttk.LabelFrame(frm, text="Пути (если нужно)")
        path_box.pack(fill="x", **pad)

        row = ttk.Frame(path_box)
        row.pack(fill="x", padx=10, pady=4)
        ttk.Label(row, text="osc_dir (NPZ):").pack(side="left")
        ttk.Entry(row, textvariable=self.osc_dir).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="...", width=3, command=self._pick_osc_dir).pack(side="left")

        row2 = ttk.Frame(path_box)
        row2.pack(fill="x", padx=10, pady=4)
        ttk.Label(row2, text="out_root:").pack(side="left")
        ttk.Entry(row2, textvariable=self.out_root).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row2, text="...", width=3, command=self._pick_out_root).pack(side="left")

        # Controls
        ctrl = ttk.Frame(frm)
        ctrl.pack(fill="x", **pad)
        self.btn_run = ttk.Button(ctrl, text="▶ Запустить", command=self._run)
        self.btn_run.pack(side="left")
        self.btn_stop = ttk.Button(ctrl, text="■ Остановить", command=self._stop, state="disabled")
        self.btn_stop.pack(side="left", padx=8)
        self.btn_open = ttk.Button(ctrl, text="📂 Открыть результат", command=self._open_result, state="disabled")
        self.btn_open.pack(side="left", padx=8)

        # Log output
        log_box = ttk.LabelFrame(frm, text="Вывод")
        log_box.pack(fill="both", expand=True, **pad)

        self.txt = tk = ttk  # for type check hack; replaced below

        # Use tkinter Text with scrollbar
        import tkinter as tk
        self.txt = tk.Text(log_box, wrap="word", height=16)
        self.txt.pack(side="left", fill="both", expand=True)
        scr = ttk.Scrollbar(log_box, command=self.txt.yview)
        scr.pack(side="right", fill="y")
        self.txt.configure(yscrollcommand=scr.set)

        self._append("Готово. Выберите уровень/опции и нажмите ▶ Запустить.\n")

    def _append(self, s: str) -> None:
        try:
            self.txt.insert("end", s)
            self.txt.see("end")
            self.txt.update_idletasks()
        except Exception:
            pass

    def _pick_osc_dir(self) -> None:
        d = filedialog.askdirectory(title="Выберите папку osc_dir (NPZ)")
        if d:
            self.osc_dir.set(d)

    def _pick_out_root(self) -> None:
        d = filedialog.askdirectory(title="Выберите папку out_root (diagnostics)")
        if d:
            self.out_root.set(d)

    def _build_cmd(self) -> list[str]:
        py = _guess_python_exe()
        script = TOOLS_DIR / "run_full_diagnostics.py"
        cmd = [str(py), str(script), "--level", self.level.get()]

        if self.skip_ui_smoke.get():
            cmd += ["--skip_ui_smoke"]
        if self.no_zip.get():
            cmd += ["--no_zip"]
        if self.run_opt_smoke.get():
            cmd += ["--run_opt_smoke", "--opt_minutes", str(int(self.opt_minutes.get())), "--opt_jobs", str(int(self.opt_jobs.get()))]

        osc_dir = Path(self.osc_dir.get()).expanduser()
        if osc_dir.exists():
            cmd += ["--osc_dir", str(osc_dir)]

        out_root = Path(self.out_root.get()).expanduser()
        cmd += ["--out_root", str(out_root)]

        return cmd

    def _run(self) -> None:
        if self._proc is not None:
            return

        cmd = self._build_cmd()
        self._append("\n=== Запуск ===\n" + " ".join(cmd) + "\n\n")

        self.btn_run.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_open.configure(state="disabled")

        def worker() -> None:
            try:
                # Make stdout unbuffered
                env = os.environ.copy()
                env.setdefault("PYTHONUTF8", "1")
                env.setdefault("PYTHONIOENCODING", "utf-8")

                self._proc = subprocess.Popen(
                    cmd,
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                )
                assert self._proc.stdout is not None

                last_zip = None
                last_run_dir = None

                for line in self._proc.stdout:
                    self.root.after(0, self._append, line)
                    if line.startswith("Zip:"):
                        try:
                            last_zip = Path(line.split("Zip:", 1)[1].strip()).resolve()
                        except Exception:
                            pass
                    if line.startswith("Diagnostics written to:"):
                        try:
                            last_run_dir = Path(line.split("Diagnostics written to:", 1)[1].strip()).resolve()
                        except Exception:
                            pass

                rc = self._proc.wait()
                self._proc = None

                self._last_zip = last_zip
                self._last_run_dir = last_run_dir

                def done_ui() -> None:
                    self.btn_run.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    self.btn_open.configure(state="normal" if (last_zip or last_run_dir) else "disabled")

                    if rc == 0:
                        msg = "Диагностика завершена успешно."
                        if last_zip:
                            msg += f"\n\nZIP: {last_zip}"
                        if last_run_dir:
                            msg += f"\n\nDIR: {last_run_dir}"
                        messagebox.showinfo("OK", msg)
                    else:
                        messagebox.showwarning("Ошибка", f"Диагностика завершилась с кодом {rc}. См. вывод ниже.")
                self.root.after(0, done_ui)

            except Exception as e:
                self._proc = None
                def err_ui() -> None:
                    self.btn_run.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    self.btn_open.configure(state="disabled")
                    messagebox.showerror("Ошибка", f"Не удалось запустить диагностику:\n{e}")
                self.root.after(0, err_ui)

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def _stop(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._append("\n[GUI] terminate() отправлен...\n")
        except Exception:
            pass

    def _open_result(self) -> None:
        p = self._last_zip or self._last_run_dir
        if p:
            if p.is_file():
                _open_in_explorer(p.parent)
            else:
                _open_in_explorer(p)

    def on_close(self) -> None:
        try:
            self._stop()
        except Exception:
            pass
        self.root.destroy()


def main() -> int:
    root = Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
