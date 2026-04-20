# -*- coding: utf-8 -*-
"""Streamlit page: environment check.

Цель:
- Быстро понять, почему у пользователя не работают 2D/3D компоненты или Plotly.
- Снять базовую инфу о среде (Python/Streamlit/Plotly) без ручного поиска.

Эта страница не изменяет модель и не запускает тяжёлые расчёты.
"""

import os
import sys
import platform
from pathlib import Path
import io
import json
import zipfile
import datetime
import traceback

import streamlit as st
from pneumo_solver_ui.diagnostics_entrypoint import (
    read_last_meta_from_out_dir,
    summarize_last_bundle_meta,
)
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled



bootstrap(st)
autosave_if_enabled(st)

try:
    from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
    _ui_bootstrap(st)
except Exception:
    pass

HERE = Path(__file__).resolve().parent.parent
REPO_ROOT = HERE.parent


def _try_import(name: str):
    try:
        mod = __import__(name)
        return True, getattr(mod, "__version__", "(no __version__)")
    except Exception as e:
        return False, repr(e)



st.title("Проверка окружения")

st.markdown(
    "Эта страница помогает быстро локализовать типовые проблемы: **Plotly не установлен**, "
    "запуск не из того Python, отсутствуют/битые ассеты компонентов (mech_anim, mech_car3d, pneumo_svg_flow)."
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Python")
    st.code(
        "\n".join(
            [
                f"sys.executable: {sys.executable}",
                f"Python: {sys.version}",
                f"platform: {platform.platform()}",
            ]
        )
    )

with col2:
    st.subheader("Пакеты")
    ok_s, v_s = _try_import("streamlit")
    ok_p, v_p = _try_import("plotly")
    ok_np, v_np = _try_import("numpy")
    ok_pd, v_pd = _try_import("pandas")
    st.write(
        {
            "streamlit": (ok_s, v_s),
            "plotly": (ok_p, v_p),
            "numpy": (ok_np, v_np),
            "pandas": (ok_pd, v_pd),
        }
    )

st.divider()

st.subheader("Компоненты Streamlit")
comp_root = HERE / "components"
if not comp_root.exists():
    st.error(f"Не найдена папка компонентов: {comp_root}")
else:
    comps = [
        "mech_anim",
        "mech_car3d",
        "pneumo_svg_flow",
        "playhead_ctrl",
    ]
    rows = []
    for c in comps:
        idx = comp_root / c / "index.html"
        rows.append(
            {
                "component": c,
                "index.html": str(idx),
                "exists": idx.exists(),
                "size_kb": round(idx.stat().st_size / 1024.0, 1) if idx.exists() else None,
            }
        )
    st.dataframe(rows, width="stretch", height=220)

st.info(
    "Если компоненты не загружаются или появляются ошибки/предупреждения — это нормально для проверки окружения.\n\n"
    "Главное: **всё должно попадать в логи** и в `events.jsonl`.\n\n"
    "Что делать без консоли:\n"
    "• Откройте эту страницу → сохраните архив проекта → скачайте файл архива.\n"
    "• Если зависимости не установлены/сломаны — запустите **START_PNEUMO_APP.pyw** и нажмите **«Установить/обновить зависимости»**.\n"
    "• После обновления — обновите страницу (Ctrl+F5) и снова проверьте.\n"
)

st.divider()

st.subheader("Быстрые проверки")
if st.button("Запустить self_check.py (лёгкая проверка)"):
    import subprocess

    py = sys.executable
    # try to prefer local venv python
    venv_py = HERE / ".venv" / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
    if venv_py.exists():
        py = str(venv_py)

    try:
        out = subprocess.check_output([py, str(HERE / "self_check.py")], cwd=str(HERE), stderr=subprocess.STDOUT, text=True)
        st.success("self_check.py выполнен")
        st.code(out)
    except Exception as e:
        st.error(f"self_check.py не выполнился: {e!r}")


st.divider()

st.subheader("Логи UI (R09+)")
st.markdown(
    "Если что-то падает/тормозит — приложите `ui_*.log` и `metrics_*.jsonl` из папки логов. "
    "По умолчанию это `pneumo_solver_ui/logs`, но для изолированных прогонов может быть переопределено через `PNEUMO_LOG_DIR`. "
    "В идеале — за текущую сессию Streamlit."
)

log_path = st.session_state.get("log_path")
metrics_path = st.session_state.get("metrics_path")
st.write({"log_path": log_path, "metrics_path": metrics_path})

try:
    logs_dir = Path((os.environ.get("PNEUMO_LOG_DIR") or str(HERE / "logs")).strip())
    if logs_dir.exists():
        files = sorted(logs_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
        st.write("Последние файлы в logs:")
        st.dataframe(
            [
                {
                    "name": f.name,
                    "size_kb": round(f.stat().st_size / 1024.0, 1),
                    "mtime": f.stat().st_mtime,
                }
                for f in files[:25]
            ],
            width="stretch",
            height=240,
        )

        # download current session files (best effort)
        if log_path and Path(log_path).exists():
            st.download_button(
                "Скачать текущий ui.log",
                data=Path(log_path).read_bytes(),
                file_name=Path(log_path).name,
                mime="text/plain",
            )
        if metrics_path and Path(metrics_path).exists():
            st.download_button(
                "Скачать текущий metrics.jsonl",
                data=Path(metrics_path).read_bytes(),
                file_name=Path(metrics_path).name,
                mime="application/json",
            )
    else:
        st.info(f"Папка logs пока не создана: {logs_dir}")
except Exception as e:
    st.warning(f"Не удалось прочитать logs: {e!r}")


st.divider()



st.divider()

st.subheader("События (обязательный лог): ModuleNotFound / Warning / ImportError")
st.caption("Файл генерируется автоматически (хуки bootstrap). Если в UI что-то пишет 'module not found' или появляются предупреждения — это должно появиться здесь.")

events_path = logs_dir / "events.jsonl"
if events_path.exists():
    try:
        # читаем хвост (чтобы не грузить гигабайты)
        raw_lines = events_path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail_lines = raw_lines[-400:]
        events = []
        for ln in tail_lines:
            try:
                events.append(json.loads(ln))
            except Exception:
                continue

        if events:
            all_types = sorted({str(e.get("event", "")) for e in events if e.get("event") is not None})
            if not all_types:
                all_types = ["(unknown)"]
            chosen = st.multiselect("Показывать типы", options=all_types, default=all_types)
            filtered = [e for e in events if str(e.get("event", "")) in set(chosen)]
            st.dataframe(filtered, width="stretch", height=280)

        st.download_button("Скачать events.jsonl", data=events_path.read_bytes(), file_name="events.jsonl", mime="application/json")
    except Exception as e:
        st.warning(f"Не удалось прочитать events.jsonl: {e!r}")
else:
    st.info(f"events.jsonl пока не создан: {events_path}. Открой любую страницу, где были ошибки/предупреждения, и вернись сюда.")


st.subheader("Архив проекта")
try:
    raw_out_dir = str(st.session_state.get("diag_output_dir", "send_bundles") or "").strip()
    if not raw_out_dir:
        diag_out_dir = (REPO_ROOT / "send_bundles").resolve()
    else:
        try:
            _p = Path(raw_out_dir).expanduser()
            diag_out_dir = _p.resolve() if _p.is_absolute() else (REPO_ROOT / raw_out_dir).resolve()
        except Exception:
            diag_out_dir = (REPO_ROOT / raw_out_dir).resolve()

    last_meta = summarize_last_bundle_meta(read_last_meta_from_out_dir(diag_out_dir))
    st.caption(f"Каталог архива проекта: {diag_out_dir}")
    if last_meta.get("zip_name"):
        archive_line = f"Последний архив: **{last_meta.get('zip_name')}**"
        if last_meta.get("zip_size_mb") is not None:
            archive_line += f" ({last_meta.get('zip_size_mb'):.1f} МБ)"
        archive_line += f" — {'готов' if last_meta.get('ok') else 'требует проверки'}"
        st.write(archive_line)
        if last_meta.get("summary_lines"):
            st.markdown("\n".join(f"- {line}" for line in last_meta["summary_lines"]))
        if last_meta.get("anim_pointer_diagnostics_path"):
            st.caption(f"Данные последней анимации: {last_meta['anim_pointer_diagnostics_path']}")
    else:
        st.write("Последний архив: —")
except Exception as e:
    st.warning(f"Не удалось прочитать статус последнего архива проекта: {e!r}")

st.info(
    "Полный архив проекта (включая результаты расчётов, логи, экспорт и отчёты) "
    "собирается в разделе: **98 — Сохранение архива проекта**. "
    "Там же выполняется автоматическое сохранение на диск и (если возможно) копирование архива в буфер обмена."
)

st.write("Здесь оставлены только инструменты просмотра окружения (версии Python, пакеты, переменные среды и т.п.).")
st.divider()
with st.expander("Дополнительно (необязательно)"):
    st.markdown("**Аварийное завершение:** если Streamlit завис и не реагирует.")
    if st.button("Остановить приложение (аварийный выход)"):
        import os
        st.warning("Останавливаю процесс Streamlit...")
        os._exit(0)

# --- Автосохранение UI (лучшее усилие) ---
# Важно: значения, введённые на этой странице, не должны пропадать при refresh/перезапуске.
