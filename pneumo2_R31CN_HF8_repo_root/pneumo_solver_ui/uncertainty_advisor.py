# -*- coding: utf-8 -*-
"""uncertainty_advisor.py

Глобальный анализ неопределённостей (UQ) и чувствительности для модели пневмосети.

Зачем:
- В проекте неизбежны паспортные «оценки» (estimated) вместо точных характеристик.
- Важно понимать НЕ «какое поле пустое», а «какие данные *влияют* на поведение системы».
- Этот инструмент:
    1) находит компоненты, задействованные в build_network_full;
    2) строит набор неопределённых факторов (в первую очередь мультипликаторы проводимости C);
    3) запускает пакет прогонов по suite (через eval_candidate);
    4) строит ранжирование «что измерять/уточнять первым».

Методы:
- 'morris' (SALib) — быстрый скрининг факторов (подходит первым делом).
- 'sobol'  (SALib) — более точный, но существенно дороже по числу прогонов.
- 'corr'   — без SALib: случайные прогоны + корреляции (Spearman/Pearson).

Примечания по ISO 6358:
- В ISO 6358 параметры C,b,m,Δpc определяются по серии измерений, а не по одной точке.
- Пока кривых нет, мы используем приближение по Qn и дефолты b,m.
  Этот модуль помогает понять, где это приближение наиболее опасно.

См. также:
- ISO 6358-1:2013 (Annex H — процедура подбора b и m методом МНК)
- SALib documentation (Sobol/Morris)

"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import re
import shutil
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from pneumo_solver_ui.module_loading import load_python_module_from_path

HERE = Path(__file__).resolve().parent


def load_py_module(path: Path, module_name: str):
    return load_python_module_from_path(path, module_name)



def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def dump_json(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def sanitize_name(s: str, max_len: int = 40) -> str:
    s = str(s or '').strip()
    s = re.sub(r'[^0-9a-zA-Z_]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    if len(s) > max_len:
        s = s[:max_len]
    if not s:
        s = 'param'
    return s


def _status_text(comp: dict) -> str:
    iso = comp.get('iso6358', {}) if isinstance(comp.get('iso6358', {}), dict) else {}
    st = iso.get('_status', {}) if isinstance(iso.get('_status', {}), dict) else {}
    return ' '.join(str(v) for v in st.values())


def _guess_uncertainty_C_rel(comp: dict) -> float:
    """Эвристика неопределённости по C (относительная, 0..1).

    Мы не делаем вид, что знаем точное распределение.
    Нужен разумный диапазон, чтобы:
    - ранжировать важность измерений;
    - не «ломать» модель экстремальными значениями.
    """
    fam = str(comp.get('family', '')).upper().strip()
    cid = str(comp.get('id', '')).upper()
    st = _status_text(comp).lower()

    # База
    unc = 0.30

    # Если компонент явно оценочный (нет табличного Qn/кривых) — шире
    if 'estimated' in st:
        unc = max(unc, 0.35)

    # 2905 / VMR — типичные точки максимальной неопределённости (часто нет прямого Qn в таблице)
    if ('2905' in cid) or (fam == 'VMR'):
        unc = max(unc, 0.50)

    # Регулятор MC как элемент с внутренней динамикой (не просто отверстие)
    if fam == 'MC':
        unc = max(unc, 0.40)

    # Дроссели/needle: реальная зависимость от положения винта может сильно отличаться
    if fam == 'SCO':
        unc = max(unc, 0.40)

    # SIL по табличным Q (Series 29) обычно лучше определены
    if fam == 'SIL' and any(cid.startswith(x) for x in ('2901', '2903', '2921', '2931', '2928', '2929')):
        unc = min(unc, 0.25)

    # Обратные клапаны VNR по Qn часто достаточно стабильны
    if fam == 'VNR':
        unc = min(max(unc, 0.20), 0.35)

    return float(np.clip(unc, 0.10, 0.80))


def ensure_passport_uncertainty(passport_raw: dict, overwrite: bool = False) -> Tuple[dict, int]:
    """Гарантировать, что в iso6358 есть блок _uncertainty для всех компонентов.

    Возвращает (passport_updated, n_changed).
    """
    data = deepcopy(passport_raw)
    comps = data.get('components', [])
    if not isinstance(comps, list):
        return data, 0

    n = 0
    for comp in comps:
        if not isinstance(comp, dict):
            continue
        iso = comp.get('iso6358', None)
        if not isinstance(iso, dict):
            comp['iso6358'] = {}
            iso = comp['iso6358']
        if (not overwrite) and isinstance(iso.get('_uncertainty', None), dict):
            continue

        unc_C = _guess_uncertainty_C_rel(comp)
        iso['_uncertainty'] = {
            'C_rel': float(unc_C),
            # b и m в ранних версиях обычно «по умолчанию» — даём небольшие коридоры.
            'b_abs': 0.05,
            'm_abs': 0.20,
            # Δpc для клапанов часто неизвестен точно, но в модели обычно вторичен.
            'delta_pc_abs_bar': 0.10,
            '_status': 'heuristic_defaults',
        }
        n += 1
    return data, n


@dataclass
class UncertainParam:
    name: str
    comp_id: str
    family: str
    bounds: Tuple[float, float]
    unc_rel: float


def select_uncertain_params(passport_raw: dict, max_params: int = 12, only_used: bool = True) -> List[UncertainParam]:
    """Собрать список неопределённых факторов kC для компонентов.

    Фактор kC масштабирует проводимость C (и C_open/C_closed) в паспорте.
    """
    comps = passport_raw.get('components', [])
    if not isinstance(comps, list):
        return []

    # кандидаты: только те, что реально встречаются в build_network_full
    cand = []
    for comp in comps:
        if not isinstance(comp, dict):
            continue
        fam = str(comp.get('family', '')).upper().strip()
        cid = str(comp.get('id', '')).strip()
        if not cid:
            continue

        used = False
        if only_used:
            in_code = comp.get('in_code', {}) if isinstance(comp.get('in_code', {}), dict) else {}
            edges = in_code.get('edges_in_build_network_full', [])
            used = isinstance(edges, list) and len(edges) > 0
            if not used:
                continue
        else:
            used = True

        iso = comp.get('iso6358', {}) if isinstance(comp.get('iso6358', {}), dict) else {}
        unc = iso.get('_uncertainty', {}) if isinstance(iso.get('_uncertainty', {}), dict) else {}
        unc_C = float(unc.get('C_rel', _guess_uncertainty_C_rel(comp)))

        # если неопределённость совсем мала — можно не включать
        if unc_C < 0.15:
            continue

        # heuristic score: uncertainty * (how many edges use it)
        in_code = comp.get('in_code', {}) if isinstance(comp.get('in_code', {}), dict) else {}
        edge_count = int(in_code.get('edge_count', 0) or 0)
        score = unc_C * max(1, edge_count)
        cand.append((score, cid, fam, unc_C))

    cand.sort(key=lambda t: t[0], reverse=True)
    cand = cand[:max(1, int(max_params))]

    out: List[UncertainParam] = []
    used_names = set()
    for _, cid, fam, unc_C in cand:
        base_name = f"kC_{sanitize_name(cid)}"
        name = base_name
        i = 2
        while name in used_names:
            name = f"{base_name}_{i}"
            i += 1
        used_names.add(name)
        lo = max(0.05, 1.0 - unc_C)
        hi = 1.0 + unc_C
        out.append(UncertainParam(name=name, comp_id=cid, family=fam, bounds=(lo, hi), unc_rel=unc_C))
    return out


def _scale_iso_in_component(comp: dict, kC: float):
    iso = comp.get('iso6358', {}) if isinstance(comp.get('iso6358', {}), dict) else None
    if iso is None:
        return

    # scalar C
    for key_m3, key_dm3 in [
        ('C_m3_s_Pa', 'C_dm3_s_bar'),
    ]:
        if key_m3 in iso and isinstance(iso.get(key_m3), (int, float)):
            iso[key_m3] = float(iso[key_m3]) * float(kC)
        if key_dm3 in iso and isinstance(iso.get(key_dm3), (int, float)):
            iso[key_dm3] = float(iso[key_dm3]) * float(kC)

    # needle: open/closed
    for key_m3, key_dm3 in [
        ('C_open_m3_s_Pa', 'C_open_dm3_s_bar'),
        ('C_closed_m3_s_Pa', 'C_closed_dm3_s_bar'),
    ]:
        if key_m3 in iso and isinstance(iso.get(key_m3), (int, float)):
            iso[key_m3] = float(iso[key_m3]) * float(kC)
        if key_dm3 in iso and isinstance(iso.get(key_dm3), (int, float)):
            iso[key_dm3] = float(iso[key_dm3]) * float(kC)


def make_passport_sample(passport_raw: dict, params: List[UncertainParam], x_row: np.ndarray) -> dict:
    data = deepcopy(passport_raw)
    comps = data.get('components', [])
    if not isinstance(comps, list):
        return data

    # map id -> factor
    k_map = {p.comp_id: float(x_row[i]) for i, p in enumerate(params)}
    for comp in comps:
        if not isinstance(comp, dict):
            continue
        cid = str(comp.get('id', '')).strip()
        if cid in k_map:
            _scale_iso_in_component(comp, k_map[cid])
    return data


def _try_import_salib():
    try:
        from SALib.sample import morris as morris_sample  # noqa
        from SALib.sample import saltelli  # noqa
        from SALib.analyze import morris as morris_analyze  # noqa
        from SALib.analyze import sobol as sobol_analyze  # noqa
        return True
    except Exception:
        return False


def generate_samples(problem: dict, method: str, N: int, seed: int) -> np.ndarray:
    np.random.seed(int(seed))
    method = str(method).lower().strip()

    have_salib = _try_import_salib()

    if method in ('morris', 'sobol') and (not have_salib):
        # fallback
        method = 'corr'

    if method == 'morris':
        from SALib.sample import morris as morris_sample
        X = morris_sample.sample(problem, N=int(N), num_levels=4, optimal_trajectories=None)
        return np.asarray(X, dtype=float)

    if method == 'sobol':
        from SALib.sample import saltelli
        # calc_second_order=False чтобы не раздувать количество прогонов
        X = saltelli.sample(problem, N=int(N), calc_second_order=False)
        return np.asarray(X, dtype=float)

    # corr / random
    bounds = np.asarray(problem['bounds'], dtype=float)
    lo = bounds[:, 0]
    hi = bounds[:, 1]
    X = lo + (hi - lo) * np.random.rand(int(N), int(problem['num_vars']))
    return np.asarray(X, dtype=float)


def analyze_sensitivity(problem: dict, method: str, X: np.ndarray, Y: np.ndarray) -> dict:
    method = str(method).lower().strip()
    have_salib = _try_import_salib()

    if method == 'morris' and have_salib:
        from SALib.analyze import morris as morris_analyze
        return morris_analyze.analyze(problem, X, Y, num_levels=4, print_to_console=False)

    if method == 'sobol' and have_salib:
        from SALib.analyze import sobol as sobol_analyze
        return sobol_analyze.analyze(problem, Y, print_to_console=False)

    # fallback: корреляции
    # Spearman лучше для нелинейностей, но без SciPy можно сделать ранги вручную.
    df = pd.DataFrame(X, columns=problem['names'])
    y = pd.Series(Y, name='Y')
    # Spearman rank corr
    r = df.rank(pct=True).corrwith(y.rank(pct=True), axis=0)
    return {
        'method': 'corr_spearman',
        'corr': r.to_dict(),
    }


def run_uq(
    model_path: Path,
    base_json: Path,
    suite_json: Path,
    passport_json: Path,
    out_dir: Path,
    method: str = 'morris',
    N: int = 12,
    seed: int = 1,
    max_params: int = 12,
    only_used: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Главная точка входа.

    Возвращает:
      - summary_df: сводка чувствительности/приоритетов
      - runs_df: таблица всех прогонов (inputs + outputs)
      - meta: служебная информация
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # загрузки
    base = load_json(base_json)
    suite = load_json(suite_json)
    passport_raw = load_json(passport_json)

    # гарантируем _uncertainty
    passport_raw_u, n_changed = ensure_passport_uncertainty(passport_raw, overwrite=False)
    if n_changed > 0:
        # не перезаписываем исходный паспорт молча — сохраняем рядом
        dump_json(out_dir / 'component_passport_with_uncertainty.json', passport_raw_u)

    params_list = select_uncertain_params(passport_raw_u, max_params=max_params, only_used=only_used)
    if not params_list:
        raise RuntimeError('Не найдено неопределённых параметров (params_list пуст).')

    problem = {
        'num_vars': len(params_list),
        'names': [p.name for p in params_list],
        'bounds': [list(p.bounds) for p in params_list],
    }

    X = generate_samples(problem, method=method, N=int(N), seed=int(seed))

    # загружаем модель и evaluator
    model = load_py_module(model_path, 'model')
    opt = load_py_module((HERE / 'opt_worker_v3_margins_energy.py').resolve(), 'opt_worker')

    cfg = {'suite': suite.get('suite', suite) if isinstance(suite, dict) else suite}

    # куда писать сэмпл-паспорта
    pass_dir = out_dir / 'passports'
    pass_dir.mkdir(parents=True, exist_ok=True)

    # прогоняем
    rows = []

    # tqdm (если есть)
    try:
        from tqdm import tqdm
        it = tqdm(range(X.shape[0]), desc='UQ runs')
    except Exception:
        it = range(X.shape[0])

    for i in it:
        x_row = X[i, :]
        # генерим паспорт
        p_i = make_passport_sample(passport_raw_u, params_list, x_row)
        p_path = pass_dir / f'passport_{i:04d}.json'
        dump_json(p_path, p_i)

        # параметры модели
        params = deepcopy(base)
        params['использовать_паспорт_компонентов'] = True
        params['паспорт_компонентов_json'] = str(p_path)

        # eval_candidate на suite
        res = opt.eval_candidate(model, idx=int(i), params=params, cfg=cfg)

        row = {p.name: float(x_row[j]) for j, p in enumerate(params_list)}
        # основные KPI
        for k in [
            'штраф_физичности_сумма',
            'цель1_устойчивость_инерция__с',
            'цель2_комфорт__RMS_ускор_м_с2',
            'метрика_энергия_дроссели_микро_Дж',
            'метрика_крен_ay3_град',
        ]:
            if k in res:
                try:
                    row[k] = float(res.get(k))
                except Exception:
                    pass

        rows.append(row)

    runs_df = pd.DataFrame(rows)
    runs_df.to_csv(out_dir / 'uq_runs.csv', index=False, encoding='utf-8-sig')

    # анализ чувствительности по нескольким выходам
    outputs = [
        'штраф_физичности_сумма',
        'цель1_устойчивость_инерция__с',
        'цель2_комфорт__RMS_ускор_м_с2',
    ]

    summaries = []
    for out_name in outputs:
        if out_name not in runs_df.columns:
            continue
        Y = runs_df[out_name].to_numpy(dtype=float)
        # SAN: NaN -> большой штраф
        if np.any(~np.isfinite(Y)):
            Y = np.where(np.isfinite(Y), Y, np.nanmax(np.where(np.isfinite(Y), Y, 0.0)) + 1e3)

        Si = analyze_sensitivity(problem, method=method, X=X, Y=Y)

        if isinstance(Si, dict) and Si.get('method', '') == 'corr_spearman':
            corr = Si.get('corr', {})
            for p in params_list:
                val = float(corr.get(p.name, 0.0) or 0.0)
                summaries.append({
                    'output': out_name,
                    'param': p.name,
                    'comp_id': p.comp_id,
                    'family': p.family,
                    'unc_C_rel': p.unc_rel,
                    'importance': abs(val),
                    'metric': 'abs_spearman',
                    'value': val,
                })
            continue

        # Morris
        if method.lower().strip() == 'morris' and ('mu_star' in Si):
            mu_star = Si.get('mu_star', [])
            sigma = Si.get('sigma', [])
            for j, p in enumerate(params_list):
                ms = float(mu_star[j]) if j < len(mu_star) else float('nan')
                sg = float(sigma[j]) if j < len(sigma) else float('nan')
                summaries.append({
                    'output': out_name,
                    'param': p.name,
                    'comp_id': p.comp_id,
                    'family': p.family,
                    'unc_C_rel': p.unc_rel,
                    'importance': abs(ms),
                    'metric': 'morris_mu_star',
                    'value': ms,
                    'sigma': sg,
                })
            continue

        # Sobol
        if method.lower().strip() == 'sobol' and ('ST' in Si):
            ST = Si.get('ST', [])
            S1 = Si.get('S1', [])
            for j, p in enumerate(params_list):
                st = float(ST[j]) if j < len(ST) else float('nan')
                s1 = float(S1[j]) if j < len(S1) else float('nan')
                summaries.append({
                    'output': out_name,
                    'param': p.name,
                    'comp_id': p.comp_id,
                    'family': p.family,
                    'unc_C_rel': p.unc_rel,
                    'importance': abs(st),
                    'metric': 'sobol_ST',
                    'value': st,
                    'S1': s1,
                })
            continue

    summary_df = pd.DataFrame(summaries)
    if not summary_df.empty:
        summary_df.to_csv(out_dir / 'uq_sensitivity_summary.csv', index=False, encoding='utf-8-sig')

    # приоритет измерений: средняя importance по выходам * unc
    if not summary_df.empty:
        grp = summary_df.groupby(['param', 'comp_id', 'family', 'unc_C_rel'], as_index=False)['importance'].mean()
        grp['priority'] = grp['importance'] * grp['unc_C_rel']
        grp = grp.sort_values('priority', ascending=False)
        grp.to_csv(out_dir / 'measurement_priority.csv', index=False, encoding='utf-8-sig')
        pr_df = grp
    else:
        pr_df = pd.DataFrame()

    meta = {
        'method': method,
        'N': int(N),
        'seed': int(seed),
        'max_params': int(max_params),
        'only_used': bool(only_used),
        'n_uncertainty_added': int(n_changed),
        'num_samples': int(X.shape[0]),
        'num_params': int(problem['num_vars']),
        'params': [p.__dict__ for p in params_list],
        'paths': {
            'out_dir': str(out_dir),
            'uq_runs_csv': str(out_dir / 'uq_runs.csv'),
        }
    }
    dump_json(out_dir / 'uq_meta.json', meta)

    return pr_df, runs_df, meta


def main():
    ap = argparse.ArgumentParser(description='UQ/Sensitivity analysis for Pneumo model')
    ap.add_argument('--model', default=str((HERE / 'model_pneumo_v8_energy_audit_vacuum.py').resolve()), help='Path to model .py')
    ap.add_argument('--base', default=str((HERE / 'default_base.json').resolve()), help='Path to base params JSON')
    ap.add_argument('--suite', default=str((HERE / 'default_suite.json').resolve()), help='Path to suite JSON')
    ap.add_argument('--passport', default=str((HERE / 'component_passport.json').resolve()), help='Path to component_passport.json')
    ap.add_argument('--out', default=str((HERE / '..' / 'out' / 'uq').resolve()), help='Output directory')
    ap.add_argument('--method', default='morris', choices=['morris', 'sobol', 'corr'], help='Sensitivity method')
    ap.add_argument('--N', type=int, default=12, help='Base sample size (interpretation depends on method)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--max_params', type=int, default=12)
    ap.add_argument('--include_unused', action='store_true', help='Also include components not referenced in build_network_full')
    args = ap.parse_args()

    out_dir = Path(args.out).resolve()
    pr_df, runs_df, meta = run_uq(
        model_path=Path(args.model).resolve(),
        base_json=Path(args.base).resolve(),
        suite_json=Path(args.suite).resolve(),
        passport_json=Path(args.passport).resolve(),
        out_dir=out_dir,
        method=str(args.method),
        N=int(args.N),
        seed=int(args.seed),
        max_params=int(args.max_params),
        only_used=(not bool(args.include_unused)),
    )

    print('=== UQ finished ===')
    print('out_dir:', out_dir)
    if not pr_df.empty:
        print('\nTop measurement priorities:')
        print(pr_df.head(12).to_string(index=False))


if __name__ == '__main__':
    main()
