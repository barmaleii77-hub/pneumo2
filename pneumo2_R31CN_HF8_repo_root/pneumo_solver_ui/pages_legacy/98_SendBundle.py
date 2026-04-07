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

import streamlit as st
from pneumo_solver_ui.streamlit_compat import safe_set_page_config

from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

from pneumo_solver_ui.tools.make_send_bundle import make_send_bundle

bootstrap(st)
autosave_if_enabled(st)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = (REPO_ROOT / "send_bundles").resolve()


def _build_and_read_zip() -> bytes:
    # Генерация происходит по клику на кнопку скачивания (Streamlit вызывает callable).
    make_send_bundle(REPO_ROOT, out_dir=OUT_DIR, keep_last_n=3, max_file_mb=80, include_workspace_osc=False)
    latest = OUT_DIR / "latest_send_bundle.zip"
    if latest.exists():
        return latest.read_bytes()

    # fallback (если по какой-то причине latest не создался)
    # найдём самый свежий SEND_*.zip
    zips = sorted(OUT_DIR.glob("SEND_*_bundle.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if zips:
        return zips[0].read_bytes()

    return b""


safe_set_page_config(page_title="Отправка ZIP", layout="centered")

st.title("Отправка результатов (ZIP)")

st.markdown(
    "Эта страница содержит **ровно одну кнопку**. Нажмите её, чтобы получить ZIP для отправки в чат.\n\n"
    "ZIP также автоматически сохраняется на диск: `send_bundles/latest_send_bundle.zip`."
)

# *** ЕДИНСТВЕННАЯ КНОПКА ***
st.download_button(
    "⬇️ Скачать ZIP для чата",
    data=_build_and_read_zip,
    file_name="latest_send_bundle.zip",
    mime="application/zip",
)

st.caption(
    "Если вы закрываете приложение через Ctrl+C в консоли, после остановки Streamlit откроется отдельное окно "
    "с одной кнопкой (копирование ZIP в буфер обмена) — см. RUN_WINDOWS.bat." 
)
