# -*- coding: utf-8 -*-
"""00_Setup.py — установка и проверка окружения (Streamlit).

Цели:
- показать статус окружения (Python/Streamlit/пакеты/пути)
- дать "одну кнопку" для установки зависимостей без консоли
- не падать из‑за отсутствия необязательных модулей
"""
from __future__ import annotations

import os
import sys
import time
import importlib.util
import subprocess
from pathlib import Path
from typing import List, Tuple

import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled




bootstrap(st)
autosave_if_enabled(st)

try:
    from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
    _ui_bootstrap(st)
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
REQ_FILE = REPO_ROOT / "requirements.txt"
LOG_DIR = REPO_ROOT / "pneumo_solver_ui" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
INSTALL_LOG = LOG_DIR / "deps_install.log"
DEPS_MISSING_LOG = LOG_DIR / "deps_missing.log"


# Пакеты, которые чаще всего "пропадают" и ломают отдельные страницы.
# (core+extras — всё равно ставится из requirements.txt, но здесь — быстрый чек)
MODULES_TO_CHECK: List[Tuple[str, str]] = [
    ("streamlit", "Web‑интерфейс"),
    ("numpy", "Численные расчёты"),
    ("pandas", "Таблицы и CSV"),
    ("scipy", "Интегрирование/оптимизация"),
    ("plotly", "Интерактивные графики"),
    ("matplotlib", "Графики (fallback)"),
    ("psutil", "Метрики CPU/RAM"),
    ("duckdb", "База экспериментов"),
    ("dask", "Распределённые вычисления"),
    ("distributed", "Dask scheduler"),
    ("torch", "MOBO (опционально)"),
    ("botorch", "MOBO (опционально)"),
    ("gpytorch", "MOBO (опционально)"),
    ("sklearn", "Аналитика (опц.)"),
    ("PySide6", "Десктоп‑аниматор (опц.)"),
    ("OpenGL_accelerate", "Ускорение OpenGL (Desktop Animator)"),
    ("cloudpickle", "Кэш/сериализация"),
]


def _spec_exists(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _run_pip_install(requirements_path: Path) -> int:
    """Run pip install -r <requirements> and stream output to log + UI.

    Требования пользователя:
    - видимый прогресс (чтобы было понятно, что процесс идёт)
    - никакой консоли
    - весь stdout/stderr сохраняем в deps_install.log
    """
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--progress-bar",
        "off",
        "-r",
        str(requirements_path),
    ]
    st.write("Команда:", " ".join(cmd))

    progress = st.progress(0.0)
    status = st.empty()
    placeholder = st.empty()
    lines: List[str] = []

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PIP_NO_COLOR"] = "1"

    t0 = time.time()
    status.info("⏳ Установка зависимостей запущена… (pip install)")
    progress.progress(0.05)

    with open(INSTALL_LOG, "a", encoding="utf-8") as lf:
        lf.write(f"\n=== pip install started: {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        lf.write(" ".join(cmd) + "\n")

        p = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        assert p.stdout is not None

        # В Streamlit нет "настоящего" индикатора прогресса pip,
        # поэтому показываем:
        # - бегущий хвост лога
        # - таймер
        # - "псевдо‑прогресс" (0.05..0.95) по числу полученных строк.
        for line in p.stdout:
            line = line.rstrip("\n")
            lines.append(line)
            lf.write(line + "\n")

            # UI: последние ~80 строк
            tail = "\n".join(lines[-80:])
            placeholder.code(tail)

            # UI: обновление статуса/прогресса
            dt = time.time() - t0
            status.info(f"⏳ pip install работает… прошло {dt:0.1f}s, строк: {len(lines)}")
            pseudo = 0.05 + min(0.90, (len(lines) / 250.0) * 0.90)
            progress.progress(float(pseudo))

        rc = p.wait()
        lf.write(f"=== pip install finished rc={rc} ===\n")

    progress.progress(1.0)
    if rc == 0:
        status.success("✅ Зависимости установлены. Рекомендуется перезапустить приложение (F5 / Rerun).")
    else:
        status.error(f"❌ pip install завершился с rc={rc}. Открой deps_install.log для подробностей.")
    return int(rc)


def main() -> None:

    st.title("Установка и проверка окружения")

    st.caption("Эта страница нужна, чтобы без консоли проверить окружение и поставить зависимости одной кнопкой.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Окружение")
        st.write("Python:", sys.version)
        st.write("Executable:", sys.executable)
        st.write("Repo root:", str(REPO_ROOT))
        st.write("Streamlit server:", os.environ.get("STREAMLIT_SERVER_PORT", "—"))
    with col2:
        st.subheader("Файлы")
        st.write("requirements.txt:", str(REQ_FILE), "✅" if REQ_FILE.exists() else "❌")
        st.write("install log:", str(INSTALL_LOG))
        if INSTALL_LOG.exists():
            st.download_button("Скачать deps_install.log", data=INSTALL_LOG.read_bytes(), file_name="deps_install.log")

    st.divider()

    st.subheader("Проверка модулей (importlib.find_spec)")
    rows = []
    missing = []
    for mod, purpose in MODULES_TO_CHECK:
        ok = _spec_exists(mod)
        rows.append({"module": mod, "ok": ok, "purpose": purpose})
        if not ok:
            missing.append(mod)

    st.dataframe(rows, width="stretch", hide_index=True)


    if missing:
        try:
            with open(DEPS_MISSING_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] missing modules: {', '.join(missing)}\n")
        except Exception:
            pass
    if missing:
        # mandatory event in logs (for Diagnostics page)
        try:
            from pneumo_solver_ui.diag.eventlog import get_global_logger
            get_global_logger(REPO_ROOT).emit("DepsMissing", "missing modules detected by Setup page", missing=missing)
        except Exception:
            pass
        st.error("Не найдены модули: " + ", ".join(missing))
    else:
        st.success("Все ключевые модули найдены.")

    st.divider()

    st.subheader("Установка зависимостей (без консоли)")

    if not REQ_FILE.exists():
        st.error("requirements.txt не найден — установка невозможна.")
        return

    st.info("Нажмите кнопку. Установка идёт в текущий Python/venv (sys.executable). После установки перезапустите приложение.")

    if st.button("Установить/обновить зависимости из requirements.txt", width="stretch"):
        rc = _run_pip_install(REQ_FILE)
        if rc == 0:
            st.success("Установка завершена успешно. Перезапустите приложение.")
        else:
            st.error(f"Установка завершилась с ошибкой rc={rc}. Смотрите deps_install.log.")

    st.caption("Примечание: чтобы убрать предупреждения Streamlit про `use_container_width`, код UI уже переведён на `width='stretch'` согласно документации Streamlit.")

    st.divider()
    st.subheader("Самопроверки UI/GUI")
    st.caption("Автоматические проверки, которые помогают ловить ошибки интеграции и генераторов (без запуска симуляции).")

    if st.button("Запустить ui_selfcheck", width="stretch"):
        try:
            from pneumo_solver_ui.ui_selfcheck import run_ui_selfcheck

            rep = run_ui_selfcheck(REPO_ROOT)
            if rep.get("ok"):
                st.success("✅ ui_selfcheck: OK")
            else:
                st.error("❌ ui_selfcheck: есть проблемы")
            st.json(rep, expanded=False)
        except Exception as e:
            st.error("Не удалось выполнить ui_selfcheck")
            st.exception(e)

if __name__ == "__main__":
    main()

# --- Автосохранение UI (лучшее усилие) ---
# Важно: значения, введённые на этой странице, не должны пропадать при refresh/перезапуске.
