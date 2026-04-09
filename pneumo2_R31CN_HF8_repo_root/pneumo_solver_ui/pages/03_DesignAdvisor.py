# -*- coding: utf-8 -*-
"""Streamlit page: Design Advisor (R46)

Эта страница даёт инженеру быстрый ответ:
- какие рёбра тратят больше всего энергии на дросселировании,
- где не хватает пропускной способности C (ISO6358) при текущих режимах,
- где нужны паспортные данные (C,b,m,Δpc) вместо автоподстановок.

Важно: это **советник**, а не «автоконструктор» — он показывает, где сеть «узкое горлышко» и где данные сомнительны.
"""

import json
from pathlib import Path
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

import pandas as pd
from pneumo_solver_ui.module_loading import load_python_module_from_path

HERE = Path(__file__).resolve().parent.parent


st.title("Советник по конструкции — анализ узких мест")

base_json = st.text_input(
    "База параметров (JSON)",
    str(HERE / 'default_base.json'),
    key="ui_da_base_json",
    help="JSON с исходными параметрами (base). Обычно: default_base.json",
)
model_py = st.text_input(
    "Файл модели (PY)",
    str(HERE / 'model_pneumo_v8_energy_audit_vacuum.py'),
    key="ui_da_model_py",
    help="Python‑файл модели. Должен содержать код модели, используемый расчётом.",
)

test_kind = st.selectbox(
    "Тест для анализа",
    [
        'baseline',
            'крен_2g_0.4s',
            'тангаж_2g_0.4s',
            'синфаз_0.02m_2Hz',
            'диагональ_0.02m_2Hz'
    ],
    key="ui_da_test_kind",
    help="Выберите сценарий/тест, для которого анализировать узкие места по расходу/энергии.",
)
dt = st.number_input("Шаг dt (с)", value=0.001, format="%.6f", key="ui_da_dt", help="Шаг интегрирования для теста (сек).")
t_end = st.number_input("Длительность t_end (с)", value=2.0, format="%.3f", key="ui_da_t_end", help="Длительность теста (сек).")

run = st.button("Запустить анализ", key="ui_da_run", help="Запустить расчёт и показать рекомендации по узким местам.")

if run:
    base_path = Path(base_json)
    model_path = Path(model_py)
    if not base_path.exists():
        st.error(f"Не найден {base_path}")
        st.stop()
    if not model_path.exists():
        st.error(f"Не найден {model_path}")
        st.stop()

    params = json.loads(base_path.read_text('utf-8'))

    # Minimal test presets (под вашу механику/пневматику)
    if test_kind == 'baseline':
        test = {"тип":"инерция_крен", "ay":2.0, "t_step":0.4}
    elif test_kind == 'крен_2g_0.4s':
        test = {"тип":"инерция_крен", "ay":2.0, "t_step":0.4}
    elif test_kind == 'тангаж_2g_0.4s':
        test = {"тип":"инерция_тангаж", "ax":2.0, "t_step":0.4}
    elif test_kind == 'синфаз_0.02m_2Hz':
        test = {"тип":"синфаз", "amp_m":0.02, "freq_Hz":2.0, "t_end":float(t_end)}
    else:
        test = {"тип":"диагональ", "amp_m":0.02, "freq_Hz":2.0, "t_end":float(t_end)}

    model = load_python_module_from_path(model_path, 'model_for_design')
    da = load_python_module_from_path(HERE / 'design_advisor.py', 'design_advisor')

    st.info("Симуляция запускается с record_full=True (давления/расходы по каждому ребру).")
    df, info = da.analyze_one_run(model, params, test, dt=float(dt), t_end=float(t_end))

    # Удобочитаемая колонка с подсказками по заменам (если есть)
    if 'suggested_replacements' in df.columns:
        def _repl_to_codes(x):
            try:
                if isinstance(x, list):
                    codes = [str(it.get('code')) for it in x if isinstance(it, dict) and it.get('code')]
                    return ', '.join(codes[:5])
            except Exception:
                pass
            return ''
        df['suggested_codes'] = df['suggested_replacements'].apply(_repl_to_codes)


    st.subheader("Таблица по рёбрам")
    st.dataframe(df, width='stretch')

    rec = da.build_recommendations(df)

    st.subheader("Критичные узкие места")
    if rec.get('critical'):
        st.dataframe(pd.DataFrame(rec['critical']), width='stretch')
    else:
        st.write("Не найдено (по текущим порогам).")

    st.subheader("Не хватает паспортных данных")
    if rec.get('needs_measurement'):
        st.dataframe(pd.DataFrame(rec['needs_measurement']), width='stretch')
    else:
        st.write("Не найдено (по текущим критериям).")

    # Export
    out_dir = HERE / 'design_advisor_out'
    out_dir.mkdir(exist_ok=True)
    out_csv = out_dir / 'design_advisor_edges.csv'
    out_xlsx = out_dir / 'design_advisor_edges.xlsx'
    df.to_csv(out_csv, index=False, encoding='utf-8')
    try:
        df.to_excel(out_xlsx, index=False)
    except Exception:
        pass

    st.success(f"Экспорт: {out_csv}")

# --- Автосохранение UI (лучшее усилие) ---
# Важно: значения, введённые на этой странице, не должны пропадать при refresh/перезапуске.
