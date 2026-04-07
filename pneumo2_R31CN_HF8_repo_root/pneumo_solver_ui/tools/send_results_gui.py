#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""send_results_gui.py

Однокнопочная GUI (tkinter) для отправки результатов в чат.

Требование пользователя:
- после закрытия приложения должен быть ZIP с логами/результатами;
- в интерфейсе должна быть **ОДНА кнопка**: «Скопировать ZIP в буфер обмена».

Улучшения (v6_27):
- окно появляется сразу, ZIP собирается в фоне (thread) + виден прогресс;
- кнопка активируется только когда ZIP готов;
- никакой "обязательной консоли": ошибки пишутся в log-файл (best-effort).

Запуск:
  python -m pneumo_solver_ui.tools.send_results_gui
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import traceback
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import ttk, messagebox

from pneumo_solver_ui.tools.clipboard_file import copy_file_to_clipboard

try:
    from pneumo_solver_ui.release_info import get_release
    RELEASE = get_release()
except Exception:
    RELEASE = os.environ.get("PNEUMO_RELEASE", "UNIFIED_v6_67") or "UNIFIED_v6_67"


def _repo_root() -> Path:
    # tools/ is inside pneumo_solver_ui/, repo root is parent of pneumo_solver_ui
    return Path(__file__).resolve().parents[2]


def _sha256_file(p: Path, buf_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(buf_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _safe_write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _is_full_file_clipboard_success(ok: bool, msg: str) -> bool:
    """True only when the ZIP itself (not just its path text) reached the clipboard."""
    if not ok:
        return False
    m = str(msg)
    return "Copied path as text" not in m and "Fallback(text): Copied path as text" not in m


class SendResultsGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"Отправка результатов — PneumoApp ({RELEASE})")
        self.root.geometry("760x260")

        self.repo_root = _repo_root()
        # Respect persisted diagnostics settings (R59): out_dir + autosave toggles.
        try:
            from pneumo_solver_ui.diagnostics_entrypoint import load_diagnostics_config

            _cfg = load_diagnostics_config(self.repo_root)
            self.out_dir = _cfg.resolved_out_dir(self.repo_root)
            self._autosave_on_exit = bool(_cfg.autosave_on_exit)
        except Exception:
            self.out_dir = (self.repo_root / "send_bundles").resolve()
            self._autosave_on_exit = True

        # state
        self.zip_path: Optional[Path] = None
        self.sha256: str = ""
        self.size_mb: float = 0.0
        self._worker_exc: Optional[str] = None
        self._worker_done = False
        self._clipboard_attempted = False
        self._clipboard_ok = False
        self._clipboard_message = ""

        frm = ttk.Frame(root, padding=14)
        frm.pack(fill="both", expand=True)

        self.lbl_title = ttk.Label(frm, text="Собираю диагностический пакет (ZIP)…", font=("Segoe UI", 12, "bold"))
        self.lbl_title.pack(anchor="w", pady=(0, 8))

        self.lbl_path_caption = ttk.Label(frm, text="Путь к ZIP:")
        self.lbl_path_caption.pack(anchor="w")
        self.lbl_path = ttk.Label(frm, text="(ещё не готово)", wraplength=720)
        self.lbl_path.pack(anchor="w", pady=(2, 10))

        self.pb = ttk.Progressbar(frm, mode="indeterminate")
        self.pb.pack(fill="x", pady=(0, 10))
        self.pb.start(10)

        self.lbl_meta = ttk.Label(frm, text="", wraplength=720)
        self.lbl_meta.pack(anchor="w", pady=(0, 10))

        ttk.Label(
            frm,
            text=(
                "Кнопка станет активной, когда ZIP будет готов.\n"
                "Если файловый clipboard недоступен, будет скопирован путь как текст."
            ),
        ).pack(anchor="w", pady=(0, 10))

        # *** ЕДИНСТВЕННАЯ КНОПКА ***
        self.btn_copy = ttk.Button(frm, text="📋 Скопировать ZIP в буфер обмена", command=self._copy)
        self.btn_copy.state(["disabled"])
        self.btn_copy.pack(anchor="center", pady=(6, 0), ipadx=10, ipady=6)

        # kick off worker
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()
        self.root.after(200, self._poll)

    def _worker(self) -> None:
        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)

            # Respect launcher-provided session dir (if any)
            primary_session_dir = None
            env_sd = os.environ.get("PNEUMO_SESSION_DIR")
            if env_sd:
                try:
                    primary_session_dir = Path(env_sd).expanduser().resolve()
                except Exception:
                    primary_session_dir = Path(env_sd)

            if self._autosave_on_exit:
                # Unified entrypoint (same as UI/crash/watchdog)
                from pneumo_solver_ui.diagnostics_entrypoint import build_full_diagnostics_bundle

                res = build_full_diagnostics_bundle(
                    trigger="exit",
                    repo_root=self.repo_root,
                    primary_session_dir=primary_session_dir,
                    open_folder=False,
                )
                if not res.ok or not res.zip_path:
                    raise RuntimeError(res.message or "bundle build failed")
                self.zip_path = Path(res.zip_path).resolve()
            else:
                # Autosave disabled: try to reuse latest existing bundle.
                cand = None
                try:
                    p_latest = self.out_dir / "latest_send_bundle.zip"
                    if p_latest.exists():
                        cand = p_latest
                except Exception:
                    cand = None
                if cand is None:
                    try:
                        p_txt = self.out_dir / "latest_send_bundle_path.txt"
                        if p_txt.exists():
                            s = (p_txt.read_text(encoding="utf-8", errors="replace") or "").strip()
                            if s:
                                p = Path(s)
                                if p.exists():
                                    cand = p
                    except Exception:
                        cand = None
                if cand is None:
                    raise RuntimeError("Автосохранение при выходе отключено, и нет предыдущего ZIP (latest_send_bundle.*)")
                self.zip_path = Path(cand).resolve()

            if self.zip_path.exists():
                self.sha256 = _sha256_file(self.zip_path)
                self.size_mb = self.zip_path.stat().st_size / (1024 * 1024)
            self._worker_done = True
        except Exception:
            self._worker_exc = traceback.format_exc()
            self._worker_done = True

    def _poll(self) -> None:
        if not self._worker_done:
            self.root.after(200, self._poll)
            return

        self.pb.stop()
        self.pb.configure(mode="determinate", maximum=1.0, value=1.0)

        if self._worker_exc:
            # write error log for pythonw runs (no console)
            try:
                log_dir = (self.repo_root / "pneumo_solver_ui" / "logs").resolve()
                _safe_write_text(log_dir / "send_results_gui_error.log", self._worker_exc)
            except Exception:
                pass
            self.lbl_title.configure(text="Ошибка при сборке ZIP")
            self.lbl_path.configure(text="(см. send_results_gui_error.log)")
            self.lbl_meta.configure(text=self._worker_exc[-1200:])
            messagebox.showerror("PneumoApp: ошибка пакета для чата", self._worker_exc)
            return

        if not self.zip_path:
            self.lbl_title.configure(text="ZIP не создан (неизвестная ошибка)")
            self.lbl_path.configure(text="(нет пути)")
            self.lbl_meta.configure(text="")
            return

        self._attempt_clipboard_copy_once()

        if self._clipboard_ok:
            self.lbl_title.configure(text="ZIP для отправки в чат готов и уже скопирован в буфер.")
        elif self._clipboard_attempted and ("Copied path as text" in str(self._clipboard_message)):
            self.lbl_title.configure(text="ZIP для отправки в чат готов. Путь к ZIP скопирован как текст; файловый clipboard не подтвердился.")
        else:
            self.lbl_title.configure(text="ZIP для отправки в чат готов.")
        self.lbl_path.configure(text=str(self.zip_path))

        extra = ""
        try:
            triage_md = self.out_dir / "latest_triage_report.md"
            if triage_md.exists():
                extra += f"\nTriage report: {triage_md}"
        except Exception:
            pass
        try:
            vj = self.out_dir / "latest_send_bundle_validation.json"
            vm = self.out_dir / "latest_send_bundle_validation.md"
            if vj.exists():
                import json
                j = json.loads(vj.read_text(encoding="utf-8", errors="replace"))
                ok = j.get("ok")
                nerr = len(j.get("errors") or [])
                nwarn = len(j.get("warnings") or [])
                extra += f"\nValidation: ok={ok} errors={nerr} warnings={nwarn}"
                if vm.exists():
                    extra += f"\nValidation report: {vm}"
        except Exception:
            pass
        try:
            diag_json = self.out_dir / "latest_anim_pointer_diagnostics.json"
            if diag_json.exists():
                import json
                d = json.loads(diag_json.read_text(encoding="utf-8", errors="replace"))
                tok = str(d.get("anim_latest_visual_cache_token") or "")
                reload_inputs = list(d.get("anim_latest_visual_reload_inputs") or [])
                if tok:
                    extra += f"\nAnim latest token: {tok}"
                if reload_inputs:
                    extra += "\nAnim reload inputs: " + ", ".join(str(x) for x in reload_inputs)
                extra += f"\nAnim pointer diagnostics: {diag_json}"
        except Exception:
            pass

        clip_line = f"\nClipboard: ok={self._clipboard_ok} msg={self._clipboard_message}" if self._clipboard_attempted else ""
        self.lbl_meta.configure(text=f"Размер: {self.size_mb:.2f} MB\nSHA256: {self.sha256}{extra}{clip_line}")

        if self._clipboard_ok:
            self.btn_copy.configure(text="📋 Скопировать ZIP ещё раз")

        # enable button
        self.btn_copy.state(["!disabled"])


    def _write_clipboard_status(self) -> None:
        if not self.zip_path:
            return
        try:
            payload = {
                "ok": bool(self._clipboard_ok),
                "message": str(self._clipboard_message),
                "zip_path": str(self.zip_path),
            }
            _safe_write_text(
                self.out_dir / "latest_send_bundle_clipboard_status.json",
                json.dumps(payload, ensure_ascii=False, indent=2),
            )
        except Exception:
            pass

    def _attempt_clipboard_copy_once(self) -> None:
        if self._clipboard_attempted or not self.zip_path:
            return
        self._clipboard_attempted = True
        try:
            ok, msg = copy_file_to_clipboard(self.zip_path)
        except Exception:
            ok = False
            msg = traceback.format_exc()
        self._clipboard_ok = _is_full_file_clipboard_success(bool(ok), str(msg))
        self._clipboard_message = str(msg)
        self._write_clipboard_status()

    def _copy(self) -> None:
        if not self.zip_path:
            messagebox.showwarning("Не готово", "ZIP ещё не готов.")
            return
        try:
            ok, msg = copy_file_to_clipboard(self.zip_path)
            self._clipboard_ok = _is_full_file_clipboard_success(bool(ok), str(msg))
            self._clipboard_message = str(msg)
            self._write_clipboard_status()
            if self._clipboard_ok:
                messagebox.showinfo("OK", msg)
            else:
                messagebox.showwarning("Не удалось", msg)
        except Exception:
            messagebox.showerror("Ошибка", traceback.format_exc())


def main() -> int:
    try:
        root = tk.Tk()
        # In some environments ttk themes fail; ignore.
        try:
            style = ttk.Style()
            if "vista" in style.theme_names():
                style.theme_use("vista")
        except Exception:
            pass

        SendResultsGUI(root)
        root.mainloop()
        return 0
    except Exception:
        tb = traceback.format_exc()
        try:
            repo_root = _repo_root()
            log_dir = (repo_root / "pneumo_solver_ui" / "logs").resolve()
            _safe_write_text(log_dir / "send_results_gui_crash.log", tb)
        except Exception:
            pass
        try:
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror("PneumoApp: критическая ошибка", tb)
            r.destroy()
        except Exception:
            # last resort
            sys.stderr.write(tb + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
