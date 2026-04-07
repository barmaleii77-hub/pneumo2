# -*- coding: utf-8 -*-
"""03_SystemInfluence.py

Streamlit страница: System Influence (пневматика + кинематика)

Показывает:
- отчёт SYSTEM_INFLUENCE.md, если уже есть в папке RUN_...
- возможность пересобрать отчёт и план стадий по влиянию

"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List

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


def _run_cmd(cmd: List[str], cwd: Path = ROOT):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def _list_runs() -> List[Path]:
    cand = [ROOT / "calibration_runs", ROOT / "workspace" / "calibration_runs"]
    runs: List[Path] = []
    for d in cand:
        if d.exists():
            runs.extend([p for p in d.glob("RUN_*") if p.is_dir()])
    uniq = {}
    for r in runs:
        uniq[str(r.resolve())] = r
    runs = list(uniq.values())
    runs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return runs


st.header("System Influence (пневматика + кинематика)")

runs = _list_runs()
if not runs:
    st.warning("Не найдено ни одной папки RUN_* в calibration_runs. Сначала запустите autopilot.")
    st.stop()

run_names = [r.name for r in runs]
sel = st.selectbox("RUN dir", run_names, index=0)
run_dir = runs[run_names.index(sel)]

st.caption(f"Папка: {run_dir}")

sys_md = run_dir / "SYSTEM_INFLUENCE.md"
sys_json = run_dir / "system_influence.json"
params_csv = run_dir / "system_influence_params.csv"
edges_csv = run_dir / "system_influence_edges.csv"
paths_csv = run_dir / "system_influence_paths.csv"

stage_dir = run_dir / "param_staging_influence"
stage_md = stage_dir / "PARAM_STAGING_INFLUENCE.md"
stages_json = stage_dir / "stages_influence.json"

colA, colB, colC = st.columns(3)
with colA:
    if st.button("Сформировать/обновить System Influence", key="btn_sysinf"):
        cmd = [sys.executable, str(CAL / "system_influence_report_v1.py"), "--run_dir", str(run_dir)]
        st.code(" ".join(cmd))
        res = _run_cmd(cmd)
        if res.returncode == 0:
            st.success("Готово.")
        else:
            st.error(f"Ошибка (код {res.returncode}).")
        if res.stdout:
            st.text_area("stdout", res.stdout, height=180)
        if res.stderr:
            st.text_area("stderr", res.stderr, height=180)

with colB:
    if st.button("Сформировать план стадий (influence)", key="btn_stage_inf"):
        # фит-диапазоны: prefer pruned
        fr_pruned = run_dir / "param_prune" / "fit_ranges_pruned.json"
        wrapper = run_dir / "AUTOPILOT_V19_WRAPPER.json"
        if fr_pruned.exists():
            fit_ranges = fr_pruned
        elif wrapper.exists():
            try:
                import json
                meta = json.loads(wrapper.read_text(encoding="utf-8"))
                fit_ranges = (ROOT / str(meta.get("fit_ranges_json", "default_ranges.json"))).resolve()
            except Exception:
                fit_ranges = ROOT / "default_ranges.json"
        else:
            fit_ranges = ROOT / "default_ranges.json"

        stage_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            str(CAL / "param_staging_v3_influence.py"),
            "--fit_ranges_json",
            str(fit_ranges),
            "--out_dir",
            str(stage_dir),
        ]
        oed = run_dir / "oed_report.json"
        if oed.exists():
            cmd += ["--oed_report_json", str(oed)]
        if sys_json.exists():
            cmd += ["--system_influence_json", str(sys_json)]

        st.code(" ".join(cmd))
        res = _run_cmd(cmd)
        if res.returncode == 0:
            st.success("Готово.")
        else:
            st.error(f"Ошибка (код {res.returncode}).")
        if res.stdout:
            st.text_area("stdout", res.stdout, height=180)
        if res.stderr:
            st.text_area("stderr", res.stderr, height=180)

with colC:
    if st.button("Пересобрать REPORT_FULL.md", key="btn_rebuild_full"):
        cmd = [sys.executable, str(CAL / "report_full_from_run_v1.py"), "--run_dir", str(run_dir)]
        st.code(" ".join(cmd))
        res = _run_cmd(cmd)
        if res.returncode == 0:
            st.success("REPORT_FULL.md обновлён.")
        else:
            st.error(f"Ошибка (код {res.returncode}).")
        if res.stdout:
            st.text_area("stdout", res.stdout, height=160)
        if res.stderr:
            st.text_area("stderr", res.stderr, height=160)

st.divider()

if sys_md.exists():
    st.subheader("SYSTEM_INFLUENCE.md")
    st.markdown(sys_md.read_text(encoding="utf-8", errors="ignore"))
else:
    st.info("SYSTEM_INFLUENCE.md пока не найден. Нажмите кнопку выше для генерации.")

if stage_md.exists():
    st.subheader("PARAM_STAGING_INFLUENCE.md")
    st.markdown(stage_md.read_text(encoding="utf-8", errors="ignore"))

st.subheader("Артефакты")
for p in [sys_json, params_csv, edges_csv, paths_csv, stages_json]:
    if p.exists():
        st.write(f"- {p.relative_to(run_dir)}")

# --- Автосохранение UI (лучшее усилие) ---
# Важно: значения, введённые на этой странице, не должны пропадать при refresh/перезапуске.
