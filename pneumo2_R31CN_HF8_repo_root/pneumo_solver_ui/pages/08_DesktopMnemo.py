# -*- coding: utf-8 -*-
"""Streamlit page: Desktop Mnemo launcher.

Отдельное Windows-окно для инженерной мнемосхемы:
- анимированная пневмосхема в отдельном desktop UI;
- follow-режим по anim_latest.json;
- быстрый доступ к обзору, выбору узла/линии и трендам.
"""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import streamlit as st

from pneumo_solver_ui.desktop_mnemo.settings_bridge import (
    desktop_mnemo_view_mode_label,
    read_desktop_mnemo_view_mode,
)
from pneumo_solver_ui.run_artifacts import (
    collect_anim_latest_diagnostics_summary,
    local_anim_latest_export_paths,
)
from pneumo_solver_ui.tools.send_bundle_contract import (
    build_anim_operator_recommendations,
    extract_anim_snapshot,
)
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled


bootstrap(st)
autosave_if_enabled(st)


st.title("🫁 Desktop Mnemo (PySide6)")
st.caption(
    "Отдельное HMI-окно с анимированной мнемосхемой пневматики: понятная топология, "
    "выделение критичных узлов, быстрые тренды и follow-режим для работы рядом с расчётным UI."
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORTS_DIR = PROJECT_ROOT / "pneumo_solver_ui" / "workspace" / "exports"
_, POINTER_PATH = local_anim_latest_export_paths(EXPORTS_DIR, ensure_exists=False)
persisted_view_mode = read_desktop_mnemo_view_mode(PROJECT_ROOT)
persisted_view_mode_label = desktop_mnemo_view_mode_label(persisted_view_mode)


def _venv_python(prefer_gui: bool) -> str:
    candidates: list[Path] = []
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

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _open_folder(path: Path) -> None:
    try:
        if platform.system() == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as exc:
        st.warning(f"Не удалось открыть папку: {exc}")


def _spawn_no_console(cmd: list[str], cwd: Path) -> subprocess.Popen:
    creationflags = 0
    startupinfo = None
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
    return subprocess.Popen(cmd, cwd=str(cwd), creationflags=creationflags, startupinfo=startupinfo)


def _pip_install_stream(packages: list[str], label: str) -> tuple[int, str]:
    py = _venv_python(prefer_gui=False)
    cmd = [py, "-m", "pip", "install", *packages]

    out_lines: list[str] = []
    placeholder = st.empty()
    status = st.empty()
    progress = st.progress(0.0)
    st.info(f"{label}: {' '.join(packages)}")

    t0 = __import__("time").time()
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
    except Exception as exc:
        progress.progress(1.0)
        return 1, f"Не удалось запустить pip: {exc}"

    assert proc.stdout is not None
    for line in proc.stdout:
        out_lines.append(line)
        if len(out_lines) > 350:
            out_lines = out_lines[-350:]
        placeholder.code("".join(out_lines))
        dt = __import__("time").time() - t0
        status.info(f"⏳ pip install работает… прошло {dt:0.1f}s, строк: {len(out_lines)}")
        pseudo = 0.05 + min(0.90, (len(out_lines) / 250.0) * 0.90)
        progress.progress(float(pseudo))

    rc = int(proc.wait())
    progress.progress(1.0)
    if rc == 0:
        status.success("✅ Установка завершена")
    else:
        status.error(f"❌ pip install завершился с rc={rc}")
    return rc, "".join(out_lines)


def _launch_mnemo(
    *,
    theme: str,
    follow: bool = False,
    npz_path: Path | None = None,
    startup_preset: str = "",
    startup_title: str = "",
    startup_reason: str = "",
    startup_view_mode: str = "",
    startup_checks: list[str] | None = None,
) -> tuple[bool, str]:
    py = _venv_python(prefer_gui=True)
    cmd = [py, "-m", "pneumo_solver_ui.desktop_mnemo.main"]
    if follow:
        cmd += ["--follow", "--pointer", str(POINTER_PATH)]
    elif npz_path is not None:
        cmd += ["--npz", str(npz_path)]
    cmd += ["--theme", str(theme)]
    if startup_preset:
        cmd += ["--startup-preset", str(startup_preset)]
    if startup_title:
        cmd += ["--startup-title", str(startup_title)]
    if startup_reason:
        cmd += ["--startup-reason", str(startup_reason)]
    if startup_view_mode:
        cmd += ["--startup-view-mode", str(startup_view_mode)]
    for item in startup_checks or []:
        text = str(item).strip()
        if text:
            cmd += ["--startup-check", text]
    try:
        _spawn_no_console(cmd, cwd=PROJECT_ROOT)
    except Exception as exc:
        return False, f"Не удалось запустить: {exc}"
    if follow:
        return True, "Desktop Mnemo запущен в follow-режиме."
    if npz_path is not None:
        return True, "Desktop Mnemo открыт на текущем NPZ."
    return True, "Desktop Mnemo открыт."


EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

col1, col2 = st.columns([1.2, 1.8])
with col1:
    theme = st.selectbox("Тема", ["dark", "light"], index=0)
with col2:
    st.caption("Где лежит anim_latest pointer")
    st.code(str(POINTER_PATH))

st.info(
    "Режим открытия отдельного окна по умолчанию: "
    f"{persisted_view_mode_label}. Это значение берётся из последней сохранённой desktop-сессии `Desktop Mnemo`."
)
launch_view_choice = st.radio(
    "Разовый режим запуска окна",
    ["Как сохранено", "Фокусный сценарий", "Полная схема"],
    index=0,
    horizontal=True,
    help="Это одноразовое переопределение для текущего запуска. Сохранённый режим по умолчанию не меняется.",
)
launch_view_mode = {
    "Как сохранено": "",
    "Фокусный сценарий": "focus",
    "Полная схема": "overview",
}[str(launch_view_choice)]
launch_view_label = desktop_mnemo_view_mode_label(launch_view_mode or persisted_view_mode)
if launch_view_mode:
    st.caption(
        "Этот запуск откроет окно в режиме: "
        f"{launch_view_label}. Сохранённый default останется: {persisted_view_mode_label}."
    )
else:
    st.caption(f"Для этого запуска будет использован сохранённый режим: {persisted_view_mode_label}.")

st.subheader("Зачем это окно")
st.write(
    "Desktop Mnemo рассчитан на инженерную работу с вторым монитором: схема остаётся перед глазами, "
    "выделение линий и узлов синхронизировано, а тренды помогают быстро проверить, где именно меняется режим."
)

st.subheader("Состояние anim_latest")
pointer_npz_path: Path | None = None
pointer_obj: dict[str, object] | None = None

if POINTER_PATH.exists():
    try:
        raw_obj = json.loads(POINTER_PATH.read_text(encoding="utf-8"))
        pointer_obj = extract_anim_snapshot(raw_obj, source="desktop_mnemo_page") or raw_obj
        pointer_dict = pointer_obj if isinstance(pointer_obj, dict) else {}
        npz_rel = pointer_dict.get("npz_path")
        pointer_npz_path = (POINTER_PATH.parent / npz_rel).resolve() if isinstance(npz_rel, str) else None
        st.success("Pointer найден")
        st.write(
            {
                "updated_utc": pointer_dict.get("updated_utc"),
                "npz_path": str(pointer_npz_path) if pointer_npz_path else npz_rel,
                "visual_cache_token": pointer_dict.get("visual_cache_token", ""),
                "visual_reload_inputs": pointer_dict.get("visual_reload_inputs", []),
                "meta": pointer_dict.get("meta", {}),
            }
        )
        with st.expander("Показать pointer visual diagnostics", expanded=False):
            st.json(pointer_dict.get("visual_cache_dependencies", {}))
        if pointer_npz_path and pointer_npz_path.exists():
            st.caption(f"NPZ размер: {pointer_npz_path.stat().st_size / 1024.0 / 1024.0:.2f} MB")
        else:
            st.warning("NPZ из pointer не найден. Сначала выполните детальный прогон с auto-export anim_latest.")
    except Exception as exc:
        st.warning(f"Pointer есть, но не читается как JSON: {exc}")
else:
    st.info(
        "Pointer ещё не создан. Перейдите в Simulator → Детальный прогон, включите auto-export anim_latest "
        "и выполните прогон. После этого Desktop Mnemo сможет автоматически подхватывать свежие данные."
    )

launcher_diag = collect_anim_latest_diagnostics_summary(
    {"pointer_json": str(POINTER_PATH)} if POINTER_PATH.exists() else None,
    include_meta=False,
)
operator_recommendations = build_anim_operator_recommendations(launcher_diag)
if operator_recommendations:
    st.subheader("Рекомендуемые действия перед запуском")
    rec_col1, rec_col2, rec_col3, rec_col4, rec_col5 = st.columns(5)
    rec_col1.metric("Режим", str(launcher_diag.get("anim_latest_mnemo_event_log_current_mode") or "—"))
    rec_col2.metric("Active latch", int(launcher_diag.get("anim_latest_mnemo_event_log_active_latch_count") or 0))
    rec_col3.metric("Perf evidence", str(launcher_diag.get("browser_perf_evidence_status") or "—"))
    rec_col4.metric("Perf compare", str(launcher_diag.get("browser_perf_comparison_status") or "—"))
    rec_col5.metric("Desktop view", persisted_view_mode_label)
    st.warning("Сначала: " + operator_recommendations[0])
    st.markdown("\n".join(f"{idx}. {item}" for idx, item in enumerate(operator_recommendations, start=1)))
else:
    st.caption(f"Desktop Mnemo сейчас будет открываться в режиме: {persisted_view_mode_label}.")


st.subheader("Зависимости Desktop Mnemo")

try:
    import PySide6  # noqa: F401

    has_pyside6 = True
except Exception:
    has_pyside6 = False

has_webengine = bool(has_pyside6 and importlib.util.find_spec("PySide6.QtWebEngineWidgets") is not None)
has_webchannel = bool(has_pyside6 and importlib.util.find_spec("PySide6.QtWebChannel") is not None)

try:
    import pyqtgraph  # noqa: F401

    has_pyqtgraph = True
except Exception:
    has_pyqtgraph = False

rows = [
    {"module": "PySide6", "ok": has_pyside6, "note": "Qt окно и docking UI"},
    {"module": "PySide6.QtWebEngineWidgets", "ok": has_webengine, "note": "рендер анимированной мнемосхемы"},
    {"module": "PySide6.QtWebChannel", "ok": has_webchannel, "note": "мост между Qt и HTML мнемосхемой"},
    {"module": "pyqtgraph", "ok": has_pyqtgraph, "note": "тренды и быстрые инженерные графики"},
]
st.dataframe(rows, width="stretch", hide_index=True)

need: list[str] = []
if not has_pyside6 or not has_webengine or not has_webchannel:
    need.append("PySide6")
if not has_pyqtgraph:
    need.append("pyqtgraph")

if need:
    deduped = list(dict.fromkeys(need))
    st.warning(
        "Не хватает зависимостей для Desktop Mnemo. Обычно достаточно установить PySide6 и pyqtgraph. "
        "После установки страница сама перезапустится."
    )
    if st.button(f"Установить: {', '.join(deduped)}", width="stretch"):
        rc, _out = _pip_install_stream(deduped, label="Установка Desktop Mnemo")
        if rc == 0:
            st.success("Готово. Перезапускаю страницу.")
            st.rerun()
        else:
            st.error("Не удалось установить зависимости. Логи показаны выше.")
else:
    st.success("✅ Все зависимости Desktop Mnemo найдены.")

st.divider()

st.subheader("Сценарный запуск")
mnemo_active_latch_count = int(launcher_diag.get("anim_latest_mnemo_event_log_active_latch_count") or 0)
mnemo_preset_label = "Запустить preset: пустое окно"
mnemo_preset_title = "Пустой инженерный старт"
mnemo_preset_reason = (
    "Свежий anim_latest ещё не готов, поэтому launcher предлагает нейтральный пустой старт без привязки к pointer."
)
mnemo_preset_key = "blank_start"
mnemo_preset_checks = [
    "Сначала подключите pointer или конкретный NPZ, чтобы схема получила живой сценарий.",
    "После загрузки ищите одну ведущую ветку, а не пытайтесь читать всю схему сразу.",
    "Тренды и события используйте как подтверждение гипотезы, а не как первый экран.",
]
mnemo_preset_follow = False
mnemo_preset_npz: Path | None = None

if mnemo_active_latch_count > 0 and POINTER_PATH.exists():
    mnemo_preset_label = "Запустить preset: оперативный follow-разбор"
    mnemo_preset_title = "Оперативный follow-разбор"
    mnemo_preset_reason = (
        "Есть активные latch-события: follow-режим лучше подходит для живого triage, ACK/reset и наблюдения за новым anim_latest."
    )
    mnemo_preset_key = "operational_follow_triage"
    mnemo_preset_checks = [
        "Сначала подтвердите ведущую ветку и активный latch на текущем кадре.",
        "ACK делайте только после того, как схема и тренды согласованы между собой.",
        "После ACK смотрите, не появляется ли новый latch уже на следующем обновлении pointer.",
    ]
    mnemo_preset_follow = True
elif pointer_npz_path and pointer_npz_path.exists():
    mnemo_preset_label = "Запустить preset: ретроспектива по текущему NPZ"
    mnemo_preset_title = "Ретроспективный разбор текущего NPZ"
    mnemo_preset_reason = (
        "Критичных latch сейчас нет: удобнее открыть фиксированный NPZ и спокойно разобрать сценарий без скачков на новый pointer."
    )
    mnemo_preset_key = "npz_retrospective_review"
    mnemo_preset_checks = [
        "Держите в голове один фиксированный сценарий и не ждите live-переключения pointer.",
        "Сначала выделите ведущую ветку, затем один опорный узел давления.",
        "Только после этого проверяйте численную гипотезу через тренды и event memory.",
    ]
    mnemo_preset_npz = pointer_npz_path
elif POINTER_PATH.exists():
    mnemo_preset_label = "Запустить preset: baseline follow"
    mnemo_preset_title = "Baseline follow"
    mnemo_preset_reason = (
        "Pointer уже готов, но отдельного повода для frozen-ретроспективы нет: безопасный базовый режим — follow."
    )
    mnemo_preset_key = "baseline_follow"
    mnemo_preset_checks = [
        "Сначала поймите текущий режим на схеме, только потом углубляйтесь в детали.",
        "Если pointer обновится, сравнивайте новый режим с предыдущим, а не начинайте чтение заново.",
        "Для спокойных кадров держите в фокусе ведущую ветку и один максимум давления.",
    ]
    mnemo_preset_follow = True

st.info(mnemo_preset_reason)
if st.button(mnemo_preset_label, width="stretch"):
    ok, msg = _launch_mnemo(
        theme=str(theme),
        follow=mnemo_preset_follow,
        npz_path=mnemo_preset_npz,
        startup_preset=mnemo_preset_key,
        startup_title=mnemo_preset_title,
        startup_reason=mnemo_preset_reason,
        startup_view_mode=launch_view_mode,
        startup_checks=mnemo_preset_checks,
    )
    if ok:
        st.success(msg)
    else:
        st.error(msg)

st.divider()

launch_col1, launch_col2, launch_col3 = st.columns([1.2, 1.2, 1.0])
with launch_col1:
    if st.button("Запустить Desktop Mnemo (follow)", width="stretch"):
        ok, msg = _launch_mnemo(theme=str(theme), follow=True, startup_view_mode=launch_view_mode)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

with launch_col2:
    disabled_npz = not bool(pointer_npz_path and pointer_npz_path.exists())
    if st.button("Запустить по текущему NPZ", width="stretch", disabled=disabled_npz):
        assert pointer_npz_path is not None
        ok, msg = _launch_mnemo(theme=str(theme), npz_path=pointer_npz_path, startup_view_mode=launch_view_mode)
        if ok:
            st.success(msg)
        else:
            st.error(msg)

with launch_col3:
    if st.button("Открыть exports", width="stretch"):
        _open_folder(EXPORTS_DIR)

st.caption(
    "Follow-режим удобен для длительной работы: после нового детального прогона окно само переключится на свежий bundle, "
    "а режим запуска по NPZ полезен для ретроспективного разбора конкретного сценария."
)

st.divider()

if st.button("Запустить Desktop Mnemo (пустой)", width="stretch"):
    ok, msg = _launch_mnemo(theme=str(theme), startup_view_mode=launch_view_mode)
    if ok:
        st.success(msg)
    else:
        st.error(msg)
