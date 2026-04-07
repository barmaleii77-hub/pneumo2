# ORIGINAL_FILENAME: 02_Калибровка_NPZ.py
# -*- coding: utf-8 -*-
"""02_Calibration_NPZ.py

Страница Streamlit для запуска калибровочных пайплайнов из папки ./calibration.

Заметки:
- Мы НЕ дублируем логику пайплайнов в UI. UI лишь собирает аргументы и
  запускает скрипты через subprocess.
- Такой подход проще поддерживать: все алгоритмические изменения остаются
  внутри calibration/*.py.

Ожидаемый запуск:
    python -m streamlit run pneumo_ui_app.py

Streamlit автоматически подхватит папку pages/.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

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

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "calibration"


def _ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save_uploaded_files(files: List[Any], dst_dir: Path) -> List[Path]:
    """Сохраняет загруженные в Streamlit файлы на диск.

    Возвращает список сохранённых путей.
    """
    out: List[Path] = []
    _ensure_dir(dst_dir)
    for f in files:
        # f.name может содержать пути (редко). Берём только basename.
        name = Path(str(getattr(f, "name", "uploaded.bin"))).name
        p = dst_dir / name
        try:
            p.write_bytes(f.getbuffer())
        except Exception:
            p.write_bytes(bytes(f.read()))
        out.append(p)
    return out


def _extract_zip(upload: Any, dst_dir: Path) -> List[Path]:
    """Распаковывает ZIP (из file_uploader) в dst_dir и возвращает список файлов."""
    _ensure_dir(dst_dir)
    zpath = dst_dir / Path(str(getattr(upload, "name", "upload.zip"))).name
    try:
        zpath.write_bytes(upload.getbuffer())
    except Exception:
        zpath.write_bytes(bytes(upload.read()))
    files: List[Path] = []
    with zipfile.ZipFile(zpath, "r") as z:
        z.extractall(dst_dir)
        for n in z.namelist():
            p = (dst_dir / n).resolve()
            if p.is_file():
                files.append(p)
    return files


def _scan_osc_dir(osc_dir: Path) -> Tuple[List[Path], List[Path], bool]:
    """Ищет в osc_dir файлы NPZ/CSV и signals.csv."""
    npz = sorted(osc_dir.glob("T*_osc.npz"))
    csv = sorted(osc_dir.glob("*.csv"))
    has_signals = (osc_dir / "signals.csv").exists()
    return npz, csv, bool(has_signals)


@dataclass
class RunResult:
    cmd: List[str]
    returncode: int
    stdout: str
    stderr: str


def _quote_cmd(cmd: List[str]) -> str:
    return " ".join(shlex.quote(c) for c in cmd)


def _run_cmd(cmd: List[str], cwd: Path) -> RunResult:
    """Запуск команды с захватом stdout/stderr."""
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return RunResult(cmd=cmd, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)


def _path_default(p: Path) -> str:
    try:
        return str(p) if p.exists() else ""
    except Exception:
        return ""


def _list_calibration_runs() -> List[Path]:
    """Список папок RUN_*.

    Исторически в проекте встречались два расположения:
    - ROOT/calibration_runs (CLI пайплайны, запускаемые из корня pneumo_solver_ui)
    - ROOT/workspace/calibration_runs (часть старых UI сценариев)

    Здесь показываем оба, чтобы UI всегда находил результаты.
    """
    cand_dirs = [
        ROOT / "calibration_runs",
        ROOT / "workspace" / "calibration_runs",
    ]
    runs: List[Path] = []
    for cr in cand_dirs:
        if not cr.exists():
            continue
        runs.extend([p for p in cr.glob("RUN_*") if p.is_dir()])

    # uniq + sort by mtime desc
    uniq = {}
    for r in runs:
        uniq[str(r.resolve())] = r
    runs = list(uniq.values())
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs


def _st_text_input(label: str, *, key: str, default: str, **kwargs) -> str:
    """Text input without SessionState warnings.

    Streamlit ругается, если одновременно передавать value=... и
    менять st.session_state[key]. Поэтому: если ключ уже есть —
    не задаём default.
    """
    if key in st.session_state:
        return st.text_input(label, key=key, **kwargs)
    return st.text_input(label, value=default, key=key, **kwargs)


st.header("Калибровка по логам (NPZ/CSV)")
st.caption(
    "Эта страница запускает готовые скрипты из папки ./calibration. "
    "Рекомендуемый режим — autopilot v20 (самый полный + отчёт System Influence + влияние параметров пневматики/кинематики)."
)

if not CAL.exists():
    st.error(f"Не найдена папка calibration: {CAL}")
    st.stop()

# --- 0) удобный выбор логов без ручного ввода путей ---
with st.expander("0) Выбор логов (NPZ/CSV) — без ручного ввода путей", expanded=True):
    st.write(
        "Streamlit не умеет выбирать **папки** через системный диалог, но умеет выбирать **файлы**. "
        "Поэтому самый надёжный способ — загрузить либо набор `*.npz`, либо один ZIP с логами. "
        "UI сохранит их в `./osc_uploads/` и подставит путь автоматически."
    )

    mode = st.radio(
        "Как передать логи в калибровку?",
        ["Путь к папке (ручной)", "Загрузить NPZ файлы", "Загрузить ZIP (NPZ/CSV)"],
        horizontal=True,
        key="cal_import_mode",
    )

    uploads_root = ROOT / "osc_uploads"

    if mode == "Загрузить NPZ файлы":
        up_npz = st.file_uploader(
            "Выберите NPZ файлы (`T01_osc.npz`, `T02_osc.npz`, ...)",
            type=["npz"],
            accept_multiple_files=True,
            key="cal_upload_npz_files",
            help="Autopilot ожидает имена вида T01_osc.npz. Если названия другие — переименуйте до загрузки.",
        )
        if up_npz:
            st.info(f"Выбрано файлов: {len(up_npz)}")
            if st.button("Сохранить и использовать для Autopilot", key="cal_btn_save_npz"):
                stamp = time.strftime("%Y%m%d_%H%M%S")
                dst = uploads_root / f"UPLOAD_{stamp}_npz"
                saved = _save_uploaded_files(list(up_npz), dst)
                st.success(f"Сохранено: {len(saved)} файлов → {dst}")
                # Важно: задаём до создания виджетов ниже (они будут позже по коду).
                st.session_state["cal_auto_osc_dir"] = str(dst)
                st.session_state["cal_csv_osc_dir"] = str(dst)

    elif mode == "Загрузить ZIP (NPZ/CSV)":
        up_zip = st.file_uploader(
            "Выберите ZIP с логами",
            type=["zip"],
            accept_multiple_files=False,
            key="cal_upload_zip",
            help="Можно положить внутрь либо NPZ (`T01_osc.npz`...), либо CSV. Если CSV — сначала запустите конвертацию (шаг 1).",
        )
        if up_zip is not None:
            if st.button("Распаковать и использовать", key="cal_btn_extract_zip"):
                stamp = time.strftime("%Y%m%d_%H%M%S")
                dst = uploads_root / f"UPLOAD_{stamp}_zip"
                files = _extract_zip(up_zip, dst)
                st.success(f"Распаковано файлов: {len(files)} → {dst}")
                st.session_state["cal_auto_osc_dir"] = str(dst)
                st.session_state["cal_csv_osc_dir"] = str(dst)

    else:
        st.info(
            "Оставьте режим **Путь к папке (ручной)** и используйте поля ниже, если у вас уже есть папка `osc_dir` на диске."
        )

    # текущая папка (после загрузки/распаковки либо по умолчанию)
    cur_dir = Path(st.session_state.get("cal_auto_osc_dir") or (ROOT / "workspace" / "osc")).expanduser().resolve()
    st.code(str(cur_dir))
    if cur_dir.exists():
        npz, csv, has_signals = _scan_osc_dir(cur_dir)
        st.write(
            f"Найдено: NPZ={len(npz)}, CSV={len(csv)}, signals.csv={'да' if has_signals else 'нет'}"
        )
        if not npz:
            st.warning(
                "В этой папке не найдено `T*_osc.npz`. Autopilot v19 не сможет стартовать, пока не будут NPZ логи. "
                "Если у вас CSV — сначала выполните шаг 1 (конвертация)."
            )
    else:
        st.warning("Папка не существует. Укажите путь ниже или загрузите файлы выше.")

with st.expander("1) Конвертация CSV → NPZ (osc_csv_to_npz_v1)", expanded=False):
    st.write(
        "Если у вас логи в CSV (osc_dir), сначала конвертируйте их в NPZ, "
        "чтобы пайплайны калибровки работали быстрее и стабильнее."
    )

    osc_dir_csv = _st_text_input(
        "Папка osc_dir с CSV",
        key="cal_csv_osc_dir",
        default=_path_default(ROOT / "workspace" / "osc"),
    )
    out_dir_npz = _st_text_input(
        "Куда писать NPZ (out_dir, опционально)",
        key="cal_csv_out_dir",
        default="",
    )
    overwrite = st.checkbox("Перезаписывать существующие NPZ", value=False, key="cal_csv_overwrite")

    colA, colB = st.columns([1, 1])
    with colA:
        if st.button("Сконвертировать CSV → NPZ", key="btn_csv2npz"):
            osc_p = Path(osc_dir_csv).expanduser()
            if not osc_p.exists():
                st.error(f"Папка не найдена: {osc_p}")
                st.stop()
            has_csv = any(osc_p.glob("*.csv"))
            if not has_csv:
                st.warning("В папке не найдено CSV. Если у вас NPZ — пропустите этот шаг.")
            cmd = [sys.executable, str(CAL / "osc_csv_to_npz_v1.py"), "--osc_dir", osc_dir_csv]
            if out_dir_npz.strip():
                cmd += ["--out_dir", out_dir_npz.strip()]
            if overwrite:
                cmd.append("--overwrite")
            st.code(_quote_cmd(cmd))
            res = _run_cmd(cmd, cwd=ROOT)
            if res.returncode == 0:
                st.success("Готово.")
            else:
                st.error(f"Ошибка (код {res.returncode}).")
            if res.stdout:
                st.text_area("stdout", res.stdout, height=220)
            if res.stderr:
                st.text_area("stderr", res.stderr, height=160)

    with colB:
        st.markdown(
            "**Подсказка:** если out_dir пустой, скрипт пишет рядом с osc_dir (см. stdout).\n\n"
            "Для autopilot удобно указать osc_dir уже с NPZ."
        )


with st.expander("2) Autopilot (pipeline_npz_autopilot_v20)", expanded=True):
    st.write(
        "Autopilot v20: v19 (bootstrap + v18) + автоматический отчёт System Influence (пневматика+кинематика) и план стадий по влиянию. Опционально: добавьте `--run_influence_staged_refine`, чтобы после staging прогнать staged refine (может быть долго). "
        "Поддерживает coarse-to-fine, блоковую донастройку, OED, профили, графики, Pareto/epsilon trade-off." 
    )

    osc_dir = _st_text_input(
        "osc_dir (NPZ-логи)",
        key="cal_auto_osc_dir",
        default=_path_default(ROOT / "workspace" / "osc"),
        help="Папка, где лежат файлы вида T01_osc.npz. Если выбрали загрузку выше — путь подставится автоматически.",
    )
    out_dir = _st_text_input("out_dir (опционально)", key="cal_auto_out_dir", default="")
    signals_csv = _st_text_input(
        "signals_csv (auto|путь)",
        key="cal_auto_signals",
        default="auto",
        help="Если auto — autopilot постарается построить/подхватить signals.csv. Иначе укажите явный путь.",
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        run_time_align = st.checkbox("run_time_align", value=True, key="cal_auto_time_align")
        run_oed = st.checkbox("run_oed", value=False, key="cal_auto_oed")
    with col2:
        run_profile_auto = st.checkbox("run_profile_auto", value=False, key="cal_auto_profile")
        run_plots = st.checkbox("run_plots", value=True, key="cal_auto_plots")
    with col3:
        run_pareto = st.checkbox("run_pareto", value=False, key="cal_auto_pareto")
        run_epsilon = st.checkbox("run_epsilon", value=False, key="cal_auto_epsilon")
    with col4:
        coarse_to_fine = st.checkbox("coarse_to_fine", value=False, key="cal_auto_ctf")
        use_smoothing_defaults = st.checkbox("use_smoothing_defaults", value=True, key="cal_auto_smooth")

    c1, c2, c3 = st.columns(3)
    with c1:
        iters = st.number_input("iters", min_value=1, max_value=10, value=2, step=1, key="cal_auto_iters")
        meas_stride = st.number_input("meas_stride", min_value=1, max_value=50, value=1, step=1, key="cal_auto_stride")
    with c2:
        n_init = st.number_input("n_init", min_value=4, max_value=400, value=32, step=4, key="cal_auto_n_init")
        n_best = st.number_input("n_best", min_value=1, max_value=100, value=6, step=1, key="cal_auto_n_best")
    with c3:
        max_nfev = st.number_input("max_nfev", min_value=20, max_value=5000, value=220, step=20, key="cal_auto_max_nfev")
        time_budget_sec = st.number_input("time_budget_sec (0=без лимита)", min_value=0.0, value=0.0, step=60.0, key="cal_auto_time_budget")

    extra_args = _st_text_input(
        "Дополнительные аргументы (как в CLI, опционально)",
        key="cal_auto_extra",
        default="",
        help="Например: --global_init cem --de_maxiter 10",
    )

    colR1, colR2 = st.columns([1, 1])
    with colR1:
        if st.button("Запустить autopilot v20", key="btn_autopilot"):
            osc_p = Path(osc_dir).expanduser()
            if not osc_p.exists():
                st.error(f"Папка не найдена: {osc_p}")
                st.stop()
            npz_files = sorted(osc_p.glob("T*_osc.npz"))
            if not npz_files:
                st.error(
                    "Не найдено ни одного файла `T*_osc.npz` — autopilot не сможет стартовать. "
                    "Если у вас CSV — сначала выполните шаг 1 (конвертация CSV→NPZ)."
                )
                st.stop()

            cmd = [
                sys.executable,
                str(CAL / "pipeline_npz_autopilot_v20.py"),
                "--osc_dir",
                osc_dir,
                "--signals_csv",
                signals_csv,
                "--iters",
                str(int(iters)),
                "--meas_stride",
                str(int(meas_stride)),
                "--n_init",
                str(int(n_init)),
                "--n_best",
                str(int(n_best)),
                "--max_nfev",
                str(int(max_nfev)),
            ]
            if out_dir.strip():
                cmd += ["--out_dir", out_dir.strip()]
            if run_time_align:
                cmd.append("--run_time_align")
            if run_oed:
                cmd.append("--run_oed")
            if run_profile_auto:
                cmd.append("--run_profile_auto")
            if run_plots:
                cmd.append("--run_plots")
            if run_pareto:
                cmd.append("--run_pareto")
            if run_epsilon:
                cmd.append("--run_epsilon")
            if coarse_to_fine:
                cmd.append("--coarse_to_fine")
            if use_smoothing_defaults:
                cmd.append("--use_smoothing_defaults")
            if float(time_budget_sec) > 0:
                cmd += ["--time_budget_sec", str(float(time_budget_sec))]

            if extra_args.strip():
                try:
                    cmd += shlex.split(extra_args)
                except Exception as e:
                    st.error(f"Не удалось разобрать extra_args: {e}")

            st.code(_quote_cmd(cmd))
            res = _run_cmd(cmd, cwd=ROOT)
            if res.returncode == 0:
                st.success("Autopilot завершён (v20).")
            else:
                st.error(f"Autopilot завершился с ошибкой (код {res.returncode}).")
            if res.stdout:
                st.text_area("stdout", res.stdout, height=260)
            if res.stderr:
                st.text_area("stderr", res.stderr, height=200)

    with colR2:
        st.markdown(
            "**Что обычно включать:**\n"
            "- `run_time_align` почти всегда полезен для реальных логов (компенсация задержек).\n"
            "- `use_smoothing_defaults` — мягче модель/оптимизация.\n"
            "- `run_plots` — строит диагностические графики после итераций.\n"
            "- `coarse_to_fine` — если модель тяжёлая и/или много сигналов.\n"
        )


with st.expander("3) Быстрые проверки (self_check / passport_check)", expanded=False):
    st.write("Полезно, чтобы убедиться, что модель и паспорт компонентов согласованы.")

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("self_check.py", key="btn_self_check"):
            cmd = [sys.executable, str(ROOT / "self_check.py")]
            st.code(_quote_cmd(cmd))
            res = _run_cmd(cmd, cwd=ROOT)
            st.write(f"returncode: {res.returncode}")
            if res.stdout:
                st.text_area("stdout", res.stdout, height=220)
            if res.stderr:
                st.text_area("stderr", res.stderr, height=160)

    with c2:
        if st.button("passport_check.py", key="btn_passport_check"):
            cmd = [sys.executable, str(ROOT / "passport_check.py")]
            st.code(_quote_cmd(cmd))
            res = _run_cmd(cmd, cwd=ROOT)
            st.write(f"returncode: {res.returncode}")
            if res.stdout:
                st.text_area("stdout", res.stdout, height=220)
            if res.stderr:
                st.text_area("stderr", res.stderr, height=160)

    with c3:
        if st.button("iso_fit_demo.py", key="btn_iso_fit_demo"):
            cmd = [sys.executable, str(ROOT / "iso_fit_demo.py")]
            st.code(_quote_cmd(cmd))
            res = _run_cmd(cmd, cwd=ROOT)
            st.write(f"returncode: {res.returncode}")
            if res.stdout:
                st.text_area("stdout", res.stdout, height=220)
            if res.stderr:
                st.text_area("stderr", res.stderr, height=160)


with st.expander("4) Найденные calibration_runs", expanded=False):
    runs = _list_calibration_runs()
    if not runs:
        st.info("Папка calibration_runs пуста или отсутствует.")
    else:
        sel = st.selectbox(
            "Выбери RUN_*",
            options=runs,
            format_func=lambda p: p.name,
            index=0,
            key="cal_runs_select",
        )
        if sel is not None:
            st.write(f"Путь: `{sel}`")
            files = [p for p in sel.rglob("*") if p.is_file()]
            files.sort(key=lambda p: (p.suffix, p.name))
            st.write(f"Файлов: {len(files)}")
            # show only first ~80 to keep UI snappy
            for p in files[:80]:
                rel = p.relative_to(sel)
                colL, colR = st.columns([1.6, 0.6])
                with colL:
                    st.write(str(rel))
                with colR:
                    # allow small file download (avoid huge binaries)
                    try:
                        size_mb = p.stat().st_size / (1024 * 1024)
                        if size_mb <= 25:
                            st.download_button(
                                "Download",
                                data=p.read_bytes(),
                                file_name=p.name,
                                key=f"dl_{sel.name}_{rel}",
                            )
                        else:
                            st.caption(f"{size_mb:.1f} MB")
                    except Exception:
                        pass
