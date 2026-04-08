# -*- coding: utf-8 -*-
"""root_cause_report.py

Человекочитаемый отчёт «почему вариант плохой».

Что делает:
- запускает baseline по default_suite.json (или по указанному suite),
- для каждого теста сохраняет метрики (включая root-cause поля),
- пишет CSV и Markdown отчёт.

Запуск:
    python root_cause_report.py

Опции:
    --base default_base.json
    --suite default_suite.json
    --model model_pneumo_v8_energy_audit_vacuum.py
    --worker opt_worker_v3_margins_energy.py
    --out baseline_root_cause

Примечание:
- Скрипт НЕ требует streamlit.
- Скорость не оптимизировалась (по задаче важнее физическая информативность).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
import importlib.util

import numpy as np
import pandas as pd
from pneumo_solver_ui.module_loading import load_python_module_from_path
from pneumo_solver_ui.packaging_surface_helpers import (
    collect_packaging_surface_metrics,
    format_packaging_markdown_lines,
)


HERE = Path(__file__).resolve().parent


def load_py_module(path: Path, module_name: str):
    return load_python_module_from_path(path, module_name)



def fmt(x, nd: int = 4):
    try:
        xf = float(x)
        if abs(xf) >= 1e4 or (0 < abs(xf) < 1e-3):
            return f"{xf:.{nd}g}"
        return f"{xf:.{nd}f}"
    except Exception:
        return str(x)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='default_base.json')
    ap.add_argument('--suite', default='default_suite.json')
    ap.add_argument('--model', default='model_pneumo_v8_energy_audit_vacuum.py')
    ap.add_argument('--worker', default='opt_worker_v3_margins_energy.py')
    ap.add_argument('--out', default='baseline_root_cause')
    args = ap.parse_args()

    base_path = (HERE / args.base).resolve()
    suite_path = (HERE / args.suite).resolve()
    model_path = (HERE / args.model).resolve()
    worker_path = (HERE / args.worker).resolve()

    base = json.loads(base_path.read_text(encoding='utf-8'))
    suite = json.loads(suite_path.read_text(encoding='utf-8'))

    model = load_py_module(model_path, 'pneumo_model')
    worker = load_py_module(worker_path, 'pneumo_worker')

    tests = worker.build_test_suite({'suite': suite})

    rows = []

    md = []
    md.append(f"# Root-cause отчёт (baseline)\n")
    md.append(f"- Дата: {datetime.now().isoformat(timespec='seconds')}\n")
    md.append(f"- Base: `{base_path.name}`\n")
    md.append(f"- Suite: `{suite_path.name}`\n")
    md.append(f"- Model: `{model_path.name}`\n")
    md.append(f"- Worker: `{worker_path.name}`\n")

    for test_name, test, dt, t_end, targets in tests:
        md.append("\n---\n")
        md.append(f"## {test_name}\n")
        desc = ''
        try:
            desc = str(test.get('описание', '') or '')
        except Exception:
            desc = ''
        if desc:
            md.append(desc + "\n")

        try:
            m = worker.eval_candidate_once(model, base, test, dt=float(dt), t_end=float(t_end), targets=targets)
            pen = float(worker.candidate_penalty(m, targets))
        except Exception as e:
            rows.append({'тест': test_name, 'ошибка': str(e), 'штраф': 1e9})
            md.append(f"**ОШИБКА:** {e}\n")
            continue

        packaging_summary = collect_packaging_surface_metrics(m, targets=targets, params=base)
        m2 = dict(m)
        m2['тест'] = test_name
        m2['штраф'] = pen
        m2.update(packaging_summary)
        rows.append(m2)

        # Ключевые KPI (минимально)
        md.append(f"- штраф: **{fmt(pen, 4)}**\n")
        md.append(f"- крен_max: {fmt(m.get('крен_max_град', 'na'))} град, тангаж_max: {fmt(m.get('тангаж_max_град', 'na'))} град\n")
        md.append(f"- RMS ускорения рамы: {fmt(m.get('RMS_ускор_рамы_м_с2', 'na'))} м/с²\n")
        md.append(f"- отрыв (доля времени): {fmt(m.get('доля_времени_отрыв', 'na'))}\n")
        md.append(f"- шток: min запас: {fmt(m.get('мин_запас_до_упора_штока_все_м', 'na'))} м, max скорость: {fmt(m.get('макс_скорость_штока_все_м_с', 'na'))} м/с\n")

        # Root-cause
        rn = str(m.get('причины_нарушений', '') or '')
        rf = str(m.get('причины_физика', '') or '')
        topv = str(m.get('топ_нарушение', '') or '')
        topvs = fmt(m.get('топ_нарушение_оценка', 0.0))
        if rn:
            md.append(f"- причины (нарушения): `{rn}`\n")
        if topv:
            md.append(f"- топ нарушение: `{topv}` (норм. {topvs})\n")
        if rf:
            md.append(f"- причины (физика): `{rf}`\n")

        md.append("\n**Packaging / пружины**\n")
        md.extend(format_packaging_markdown_lines(m2, targets=targets, params=base, fmt_func=fmt))

        # Эксергия
        md.append("\n**Эксергия / необратимости**\n")
        md.append(f"- эксергия разрушена (всего): {fmt(m.get('эксергия_разрушена_Дж', 'na'))} Дж\n")
        md.append(f"- эксергия в атмосферу: {fmt(m.get('эксергия_в_атмосферу_Дж', 'na'))} Дж\n")
        md.append(f"- эксергия разрушена (падение давления): {fmt(m.get('эксергия_разрушена_падение_давления_Дж', 'na'))} Дж\n")
        md.append(f"- эксергия разрушена (теплопередача): {fmt(m.get('эксергия_разрушена_теплопередача_Дж', m.get('эксергия_разрушена_теплопередача_Дж', 'na')))} Дж\n")
        md.append(f"- эксергия разрушена (смешение): {fmt(m.get('эксергия_разрушена_смешение_Дж', 'na'))} Дж\n")
        md.append(f"- эксергия разрушена (остаток без тепло/смешения): {fmt(m.get('эксергия_разрушена_остаток_без_тепло_без_смешения_Дж', 'na'))} Дж\n")
        hm = str(m.get('топ_узлы_теплопередача', '') or '')
        mm = str(m.get('топ_узлы_смешение', '') or '')
        if hm:
            md.append(f"- топ узлы (теплопередача): {hm}\n")
        if mm:
            md.append(f"- топ узлы (смешение): {mm}\n")
        md.append(f"- топ группа по эксергии: `{m.get('топ_эксергия_группа', '')}` (доля {fmt(m.get('доля_эксергии_топ_группа', 'na'))})\n")
        te = str(m.get('топ_эксергия_элементы', '') or '')
        if te:
            md.append(f"- TOP-5 элементы по эксергии: {te}\n")

    df = pd.DataFrame(rows)

    out_prefix = (HERE / args.out).resolve()
    csv_path = str(out_prefix) + '.csv'
    md_path = str(out_prefix) + '.md'

    df.to_csv(csv_path, index=False)
    Path(md_path).write_text('\n'.join(md), encoding='utf-8')

    print('Saved:', csv_path)
    print('Saved:', md_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
