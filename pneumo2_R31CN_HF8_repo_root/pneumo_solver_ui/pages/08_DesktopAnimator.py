# -*- coding: utf-8 -*-
"""Streamlit page: Desktop Animator launcher.

Цель страницы:
- Запуск Desktop Animator (PySide6) одним кликом из Web UI.
- Рекомендованный режим: --follow, который автоматически подхватывает
  workspace/exports/anim_latest.json.

Подготовка данных:
- В Simulator -> Детальный прогон включите:
    ✅ Auto‑экспорт anim_latest (Desktop Animator)
  Тогда после расчёта будет создано:
    pneumo_solver_ui/workspace/exports/anim_latest.npz
    pneumo_solver_ui/workspace/exports/anim_latest.json

"""

from __future__ import annotations

import json
import importlib.util
import os
import subprocess
import sys
import platform
from pathlib import Path

import streamlit as st
from pneumo_solver_ui.run_artifacts import local_anim_latest_export_paths
from pneumo_solver_ui.tools.send_bundle_contract import extract_anim_snapshot
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled



bootstrap(st)
autosave_if_enabled(st)

try:
    from pneumo_solver_ui.ui_bootstrap import bootstrap as _ui_bootstrap
    _ui_bootstrap(st)
except Exception:
    pass


st.title("🖥 Десктоп‑аниматор (PySide6)")
st.caption(
    "Отдельное окно с информативной анимацией (multi-view + HUD + давления/клапаны/потоки/heatmap). "
    "Запускается локально (Windows) и может работать в follow-режиме, автоматически подхватывая последнюю выгрузку из UI."
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORTS_DIR = PROJECT_ROOT / "pneumo_solver_ui" / "workspace" / "exports"
_, POINTER_PATH = local_anim_latest_export_paths(EXPORTS_DIR, ensure_exists=False)

# --- helpers ---

def _venv_python(prefer_gui: bool) -> str:
    """Try to find venv python/pythonw inside project; fallback to sys.executable."""
    candidates = []
    if platform.system() == "Windows":
        candidates += [
            PROJECT_ROOT / ".venv" / "Scripts" / ("pythonw.exe" if prefer_gui else "python.exe"),
            PROJECT_ROOT / "venv" / "Scripts" / ("pythonw.exe" if prefer_gui else "python.exe"),
        ]
    else:
        candidates += [
            PROJECT_ROOT / ".venv" / "bin" / "python",
            PROJECT_ROOT / "venv" / "bin" / "python",
        ]

    for c in candidates:
        if c.exists():
            return str(c)

    # sys.executable may be good enough (streamlit runs inside venv)
    return sys.executable


def _open_folder(path: Path) -> None:
    try:
        if platform.system() == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        st.warning(f"Не удалось открыть папку: {e}")



def _spawn_no_console(cmd: list[str], cwd: Path) -> subprocess.Popen:
    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
    return subprocess.Popen(cmd, cwd=str(cwd), creationflags=creationflags, startupinfo=startupinfo)


def _pip_install_stream(packages: list[str], label: str = "Установка") -> tuple[int, str]:
    """Run pip install and stream output into the Streamlit page.

    Требования:
    - без консоли
    - понятный прогресс (хотя бы: таймер/строки/лог)
    """
    py = _venv_python(prefer_gui=False)
    cmd = [py, "-m", "pip", "install", *packages]

    out_lines: list[str] = []
    placeholder = st.empty()
    status = st.empty()
    progress = st.progress(0.0)

    st.info(f"{label}: {' '.join(packages)}")

    t0 = __import__('time').time()
    progress.progress(0.05)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        progress.progress(1.0)
        return 1, f"Не удалось запустить pip: {e}"

    assert proc.stdout is not None
    for line in proc.stdout:
        out_lines.append(line)
        # keep last N lines to avoid huge UI
        if len(out_lines) > 350:
            out_lines = out_lines[-350:]
        placeholder.code(''.join(out_lines))

        dt = __import__('time').time() - t0
        status.info(f"⏳ pip install работает… прошло {dt:0.1f}s, строк: {len(out_lines)}")
        # pseudo progress: 0.05..0.95
        pseudo = 0.05 + min(0.90, (len(out_lines) / 250.0) * 0.90)
        progress.progress(float(pseudo))

    rc = proc.wait()
    progress.progress(1.0)
    if rc == 0:
        status.success("✅ Установка завершена")
    else:
        status.error(f"❌ pip install завершился с rc={rc}")

    return int(rc), ''.join(out_lines)

# --- UI ---

EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

col1, col2, col3 = st.columns([1.2, 1.2, 1.6])
with col1:
    theme = st.selectbox("Тема", ["dark", "light"], index=0)
with col2:
    no_gl = st.checkbox("--no-gl (совместимость)", value=False, help="Отключает QOpenGL (на старых GPU/драйверах полезно).")
with col3:
    st.caption("Где лежит anim_latest pointer")
    st.code(str(POINTER_PATH))

# pointer preview
st.subheader("Состояние anim_latest")

if POINTER_PATH.exists():
    try:
        raw_obj = json.loads(POINTER_PATH.read_text(encoding="utf-8"))
        obj = extract_anim_snapshot(raw_obj, source="desktop_animator_page") or raw_obj
        npz_rel = obj.get("npz_path")
        npz_path = (POINTER_PATH.parent / npz_rel).resolve() if isinstance(npz_rel, str) else None
        st.success("Pointer найден")
        st.write({
            "updated_utc": obj.get("updated_utc"),
            "npz_path": str(npz_path) if npz_path else npz_rel,
            "visual_cache_token": obj.get("visual_cache_token", ""),
            "visual_reload_inputs": obj.get("visual_reload_inputs", []),
            "meta": obj.get("meta", {}),
        })
        with st.expander("Показать pointer visual diagnostics", expanded=False):
            st.json(obj.get("visual_cache_dependencies", {}))
        if npz_path and Path(npz_path).exists():
            st.caption(f"NPZ размер: {Path(npz_path).stat().st_size / 1024.0 / 1024.0:.2f} MB")
        else:
            st.warning("NPZ из pointer не найден. Запустите детальный прогон с авто‑экспортом или нажмите экспорт вручную в Simulator.")
    except Exception as e:
        st.warning(f"Pointer есть, но не читается как JSON: {e}")
else:
    st.info(
        "Pointer ещё не создан. Перейдите в Simulator → Детальный прогон и включите **Авто‑экспорт anim_latest**, "
        "затем выполните детальный прогон (или нажмите экспорт вручную в блоке Desktop Animator внутри детального просмотра)."
    )



# --- dependency check / one-click install ---
st.subheader("Зависимости Desktop Animator")

# Проверяем: PySide6 (Qt), pyqtgraph (2D) и pyqtgraph.opengl (3D/OpenGL)
try:
    import PySide6  # noqa: F401
    has_pyside6 = True
except Exception:
    has_pyside6 = False

try:
    import pyqtgraph  # noqa: F401
    has_pyqtgraph = True
except Exception:
    has_pyqtgraph = False

try:
    import pyqtgraph.opengl  # noqa: F401
    has_gl = True
except Exception:
    has_gl = False

has_gl_accel = importlib.util.find_spec("OpenGL_accelerate") is not None

# Короткий статус
rows = [
    {"module": "PySide6", "ok": has_pyside6, "note": "Qt (окно Animator)"},
    {"module": "pyqtgraph", "ok": has_pyqtgraph, "note": "2D графики в Animator"},
    {"module": "pyqtgraph.opengl", "ok": has_gl, "note": "3D (OpenGL). Требует PyOpenGL"},
    {"module": "OpenGL_accelerate", "ok": has_gl_accel, "note": "Ускорение PyOpenGL на Windows (сильно влияет на 3D FPS)"},
]
st.dataframe(rows, width="stretch", hide_index=True)

need = []
if not has_pyside6:
    need.append("PySide6")
if not has_pyqtgraph:
    need.append("pyqtgraph")
# Если нет OpenGL-части — почти всегда не хватает PyOpenGL.
if not has_gl:
    need.append("PyOpenGL")
if platform.system() == "Windows" and not has_gl_accel:
    need.append("PyOpenGL_accelerate")

if has_gl and not has_gl_accel:
    st.warning("OpenGL работает, но пакет OpenGL_accelerate не установлен. 3D Animator будет работать, но заметно медленнее на Windows.")

# Установка одной кнопкой (без консоли)
if need:
    # de-dup preserving order
    seen = set(); need2 = []
    for x in need:
        if x not in seen:
            need2.append(x); seen.add(x)

    st.warning(
        "Не хватает зависимостей для Desktop Animator. Нажмите кнопку — установка пройдёт автоматически (без консоли).\n\n"
        "Если 3D/OpenGL всё равно не заработает (драйвер/Remote Desktop), используйте режим совместимости **--no-gl**.\n\nНа Windows для нормальной скорости нужен и **PyOpenGL_accelerate**."
    )

    if st.button(f"Установить: {', '.join(need2)}", width="stretch"):
        rc, out = _pip_install_stream(need2, label="Установка Desktop Animator")
        if rc == 0:
            st.success("Готово. Перезапустите страницу (или нажмите Rerun).")
            st.rerun()
        else:
            st.error("Не удалось установить зависимости. Логи показаны выше.")
else:
    if has_gl_accel or platform.system() != "Windows":
        st.success("✅ Все зависимости Desktop Animator найдены.")
    else:
        st.info("Qt/OpenGL найдены, но для ускорения 3D рекомендуется установить PyOpenGL_accelerate.")

st.divider()

cA, cB, cC = st.columns([1, 1, 1])
with cA:
    if st.button("Запустить Desktop Animator (follow)"):
        py = _venv_python(prefer_gui=True)
        cmd = [py, "-m", "pneumo_solver_ui.desktop_animator.main", "--follow", "--pointer", str(POINTER_PATH), "--theme", str(theme)]
        if no_gl:
            cmd.append("--no-gl")
        try:
            _spawn_no_console(cmd, cwd=PROJECT_ROOT)
            st.success("Запущено (если система позволяет GUI).")
        except Exception as e:
            st.error(f"Не удалось запустить: {e}")

with cB:
    if st.button("Открыть папку exports"):
        _open_folder(EXPORTS_DIR)

with cC:
    st.caption("Подсказка")
    st.write(
        "Если Animator открыт в follow-режиме, то после каждого детального прогона он автоматически обновится "
        "на новую симуляцию (anim_latest).*"
    )

st.divider()

st.subheader("Запуск без follow")
st.caption("Если хотите открыть конкретный NPZ файл — можно запустить Animator и выбрать файл через кнопку Open (в самом Animator).")
if st.button("Запустить Desktop Animator (пустой)"):
    py = _venv_python(prefer_gui=True)
    cmd = [py, "-m", "pneumo_solver_ui.desktop_animator.main", "--theme", str(theme)]
    if no_gl:
        cmd.append("--no-gl")
    try:
        _spawn_no_console(cmd, cwd=PROJECT_ROOT)
        st.success("Запущено")
    except Exception as e:
        st.error(f"Не удалось запустить: {e}")

# --- Автосохранение UI (лучшее усилие) ---
# Важно: значения, введённые на этой странице, не должны пропадать при refresh/перезапуске.
