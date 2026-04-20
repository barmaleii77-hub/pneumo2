# -*- coding: utf-8 -*-
"""run_autotest_gui.py

Tkinter GUI wrapper for `pneumo_solver_ui/tools/run_autotest.py`.

Run:
  python pneumo_solver_ui/tools/run_autotest_gui.py

Windows convenience launcher:
  RUN_AUTOTEST_GUI_WINDOWS.bat
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

from tkinter import Tk, Text, StringVar, BooleanVar, END
from tkinter import messagebox
from tkinter import ttk

from pneumo_solver_ui.tools.send_bundle_contract import (
    ANIM_DIAG_SIDECAR_JSON,
    format_anim_dashboard_brief_lines,
    load_latest_send_bundle_anim_dashboard,
)

try:
    from pneumo_solver_ui.release_info import get_release

    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


AUTOTEST_LEVELS = {
    "Быстро": "quick",
    "Стандартно": "standard",
    "Полностью": "full",
}
AUTOTEST_LEVEL_LABELS_BY_KEY = {value: label for label, value in AUTOTEST_LEVELS.items()}


@dataclass
class RunState:
    proc: subprocess.Popen[str] | None = None
    last_run_dir: str | None = None
    last_zip: str | None = None
    start_time: float = 0.0


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _guess_python() -> str:
    """Prefer local .venv python if exists, else fall back to current interpreter."""
    root = _repo_root()
    cand_win = root / ".venv" / "Scripts" / "python.exe"
    if cand_win.exists():
        return str(cand_win)
    cand_posix = root / ".venv" / "bin" / "python"
    if cand_posix.exists():
        return str(cand_posix)
    return sys.executable or "python"


def _autotest_level_key(label: str) -> str:
    text = str(label or "").strip()
    return AUTOTEST_LEVELS.get(text, text if text in AUTOTEST_LEVEL_LABELS_BY_KEY else "standard")


def _autotest_level_label(value: str) -> str:
    return AUTOTEST_LEVEL_LABELS_BY_KEY.get(str(value or "").strip(), "Стандартно")


def _operator_output_line(line: str) -> str:
    text = str(line)
    replacements = {
        "CMD:": "Команда запуска:",
        "Run dir:": "Папка результата:",
        "Zip:": "Архив:",
        "ZIP:": "Архив:",
        "[process exit code:": "[код завершения процесса:",
        "[STOP requested]": "[запрошена остановка]",
        "=== AUTOTEST FINISHED ===": "=== АВТОТЕСТ ЗАВЕРШЁН ===",
        "AUTOTEST": "АВТОТЕСТ",
        "Autotest": "Автотест",
        "ready": "готово",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _open_in_file_manager(path: str) -> None:
    """Best-effort open folder in OS file manager."""
    try:
        p = Path(path)
        if p.is_file():
            p = p.parent
        if sys.platform.startswith("win"):
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
    except Exception:
        return


class App:
    def __init__(self, host: tk.Misc | None = None, *, hosted: bool = False) -> None:
        self._owns_root = host is None
        self._hosted = bool(hosted or not self._owns_root)
        self.root = host if host is not None else Tk()
        if self._owns_root:
            self.root.title(f"Автотесты проекта ({RELEASE})")
            self.root.geometry("920x620")

        self.level = StringVar(value=_autotest_level_label("standard"))
        self.no_zip = BooleanVar(value=False)
        self.open_send_gui = BooleanVar(value=True)
        self.auto_open_folder = BooleanVar(value=False)

        self.q: "queue.Queue[str]" = queue.Queue()
        self.state = RunState()
        self._host_closed = False
        self._tick_after_id: str | None = None

        self._build_ui()
        if self._owns_root:
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._schedule_tick()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Уровень:").pack(side="left")
        lvl = ttk.Combobox(
            top,
            textvariable=self.level,
            values=list(AUTOTEST_LEVELS),
            width=14,
            state="readonly",
        )
        lvl.pack(side="left", padx=(6, 16))

        ttk.Checkbutton(top, text="Не создавать архив", variable=self.no_zip).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(top, text="После завершения открыть сохранение архива проекта", variable=self.open_send_gui).pack(
            side="left", padx=(0, 16)
        )
        ttk.Checkbutton(top, text="Открыть папку результата", variable=self.auto_open_folder).pack(side="left")

        btns = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        btns.pack(fill="x")

        self.btn_run = ttk.Button(btns, text="Запустить автотест", command=self._on_run)
        self.btn_run.pack(side="left")

        self.btn_stop = ttk.Button(btns, text="Остановить", command=self._on_stop, state="disabled")
        self.btn_stop.pack(side="left", padx=(8, 0))

        self.btn_open = ttk.Button(btns, text="Открыть папку автотестов", command=self._open_autotest_runs)
        self.btn_open.pack(side="left", padx=(8, 0))

        self.status = StringVar(value="Готов.")
        ttk.Label(btns, textvariable=self.status).pack(side="right")

        self.text = Text(self.root, wrap="word")
        self.text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self._append("Окно автотестов готово.\n")

    def _append(self, s: str) -> None:
        self.text.insert(END, s)
        self.text.see(END)

    def _open_autotest_runs(self) -> None:
        p = _repo_root() / "pneumo_solver_ui" / "autotest_runs"
        p.mkdir(parents=True, exist_ok=True)
        _open_in_file_manager(str(p))

    def _on_run(self) -> None:
        if self.state.proc is not None:
            messagebox.showwarning("Автотесты", "Тест уже запущен.")
            return

        py = _guess_python()
        repo = _repo_root()
        script = repo / "pneumo_solver_ui" / "tools" / "run_autotest.py"

        cmd = [py, "-u", str(script), "--level", _autotest_level_key(self.level.get())]
        if self.no_zip.get():
            cmd.append("--no_zip")

        self._append("\n" + "=" * 72 + "\n")
        self._append("Команда запуска: " + " ".join(cmd) + "\n")
        self._append("=" * 72 + "\n")

        try:
            self.state = RunState(proc=None, last_run_dir=None, last_zip=None, start_time=time.time())
            self.status.set("Запуск...")
            self.btn_run.config(state="disabled")
            self.btn_stop.config(state="normal")

            proc = subprocess.Popen(
                cmd,
                cwd=str(repo),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.state.proc = proc

            t = threading.Thread(target=self._reader_thread, daemon=True)
            t.start()
        except Exception as e:
            self.state.proc = None
            self.btn_run.config(state="normal")
            self.btn_stop.config(state="disabled")
            self.status.set("Ошибка запуска.")
            messagebox.showerror("Автотесты", f"Не удалось запустить: {e}")

    def _reader_thread(self) -> None:
        assert self.state.proc is not None
        proc = self.state.proc
        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    if line.startswith("Run dir:"):
                        self.state.last_run_dir = line.split("Run dir:", 1)[1].strip()
                    if line.startswith("Zip:"):
                        self.state.last_zip = line.split("Zip:", 1)[1].strip()
                    self.q.put(_operator_output_line(line))
        finally:
            rc = proc.wait()
            self.q.put(f"\n[код завершения процесса: {rc}]\n")
            self.q.put("__PROC_DONE__" + str(rc))

    def _on_stop(self) -> None:
        proc = self.state.proc
        if proc is None:
            return
        try:
            self._append("\n[запрошена остановка]\n")
            proc.terminate()
        except Exception:
            return

    def _tick(self) -> None:
        if self._host_closed:
            return
        self._tick_after_id = None
        try:
            while True:
                msg = self.q.get_nowait()
                if msg.startswith("__PROC_DONE__"):
                    rc_str = msg.replace("__PROC_DONE__", "")
                    try:
                        rc = int(rc_str)
                    except Exception:
                        rc = 999
                    self._on_finished(rc)
                else:
                    self._append(msg)
        except queue.Empty:
            pass
        self._schedule_tick()

    def _schedule_tick(self) -> None:
        if self._host_closed:
            return
        self._tick_after_id = self.root.after(100, self._tick)

    def _cancel_tick(self) -> None:
        after_id = self._tick_after_id
        self._tick_after_id = None
        if after_id:
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass

    def on_host_close(self) -> None:
        self._host_closed = True
        self._cancel_tick()
        self._on_stop()

    def on_close(self) -> None:
        self.on_host_close()
        if self._owns_root:
            self.root.destroy()

    def _on_finished(self, rc: int) -> None:
        self.status.set(f"Готово. Код завершения: {rc}.")
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")

        self.state.proc = None

        dur = 0.0
        try:
            dur = time.time() - float(self.state.start_time)
        except Exception:
            pass

        msg_lines = [f"Автотест завершён (код {rc}, {dur:.1f} с)."]
        if self.state.last_run_dir:
            msg_lines.append(f"Папка результата: {self.state.last_run_dir}")
        if self.state.last_zip and not self.no_zip.get():
            msg_lines.append(f"Архив: {self.state.last_zip}")
            out_dir = Path(self.state.last_zip).expanduser().resolve().parent
            msg_lines.extend(format_anim_dashboard_brief_lines(load_latest_send_bundle_anim_dashboard(out_dir)))
            diag_json = out_dir / ANIM_DIAG_SIDECAR_JSON
            if diag_json.exists():
                msg_lines.append(f"Сведения о последней анимации: {diag_json}")

        messagebox.showinfo("Автотесты", "\n".join(msg_lines))

        if self.auto_open_folder.get() and self.state.last_run_dir:
            _open_in_file_manager(self.state.last_run_dir)

        if self.open_send_gui.get():
            try:
                repo = _repo_root()
                py = _guess_python()
                script = repo / "pneumo_solver_ui" / "tools" / "send_results_gui.py"
                subprocess.Popen([py, str(script)], cwd=str(repo))
            except Exception as e:
                messagebox.showwarning("Архив проекта", f"Не удалось открыть сохранение архива проекта: {e}")

    def run(self) -> None:
        if self._owns_root:
            self.root.mainloop()


def main() -> int:
    try:
        App().run()
        return 0
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
