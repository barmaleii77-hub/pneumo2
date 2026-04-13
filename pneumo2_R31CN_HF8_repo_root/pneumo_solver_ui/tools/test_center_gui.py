# -*- coding: utf-8 -*-
"""test_center_gui.py

Autonomous Testing Center (Tkinter GUI) — R54

Goal
----
Provide a *single* standalone GUI to run the most important autonomous checks:
- Autotest Harness (`tools/run_autotest.py`)
- Full Diagnostics (`tools/run_full_diagnostics.py`)
- Optional Send Bundle creation + open the shared diagnostics/send desktop center

This GUI intentionally runs underlying tools as subprocesses so that:
- stdout/stderr is captured exactly as in CLI
- failures can't corrupt the GUI process state
- logs/artifacts are still produced in the standard project folders

Run
---
  python pneumo_solver_ui/tools/test_center_gui.py

Windows convenience launcher:
  RUN_TEST_CENTER_GUI_WINDOWS.bat
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


# Release (best-effort)
try:
    from pneumo_solver_ui.release_info import get_release
    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"

# R49: Run Registry (best-effort)
try:
    from pneumo_solver_ui.run_registry import append_event, env_context
except Exception:
    append_event = None  # type: ignore
    env_context = None  # type: ignore

def _rr(action: str, **fields):
    try:
        if append_event is None:
            return
        ctx = {}
        try:
            if env_context is not None:
                ctx = {"env": env_context()}
        except Exception:
            ctx = {}
        append_event({
            "event": "test_center_action",
            "run_type": "test_center",
            "run_id": os.environ.get("PNEUMO_RUN_ID") or "TEST_CENTER",
            "status": "info",
            "action": action,
            **fields,
            **ctx,
        })
    except Exception:
        return


from tkinter import Tk, Text, StringVar, BooleanVar, IntVar, END
from tkinter import messagebox
from tkinter import ttk

from pneumo_solver_ui.desktop_ui_core import ScrollableFrame, build_scrolled_text, build_status_strip
from pneumo_solver_ui.desktop_results_runtime import DesktopResultsRuntime
from pneumo_solver_ui.desktop_results_model import DesktopResultsSessionHandoff
from pneumo_solver_ui.tools.desktop_results_center import DesktopResultsCenter
from pneumo_solver_ui.tools.send_bundle_contract import (
    ANIM_DIAG_SIDECAR_JSON,
    format_anim_dashboard_brief_lines,
    load_latest_send_bundle_anim_dashboard,
)


@dataclass
class RunState:
    proc: subprocess.Popen[str] | None = None
    start_time: float = 0.0
    last_zip: str | None = None
    requested_autotest: bool = False
    requested_diagnostics: bool = False
    requested_send_bundle: bool = False
    autotest_rc: int | None = None
    diagnostics_rc: int | None = None
    send_bundle_ok: bool | None = None
    send_bundle_error: str = ""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _guess_python() -> str:
    root = _repo_root()
    cand_win = root / ".venv" / "Scripts" / "python.exe"
    if cand_win.exists():
        return str(cand_win)
    cand_posix = root / ".venv" / "bin" / "python"
    if cand_posix.exists():
        return str(cand_posix)
    return sys.executable or "python"


def _open_in_file_manager(path: str) -> None:
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
        self.repo = _repo_root()
        self.py = _guess_python()
        self.results_runtime = DesktopResultsRuntime(
            repo_root=self.repo,
            python_executable=self.py,
        )

        self._owns_root = host is None
        self._hosted = bool(hosted or not self._owns_root)
        self.root = host if host is not None else Tk()
        if self._owns_root:
            self.root.title(f"Центр тестов и проверки результатов ({RELEASE})")
            self.root.geometry("1180x760")
            self.root.minsize(1040, 720)

        # What to run
        self.do_autotest = BooleanVar(value=True)
        self.do_diagnostics = BooleanVar(value=True)

        self.autotest_level = StringVar(value="standard")
        self.diagnostics_level = StringVar(value="standard")

        # Diagnostics options
        self.skip_ui_smoke = BooleanVar(value=False)
        self.run_opt_smoke = BooleanVar(value=False)
        self.opt_minutes = IntVar(value=2)
        self.opt_jobs = IntVar(value=2)

        # After run
        self.make_send_bundle = BooleanVar(value=True)
        self.open_send_gui = BooleanVar(value=False)
        self.auto_open_folder = BooleanVar(value=False)
        self.continue_on_failure = BooleanVar(value=True)

        self.q: "queue.Queue[str]" = queue.Queue()
        self.state = RunState()
        self._host_closed = False

        self._build_ui()
        self.root.after(100, self._tick)

    def _build_ui(self) -> None:
        pad = 10

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        run_tab = ttk.Frame(self.notebook)
        self.results_center = DesktopResultsCenter(
            self.notebook,
            runtime=self.results_runtime,
        )
        self.notebook.add(run_tab, text="Тесты и проверка")
        self.notebook.add(self.results_center, text="Результаты и анализ")

        run_split = ttk.Panedwindow(run_tab, orient="vertical")
        run_split.pack(fill="both", expand=True)
        config_scroll = ScrollableFrame(run_split)
        run_split.add(config_scroll, weight=0)
        log_frame = ttk.LabelFrame(run_split, text="Журнал выполнения", padding=pad)
        run_split.add(log_frame, weight=1)
        config_body = config_scroll.body
        config_body.columnconfigure(0, weight=1)

        top = ttk.Frame(config_body, padding=pad)
        top.pack(fill="x")

        ttk.Label(top, text="Что запускать:").grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(top, text="Автотест", variable=self.do_autotest).grid(row=0, column=1, sticky="w", padx=(8, 0))
        ttk.Checkbutton(top, text="Полная диагностика", variable=self.do_diagnostics).grid(row=0, column=2, sticky="w", padx=(8, 0))

        # Levels
        lvl = ttk.Frame(config_body, padding=(pad, 0, pad, pad))
        lvl.pack(fill="x")

        ttk.Label(lvl, text="Уровень автотеста:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(lvl, textvariable=self.autotest_level, values=["quick", "standard", "full"], width=12, state="readonly").grid(row=0, column=1, sticky="w", padx=(6, 16))

        ttk.Label(lvl, text="Уровень диагностики:").grid(row=0, column=2, sticky="w")
        ttk.Combobox(lvl, textvariable=self.diagnostics_level, values=["minimal", "standard", "full"], width=12, state="readonly").grid(row=0, column=3, sticky="w", padx=(6, 16))

        ttk.Checkbutton(lvl, text="Продолжать при ошибках", variable=self.continue_on_failure).grid(row=0, column=4, sticky="w")
        lvl.columnconfigure(5, weight=1)

        # Diagnostics options
        diag = ttk.LabelFrame(config_body, text="Опции полной диагностики", padding=pad)
        diag.pack(fill="x", padx=pad, pady=(0, pad))

        ttk.Checkbutton(diag, text="Пропустить быструю проверку интерфейса (не запускать Streamlit)", variable=self.skip_ui_smoke).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(diag, text="Быстрая проверка оптимизации", variable=self.run_opt_smoke).grid(row=1, column=0, sticky="w", pady=(6, 0))

        row = ttk.Frame(diag)
        row.grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(6, 0))
        ttk.Label(row, text="минут:").pack(side="left")
        ttk.Spinbox(row, from_=1, to=60, textvariable=self.opt_minutes, width=6).pack(side="left", padx=(6, 16))
        ttk.Label(row, text="задач:").pack(side="left")
        ttk.Spinbox(row, from_=1, to=32, textvariable=self.opt_jobs, width=6).pack(side="left", padx=(6, 0))

        diag.columnconfigure(2, weight=1)

        # After run
        aft = ttk.LabelFrame(config_body, text="После завершения", padding=pad)
        aft.pack(fill="x", padx=pad, pady=(0, pad))
        ttk.Checkbutton(aft, text="Создать пакет для отправки (ZIP для чата)", variable=self.make_send_bundle).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(aft, text="Сразу открыть центр диагностики и отправки", variable=self.open_send_gui).grid(row=0, column=1, sticky="w", padx=(16, 0))
        ttk.Checkbutton(aft, text="Открыть папку пакетов отправки", variable=self.auto_open_folder).grid(row=0, column=2, sticky="w", padx=(16, 0))
        aft.columnconfigure(3, weight=1)

        # Buttons
        btns = ttk.Frame(config_body, padding=(pad, 0, pad, pad))
        btns.pack(fill="x")
        self.btn_run = ttk.Button(btns, text="▶ Запустить автономное тестирование", command=self._on_run)
        self.btn_run.pack(side="left")

        self.btn_stop = ttk.Button(btns, text="■ Остановить", command=self._on_stop, state="disabled")
        self.btn_stop.pack(side="left", padx=(8, 0))

        ttk.Button(btns, text="📂 Пакеты отправки", command=self._open_send_bundles).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="📂 Папка автотеста", command=self._open_autotest_runs).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="📂 Папка диагностики", command=self._open_diagnostics_runs).pack(side="left", padx=(8, 0))
        ttk.Button(
            btns,
            text="Результаты и анализ",
            command=lambda: self.notebook.select(self.results_center),
        ).pack(side="left", padx=(8, 0))

        self.status = StringVar(value="Готов.")
        ttk.Label(btns, textvariable=self.status).pack(side="right")

        output_body, self.text = build_scrolled_text(log_frame, wrap="word", height=16)
        output_body.pack(fill="both", expand=True)
        self._append("Центр тестов и проверки результатов готов.\n")

        footer = build_status_strip(self.root, primary_var=self.status)
        footer.pack(fill="x", padx=pad, pady=(0, pad))

    def _append(self, s: str) -> None:
        self.text.insert(END, s)
        self.text.see(END)

    def _open_send_bundles(self) -> None:
        p = self.repo / "send_bundles"
        p.mkdir(parents=True, exist_ok=True)
        _open_in_file_manager(str(p))

    def _open_autotest_runs(self) -> None:
        p = self.repo / "pneumo_solver_ui" / "autotest_runs"
        p.mkdir(parents=True, exist_ok=True)
        _open_in_file_manager(str(p))

    def _open_diagnostics_runs(self) -> None:
        p = self.repo / "diagnostics_runs"
        p.mkdir(parents=True, exist_ok=True)
        _open_in_file_manager(str(p))

    def _on_run(self) -> None:
        if self.state.proc is not None:
            messagebox.showwarning("Testing", "Процесс уже запущен.")
            return

        if not self.do_autotest.get() and not self.do_diagnostics.get():
            messagebox.showwarning("Testing", "Нечего запускать: выберите хотя бы один пункт.")
            return

        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.status.set("Запуск...")

        self.state = RunState(
            proc=None,
            start_time=time.time(),
            last_zip=None,
            requested_autotest=bool(self.do_autotest.get()),
            requested_diagnostics=bool(self.do_diagnostics.get()),
            requested_send_bundle=bool(self.make_send_bundle.get()),
        )

        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    def _on_stop(self) -> None:
        proc = self.state.proc
        if proc is None:
            return
        try:
            self._append("\n[STOP requested]\n")
            proc.terminate()
        except Exception:
            return

    def _run_cmd(self, cmd: list[str], label: str) -> int:
        self.q.put("\n" + "=" * 80 + "\n")
        self.q.put(f"[STEP] {label}\n")
        self.q.put("CMD: " + " ".join(cmd) + "\n")
        self.q.put("=" * 80 + "\n")

        _rr("cmd_start", label=label, cmd=cmd)

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.repo),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as e:
            self.q.put(f"[FAILED TO START] {e}\n")
            return 999

        self.state.proc = proc

        try:
            if proc.stdout is not None:
                for line in proc.stdout:
                    self.q.put(line)
        finally:
            rc = 999
            try:
                rc = int(proc.wait())
            except Exception:
                rc = 999
            self.state.proc = None

        _rr("cmd_end", label=label, rc=rc)
        self.q.put(f"\n[STEP DONE] {label} rc={rc}\n")
        return rc

    def _worker(self) -> None:
        final_rc = 0

        try:
            if self.do_autotest.get():
                cmd = [self.py, "-u", str(self.repo / "pneumo_solver_ui" / "tools" / "run_autotest.py"), "--level", self.autotest_level.get().strip()]
                rc = self._run_cmd(cmd, f"Автотест ({self.autotest_level.get()})")
                self.state.autotest_rc = rc
                if rc != 0:
                    final_rc = rc
                    if not self.continue_on_failure.get():
                        self.q.put("[ОСТАНОВ] Прекращаем после ошибки (continue_on_failure=0).\n")
                        self.q.put("__ALL_DONE__" + str(final_rc))
                        return

            if self.do_diagnostics.get():
                cmd = [self.py, "-u", str(self.repo / "pneumo_solver_ui" / "tools" / "run_full_diagnostics.py"), "--level", self.diagnostics_level.get().strip()]
                if self.skip_ui_smoke.get():
                    cmd.append("--skip_ui_smoke")
                if self.run_opt_smoke.get():
                    cmd += ["--run_opt_smoke", "--opt_minutes", str(int(self.opt_minutes.get())), "--opt_jobs", str(int(self.opt_jobs.get()))]
                rc = self._run_cmd(cmd, f"Полная диагностика ({self.diagnostics_level.get()})")
                self.state.diagnostics_rc = rc
                if rc != 0:
                    final_rc = rc
                    if not self.continue_on_failure.get():
                        self.q.put("[ОСТАНОВ] Прекращаем после ошибки (continue_on_failure=0).\n")
                        self.q.put("__ALL_DONE__" + str(final_rc))
                        return

            if self.make_send_bundle.get():
                self.q.put("\n" + "=" * 80 + "\n")
                self.q.put("[ШАГ] Сборка пакета отправки\n")
                self.q.put("=" * 80 + "\n")
                _rr("send_bundle_start")
                try:
                    from pneumo_solver_ui.tools.make_send_bundle import make_send_bundle

                    out_dir = (self.repo / "send_bundles").resolve()
                    out_dir.mkdir(parents=True, exist_ok=True)
                    zip_path = make_send_bundle(self.repo, out_dir=out_dir, keep_last_n=3, max_file_mb=80, include_workspace_osc=False)
                    self.state.last_zip = str(zip_path)
                    self.state.send_bundle_ok = True
                    self.state.send_bundle_error = ""
                    self.q.put(f"ZIP: {zip_path}\n")
                    _rr("send_bundle_done", zip_path=str(zip_path))
                except Exception as e:
                    self.state.send_bundle_ok = False
                    self.state.send_bundle_error = str(e)
                    _rr("send_bundle_failed", error=repr(e))
                    self.q.put(f"[Ошибка сборки пакета отправки] {e}\n")
                    if final_rc == 0:
                        final_rc = 2

        finally:
            self.q.put("__ALL_DONE__" + str(final_rc))

    def _tick(self) -> None:
        if self._host_closed:
            return
        try:
            while True:
                msg = self.q.get_nowait()
                if msg.startswith("__ALL_DONE__"):
                    rc_str = msg.replace("__ALL_DONE__", "")
                    try:
                        rc = int(rc_str)
                    except Exception:
                        rc = 999
                    self._on_finished(rc)
                else:
                    self._append(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._tick)

    def on_host_close(self) -> None:
        self._host_closed = True
        self._on_stop()

    def _on_finished(self, rc: int) -> None:
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.status.set(f"Готово. RC={rc}.")
        self.results_center.refresh()
        dur = 0.0
        try:
            dur = time.time() - float(self.state.start_time)
        except Exception:
            pass
        snapshot = self.results_center.snapshot_state
        step_lines: list[str] = []
        if self.state.requested_autotest:
            step_lines.append(
                f"Автотест ({self.autotest_level.get()}): rc={self.state.autotest_rc}"
            )
        if self.state.requested_diagnostics:
            step_lines.append(
                f"Полная диагностика ({self.diagnostics_level.get()}): rc={self.state.diagnostics_rc}"
            )
        if self.state.requested_send_bundle:
            if self.state.send_bundle_ok:
                step_lines.append("Пакет отправки: готов")
            elif self.state.send_bundle_ok is False:
                step_lines.append("Пакет отправки: ошибка")
        if self.open_send_gui.get():
            step_lines.append("Автооткрытие центра отправки: вкл")
        if self.auto_open_folder.get():
            step_lines.append("Автооткрытие папки пакетов: вкл")
        handoff_detail = (
            f"Прогон завершён с кодом {rc} за {dur:.1f} с. "
            "Ниже подготовлен рекомендуемый следующий шаг для проверки и разбора результатов."
        )
        if self.state.send_bundle_error:
            handoff_detail = handoff_detail + f" Ошибка пакета отправки: {self.state.send_bundle_error}"
        self.results_center.set_session_handoff(
            DesktopResultsSessionHandoff(
                summary=f"rc={rc} | duration={dur:.1f}s",
                detail=handoff_detail,
                step_lines=tuple(step_lines),
                zip_path=Path(self.state.last_zip).expanduser().resolve()
                if self.state.last_zip
                else None,
                autotest_run_dir=(
                    snapshot.latest_autotest_run_dir if snapshot is not None else None
                ),
                diagnostics_run_dir=(
                    snapshot.latest_diagnostics_run_dir if snapshot is not None else None
                ),
            )
        )
        self.notebook.select(self.results_center)

        msg_lines = [
            f"Автономное тестирование завершено (rc={rc}, {dur:.1f} s).",
            "Сводка проверки и результатов обновлена во второй вкладке.",
        ]
        if self.state.last_zip:
            msg_lines.append(f"ZIP: {self.state.last_zip}")
            out_dir = Path(self.state.last_zip).expanduser().resolve().parent
            msg_lines.extend(format_anim_dashboard_brief_lines(load_latest_send_bundle_anim_dashboard(out_dir)))
            diag_json = out_dir / ANIM_DIAG_SIDECAR_JSON
            if diag_json.exists():
                msg_lines.append(f"Диагностика указателя анимации: {diag_json}")

        messagebox.showinfo("Автономное тестирование", "\n".join(msg_lines))

        if self.auto_open_folder.get():
            try:
                p = self.repo / "send_bundles"
                _open_in_file_manager(str(p))
            except Exception:
                pass

        if self.open_send_gui.get():
            try:
                env = os.environ.copy()
                if self.make_send_bundle.get() and self.state.last_zip:
                    env["PNEUMO_SEND_RESULTS_REUSE_LATEST"] = "1"
                self.results_runtime.launch_send_results_gui(env=env)
            except Exception:
                pass

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
