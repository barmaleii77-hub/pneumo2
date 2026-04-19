#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Точка входа desktop-отправки результатов.

Совместимость оставлена намеренно:
- hosted shell по-прежнему импортирует `SendResultsGUI`;
- сценарий отправки по-прежнему держит одно главное действие копирования архива;
- состояние буфера обмена сохраняется в `latest_send_bundle_clipboard_status.json`.

Реальное окно живёт в едином desktop-центре диагностики и отправки, чтобы
оператор собирал архив, читал сводку, проверял архив, смотрел состояние проекта
и отправлял результаты из одного последовательного сценария.
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, ttk

from pneumo_solver_ui.tools.desktop_diagnostics_center import DesktopDiagnosticsCenter
from pneumo_solver_ui.desktop_diagnostics_runtime import (
    load_desktop_diagnostics_bundle_record,
    write_send_bundle_clipboard_status,
)
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


_LEGACY_SEND_SUMMARY_HELPERS = (
    ANIM_DIAG_SIDECAR_JSON,
    load_latest_send_bundle_anim_dashboard,
    format_anim_dashboard_brief_lines,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _log_dir() -> Path:
    return (_repo_root() / "pneumo_solver_ui" / "logs").resolve()


def _sha256_file(path: Path, buf_size: int = 1024 * 1024) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(buf_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _safe_write_text(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _is_full_file_clipboard_success(ok: bool, msg: str) -> bool:
    if not ok:
        return False
    text = str(msg or "")
    return "Copied path as text" not in text and "Fallback(text): Copied path as text" not in text


class SendResultsGUI(DesktopDiagnosticsCenter):
    READY_COPIED_TITLE = "Архив для отправки в чат готов и уже скопирован в буфер."
    CLIPBOARD_STATUS_JSON = "latest_send_bundle_clipboard_status.json"
    ANIM_POINTER_CAPTION = "Диагностика последней анимации:"

    def __init__(self, root: tk.Misc, hosted: bool = False) -> None:
        reuse_latest = str(os.environ.get("PNEUMO_SEND_RESULTS_REUSE_LATEST", "0")).strip() == "1"
        bundle_state = load_desktop_diagnostics_bundle_record(_repo_root())
        super().__init__(
            root,
            hosted=hosted,
            initial_tab="send",
            auto_build_bundle=(not reuse_latest) or (not bundle_state.latest_zip_path),
        )
        if not self._hosted:
            self.root.title(f"Отправка результатов — PneumoApp ({RELEASE})")

        self.send_title_var.set(self.READY_COPIED_TITLE if self._clipboard_ok else self.send_title_var.get())

        # Совместимый eager-hook оставлен для старых launcher-интеграций;
        # сбрасываем guard, чтобы свежий архив всё равно скопировался один раз.
        self._attempt_clipboard_copy_once()
        self._clipboard_attempted = False

    def _attempt_clipboard_copy_once(self) -> None:
        return super()._attempt_clipboard_copy_once()

    def _write_clipboard_status(self) -> None:
        if not self.zip_path:
            return
        write_send_bundle_clipboard_status(self.out_dir, self.zip_path, bool(self._clipboard_ok), str(self._clipboard_message))

    def _worker(self) -> None:
        self._start_bundle_build(auto_copy_on_ready=True)

    def _poll(self) -> None:
        self._refresh_bundle_views(regenerate_reports=False)

    def _copy(self) -> None:
        return super()._copy()

    def _on_bundle_build_finished(self, ok: bool, zip_path: str, message: str) -> None:
        if not ok:
            try:
                _safe_write_text(_log_dir() / "send_results_gui_error.log", str(message or "Не удалось собрать архив отправки"))
            except Exception:
                pass
        super()._on_bundle_build_finished(ok, zip_path, message)

    def on_host_close(self) -> None:
        self._host_closed = True
        super().on_host_close()


def main() -> int:
    try:
        root = tk.Tk()
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
            _safe_write_text(_log_dir() / "send_results_gui_crash.log", tb)
        except Exception:
            pass
        try:
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror("PneumoApp: критическая ошибка", tb)
            r.destroy()
        except Exception:
            pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
