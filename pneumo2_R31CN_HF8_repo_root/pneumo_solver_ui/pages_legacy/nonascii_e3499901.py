# ORIGINAL_FILENAME: 99_Диагностика_среды.py
# -*- coding: utf-8 -*-
"""Streamlit page: Diagnostics.

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
from pneumo_solver_ui.streamlit_compat import safe_set_page_config

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


def _try_import(name: str):
    try:
        mod = __import__(name)
        return True, getattr(mod, "__version__", "(no __version__)")
    except Exception as e:
        return False, repr(e)


safe_set_page_config(page_title="Диагностика", layout="wide")

st.title("Диагностика среды")

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
    "Если компоненты не загружаются или появляются ошибки/предупреждения — это нормально для диагностики.\n\n"
    "Главное: **всё должно попадать в логи** и в `events.jsonl`.\n\n"
    "Что делать без консоли:\n"
    "• Откройте эту страницу → нажмите **«Собрать диагностический пакет»** → скачайте zip.\n"
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


st.subheader("Диагностический пакет (zip)")
st.markdown(
    "Кнопка собирает **единый архив для диагностики**, чтобы не нужно было вручную искать/копировать файлы. "
    "Содержимое пакета старается включить всё, что обычно важно: логи, метрики, результаты оптимизации, "
    "снэпшот `st.session_state`, `pip freeze`, вывод `self_check.py` и список файлов проекта."
)


def _safe_bytes(path: Path, max_mb: float = 50.0) -> bytes:
    """Read file with size guard."""
    try:
        if not path.exists() or not path.is_file():
            return b""
        if path.stat().st_size > int(max_mb * 1024 * 1024):
            return (f"SKIPPED (too large >{max_mb}MB): {path.name}\n").encode("utf-8", errors="replace")
        return path.read_bytes()
    except Exception as e:
        return (f"ERROR reading {path}: {e!r}\n").encode("utf-8", errors="replace")


def _session_state_snapshot(max_str: int = 2000) -> dict:
    snap = {}
    for k, v in st.session_state.items():
        try:
            # Simple JSON serializable
            json.dumps(v)
            snap[k] = v
        except Exception:
            s = repr(v)
            if len(s) > max_str:
                s = s[:max_str] + "...<truncated>"
            snap[k] = {"__repr__": s, "__type__": str(type(v))}
    return snap


def _list_files(root: Path, limit: int = 400) -> list:
    rows = []
    try:
        for p in sorted(root.rglob("*"), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True):
            if len(rows) >= limit:
                break
            if p.is_file():
                try:
                    stt = p.stat()
                    rows.append(
                        {
                            "path": str(p.relative_to(root)),
                            "size_bytes": int(stt.st_size),
                            "mtime": float(stt.st_mtime),
                        }
                    )
                except Exception:
                    rows.append({"path": str(p), "error": "stat_failed"})
    except Exception as e:
        rows.append({"error": repr(e)})
    return rows


def _run_subprocess(cmd: list, cwd: Path) -> str:
    """Запуск команды с захватом stdout/stderr.

    Важно: не используем check_call/check_output, чтобы НЕ ловить CalledProcessError
    и всегда сохранять вывод даже при returncode != 0.
    """
    import time
    import subprocess

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
        dt = time.perf_counter() - t0

        parts: list[str] = []
        parts.append(f"$ {' '.join(map(str, cmd))}\n")
        parts.append(f"returncode: {proc.returncode}\n")
        parts.append(f"duration_s: {dt:.3f}\n")
        if proc.stdout:
            parts.append("\n--- STDOUT ---\n")
            parts.append(proc.stdout)
        if proc.stderr:
            parts.append("\n--- STDERR ---\n")
            parts.append(proc.stderr)
        return ''.join(parts)
    except Exception:
        dt = time.perf_counter() - t0
        return (
            f"$ {' '.join(map(str, cmd))}\n"
            f"EXCEPTION after {dt:.3f}s\n\n"
            + traceback.format_exc()
        )
def build_diagnostic_bundle(include_results: bool = True, include_components: bool = True) -> tuple[str, bytes]:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"diagnostics_{ts}.zip"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        # 0) meta
        meta = {
            "timestamp": ts,
            "here": str(HERE),
            "sys.executable": sys.executable,
            "python": sys.version,
            "platform": platform.platform(),
        }
        z.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

        # 1) session state snapshot
        z.writestr("session_state.json", json.dumps(_session_state_snapshot(), ensure_ascii=False, indent=2))

        # 2) pip freeze
        z.writestr("pip_freeze.txt", _run_subprocess([sys.executable, "-m", "pip", "freeze"], HERE))

        # 3) self_check
        z.writestr("self_check.txt", _run_subprocess([sys.executable, str(HERE / "self_check.py")], HERE))

        # 4) logs
        logs_dir = Path((os.environ.get("PNEUMO_LOG_DIR") or str(HERE / "logs")).strip())
        if logs_dir.exists():
            for p in sorted(logs_dir.glob("*")):
                if p.is_file():
                    z.writestr(f"logs/{p.name}", _safe_bytes(p, max_mb=20.0))
        else:
            z.writestr("logs/README.txt", "No logs dir found.\n")

        # 5) current session ui/metrics if известны
        try:
            lp = st.session_state.get("log_path")
            if lp:
                p = Path(lp)
                if p.exists():
                    z.writestr(f"logs/{p.name}", _safe_bytes(p, max_mb=20.0))
        except Exception:
            pass
        try:
            mp = st.session_state.get("metrics_path")
            if mp:
                p = Path(mp)
                if p.exists():
                    z.writestr(f"logs/{p.name}", _safe_bytes(p, max_mb=20.0))
        except Exception:
            pass

        # 6) results (best effort): CSV/progress/pareto/etc in HERE
        if include_results:
            patterns = [
                "results_*.csv",
                "results_*_progress.json",
                "*_progress.json",
                "pareto*.xlsx",
                "pareto*.csv",
                "*_events.csv",
                "*_events.json",
                "*_baseline*.json",
                "*_detail*.json",
            ]
            found = set()
            for pat in patterns:
                for p in HERE.glob(pat):
                    if p.is_file():
                        found.add(p)
            for p in sorted(found):
                z.writestr(f"results/{p.name}", _safe_bytes(p, max_mb=80.0))
        else:
            z.writestr("results/README.txt", "Results were not included (checkbox off).\n")

        # 7) exported JSONs: base/suite/ranges/mapping if есть в session_state
        # We store them exactly as seen by UI.
        for key, out_name in [
            ("base_json_text", "ui/base_json_text.json"),
            ("ranges_json_text", "ui/ranges_json_text.json"),
            ("suite_json_text", "ui/suite_json_text.json"),
            ("svg_mapping_current", "ui/svg_mapping_current.json"),
        ]:
            v = st.session_state.get(key)
            if isinstance(v, str) and v.strip():
                z.writestr(out_name, v)

        # 8) project tree snapshots
        z.writestr("tree_here.json", json.dumps(_list_files(HERE), ensure_ascii=False, indent=2))
        try:
            z.writestr("tree_root.json", json.dumps(_list_files(HERE.parent), ensure_ascii=False, indent=2))
        except Exception:
            pass

        # 9) optional: include component HTML assets (helps debug component load)
        if include_components:
            comp_root = HERE / "components"
            if comp_root.exists():
                for p in comp_root.rglob("*"):
                    if p.is_file() and p.suffix.lower() in {".html", ".js", ".css", ".json"}:
                        rel = p.relative_to(HERE)
                        z.writestr(str(rel).replace("\\", "/"), _safe_bytes(p, max_mb=5.0))

    return fname, buf.getvalue()


include_results = True
include_components = True


if st.button("Собрать диагностический пакет"):
    try:
        fname, data = build_diagnostic_bundle(include_results=include_results, include_components=include_components)
        st.session_state["diag_bundle_name"] = fname
        st.session_state["diag_bundle_bytes"] = data
        st.success(f"Пакет готов: {fname} ({round(len(data)/1024/1024,2)} MB)")
    except Exception as e:
        st.error(f"Не удалось собрать пакет: {e!r}")

if st.session_state.get("diag_bundle_bytes"):
    st.download_button(
        "Скачать диагностический пакет",
        data=st.session_state["diag_bundle_bytes"],
        file_name=st.session_state.get("diag_bundle_name", "diagnostics.zip"),
        mime="application/zip",
    )

st.caption(
    "После скачивания — просто приложите zip в чат. Это заменяет пересылку всей папки проекта и ускоряет диагностику."
)

st.divider()
with st.expander("Дополнительно (необязательно)"):
    st.markdown("**Аварийное завершение:** если Streamlit завис и не реагирует.")
    if st.button("Остановить приложение (аварийный выход)"):
        import os
        st.warning("Останавливаю процесс Streamlit...")
        os._exit(0)
