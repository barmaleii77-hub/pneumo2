# -*- coding: utf-8 -*-
"""Streamlit page: Uncertainty / Sensitivity (R48)

Цель:
- Понять, какие паспортные неопределённости (в первую очередь ISO 6358 C)
  сильнее всего влияют на поведение системы.
- Получить ранжирование «что мерить/уточнять первым», чтобы модель быстрее стала «железной».

Важно:
- Это вычислительно тяжёлая операция.
- Начинайте с метода Morris (N=8..12, max_params=8..12).
"""

import json
from pathlib import Path
from pneumo_solver_ui.module_loading import load_python_module_from_path
import streamlit as st
from pneumo_solver_ui.ui_bootstrap import bootstrap
from pneumo_solver_ui.ui_persistence import autosave_if_enabled

bootstrap(st)
autosave_if_enabled(st)

HERE = Path(__file__).resolve().parent.parent

st.title("Uncertainty / Sensitivity — что в паспорте реально важно")

model_py = st.text_input("Модель (py)", str(HERE / 'model_pneumo_v8_energy_audit_vacuum.py'))
base_json = st.text_input("Base параметры (json)", str(HERE / 'default_base.json'))
suite_json = st.text_input("Suite (json)", str(HERE / 'default_suite.json'))
passport_json = st.text_input("Паспорт компонентов (json)", str(HERE / 'component_passport.json'))

method = st.selectbox("Метод", ['morris', 'sobol', 'corr'], index=0,
                      help="morris — быстрый скрининг; sobol — точнее, но дороже; corr — без SALib")
N = st.number_input("N (размер выборки)", min_value=2, max_value=200, value=12, step=1)
max_params = st.number_input("Макс. число факторов", min_value=2, max_value=40, value=12, step=1)
seed = st.number_input("Seed", min_value=0, max_value=10_000, value=1, step=1)

run = st.button("Запустить UQ")

if run:
    mp = Path(model_py)
    bp = Path(base_json)
    sp = Path(suite_json)
    pp = Path(passport_json)
    for p in (mp, bp, sp, pp):
        if not p.exists():
            st.error(f"Не найден файл: {p}")
            st.stop()

    # Подгружаем модуль uncertainty_advisor
    import importlib.util

    def load_py_module(path: Path, module_name: str):
        return load_python_module_from_path(path, module_name)

    uq = load_py_module(HERE / 'uncertainty_advisor.py', 'uq_mod')

    out_dir = HERE.parent / 'out' / 'uq_streamlit'
    out_dir.mkdir(parents=True, exist_ok=True)

    st.info("Запуск... (может занять время, зависит от suite и N)")

    pr_df, runs_df, meta = uq.run_uq(
        model_path=mp.resolve(),
        base_json=bp.resolve(),
        suite_json=sp.resolve(),
        passport_json=pp.resolve(),
        out_dir=out_dir.resolve(),
        method=str(method),
        N=int(N),
        seed=int(seed),
        max_params=int(max_params),
        only_used=True,
    )

    st.success("Готово")

    st.subheader("Приоритет измерений / уточнения")
    if pr_df is not None and len(pr_df) > 0:
        st.dataframe(pr_df, width="stretch")
    else:
        st.write("Пусто (возможно, нет факторов или ошибка метода)")

    st.subheader("Результаты прогонов")
    if runs_df is not None and len(runs_df) > 0:
        st.dataframe(runs_df.head(200), width="stretch")
        st.caption("Показаны первые 200 строк")
    else:
        st.write("Пусто")

    st.subheader("Meta")
    st.json(meta)

    # Ссылки на файлы в out_dir
    st.subheader("Экспорт")
    st.write(f"Папка: {out_dir}")
    for fn in [
        'uq_runs.csv',
        'measurement_priority.csv',
        'sensitivity__штраф_физичности_сумма.csv',
        'uq_report.md',
    ]:
        f = out_dir / fn
        if f.exists():
            st.write(str(f))
