# -*- coding: utf-8 -*-
"""Streamlit page: Send Bundle (one button).

Требование пользователя
----------------------
Нужна максимально простая отправка результатов:
- ZIP пишется на диск автоматически (send_bundles/latest_send_bundle.zip)
- в интерфейсе должна быть ОДНА кнопка: "скачать/скопировать ZIP"

В Windows сценарии "скопировать ZIP в буфер" удобнее делать отдельным локальным
окном (tkinter): `pneumo_solver_ui/tools/send_results_gui.py`.

Но иногда проще именно *скачать* ZIP из Streamlit. Эта страница — ровно
одна кнопка download, которая:
  1) собирает send bundle (best-effort)
  2) пишет его на диск в send_bundles/
  3) отдаёт браузеру ZIP как файл.

"""

from __future__ import annotations

from pathlib import Path

import sys

import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled
from pneumo_solver_ui.tools.send_bundle_contract import (
    ANIM_DIAG_SIDECAR_JSON,
    format_anim_dashboard_brief_lines,
    load_latest_send_bundle_anim_dashboard,
)



bootstrap(st)
autosave_if_enabled(st)

try:
    from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
    _ui_bootstrap(st)
except Exception:
    pass

from pneumo_solver_ui.tools.make_send_bundle import make_send_bundle

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = (REPO_ROOT / "send_bundles").resolve()

def _copy_file_to_clipboard_windows(file_path: Path) -> bool:
    # Windows-only: copy a file into clipboard as a FileDropList (so user can Ctrl+V).
    # Returns True on success.
    if sys.platform != "win32":
        return False
    try:
        import subprocess
        p = str(file_path).replace("'", "''")
        ps = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$files = New-Object System.Collections.Specialized.StringCollection; "
            f"$files.Add('{p}'); "
            "[System.Windows.Forms.Clipboard]::SetFileDropList($files)"
        )
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        return r.returncode == 0
    except Exception:
        return False


def _build_and_read_zip() -> bytes:
    # Генерация происходит по клику на кнопку скачивания (Streamlit вызывает callable).
    make_send_bundle(
        REPO_ROOT,
        out_dir=OUT_DIR,
        keep_last_n=3,
        max_file_mb=80,
        include_workspace_osc=False,
    )

    latest = OUT_DIR / "latest_send_bundle.zip"
    if latest.exists():
        try:
            ok = _copy_file_to_clipboard_windows(latest)
        except Exception:
            ok = False
        st.session_state["last_send_bundle_zip"] = str(latest)
        st.session_state["last_send_bundle_clipboard_ok"] = bool(ok)
        st.session_state["last_send_bundle_anim_dashboard"] = load_latest_send_bundle_anim_dashboard(OUT_DIR)
        diag_json = OUT_DIR / ANIM_DIAG_SIDECAR_JSON
        st.session_state["last_send_bundle_anim_diag_path"] = str(diag_json) if diag_json.exists() else ""
        return latest.read_bytes()

    # fallback (если по какой-то причине latest не создался):
    # найдём самый свежий SEND_*.zip
    zips = sorted(OUT_DIR.glob("SEND_*_bundle.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if zips:
        picked = zips[0]
        try:
            ok = _copy_file_to_clipboard_windows(picked)
        except Exception:
            ok = False
        st.session_state["last_send_bundle_zip"] = str(picked)
        st.session_state["last_send_bundle_clipboard_ok"] = bool(ok)
        st.session_state["last_send_bundle_anim_dashboard"] = load_latest_send_bundle_anim_dashboard(OUT_DIR)
        diag_json = OUT_DIR / ANIM_DIAG_SIDECAR_JSON
        st.session_state["last_send_bundle_anim_diag_path"] = str(diag_json) if diag_json.exists() else ""
        return picked.read_bytes()

    st.session_state["last_send_bundle_zip"] = ""
    st.session_state["last_send_bundle_clipboard_ok"] = False
    st.session_state["last_send_bundle_anim_dashboard"] = {}
    st.session_state["last_send_bundle_anim_diag_path"] = ""
    return b""



st.title("Отправка результатов (ZIP)")

st.markdown(
    "Эта страница содержит **ровно одну кнопку**. Нажмите её, чтобы получить ZIP для отправки в чат.\n\n"
    "ZIP также автоматически сохраняется на диск: `send_bundles/latest_send_bundle.zip`."
)

# *** ЕДИНСТВЕННАЯ КНОПКА ***

# Status after a previous click
if st.session_state.get("last_send_bundle_zip"):
    _p = st.session_state.get("last_send_bundle_zip")
    _ok = st.session_state.get("last_send_bundle_clipboard_ok")
    _anim = st.session_state.get("last_send_bundle_anim_dashboard") or {}
    _diag_path = st.session_state.get("last_send_bundle_anim_diag_path") or ""
    if _ok:
        st.success(f"ZIP создан и скопирован в буфер обмена: {_p}")
    else:
        st.info(f"ZIP создан: {_p}")
    _anim_lines = format_anim_dashboard_brief_lines(_anim)
    if _anim_lines:
        st.markdown("\n".join(f"- {line}" for line in _anim_lines))
    if _diag_path:
        st.caption(f"Anim pointer diagnostics: {_diag_path}")

st.download_button(
    "⬇️ Скачать ZIP и скопировать в буфер",
    data=_build_and_read_zip,
    file_name="latest_send_bundle.zip",
    mime="application/zip",
)

st.caption(
    "Кнопка сохраняет архив на диск и пытается скопировать ZIP как файл в буфер обмена (Windows). "
    "Если копирование не удалось — ниже будет доступен путь к ZIP и обычное скачивание."
)

# --- Автосохранение UI (лучшее усилие) ---
# Важно: значения, введённые на этой странице, не должны пропадать при refresh/перезапуске.
