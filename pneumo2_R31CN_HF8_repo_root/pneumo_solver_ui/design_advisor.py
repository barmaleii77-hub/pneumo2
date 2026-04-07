# -*- coding: utf-8 -*-
"""design_advisor.py

Инженерный "Design Advisor" для пневмосети.

Идея:
- запускаем один тест или suite;
- собираем по рёбрам:
    * интеграл энергии дросселирования (energy_audit),
    * пик расхода |m_dot|,
    * пик перепада Δp,
    * оценку требуемого ISO6358 C_req (если выбран ISO-модель или если задан C_iso у ребра);
    * запас по C: margin_C = C_current / C_req.
- формируем рекомендации:
    * какие узлы/рёбра «душат» (большая энергия + малый запас по C),
    * где ограничения сознательные (например, синфазное демпфирование),
    * где разумно добавить/увеличить регулировку (коэф_прохода_*, дроссели).

ВАЖНО:
- C_req считается приближённо: ISO6358 модель линейна по C, поэтому C_req = |m_dot| / mdot_iso6358(C=1).
- Для регуляторов MC/VMR это «гидравлический эквивалент» проточной части, а не полная модель регулятора.

Запуск (CLI):
    python design_advisor.py --base default_base.json --test baseline

Запуск из Streamlit:
    pages/03_Design_Advisor.py

"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import importlib.util
from datetime import datetime

import numpy as np
import pandas as pd
from pneumo_solver_ui.module_loading import load_python_module_from_path

HERE = Path(__file__).resolve().parent


def load_py_module(path: Path, module_name: str):
    return load_python_module_from_path(path, module_name)



def safe_float(x, default: float = float('nan')) -> float:
    try:
        return float(x)
    except Exception:
        return default



def infer_family_from_code(code: str) -> str:
    # Очень грубая идентификация семейства по строке кода.
    s = str(code or '').strip()
    su = s.upper()
    if su.startswith('VNR'):
        return 'VNR'
    if su.startswith('SCO'):
        return 'SCO'
    if su.startswith('MC'):
        return 'MC'
    if su.startswith('VMR'):
        return 'VMR'
    if (su.startswith('2905') or su.startswith('2901') or su.startswith('2903') or su.startswith('2921') or su.startswith('2931') or su.startswith('2928') or su.startswith('2929')
            or ('SIL' in su) or ('SILENC' in su) or ('MUFF' in su)):
        return 'SIL'
    return ''


def get_component_C_max_from_passport(passport: dict, family: str, code: str) -> float:
    # Вернуть максимально доступный C для компонента по паспорту.
    try:
        fam = passport.get(family, {}) or {}
        ent = fam.get(code, None)
        if ent is None:
            return float('nan')
        iso = (ent.get('iso') or {}) if isinstance(ent, dict) else {}
        if family == 'SCO':
            C = iso.get('C_open_m3_s_Pa', None)
        else:
            C = iso.get('C_m3_s_Pa', None)
        return float(C) if C is not None else float('nan')
    except Exception:
        return float('nan')


def suggest_replacements(passport: dict, family: str, C_req: float, factor: float = 1.2, limit: int = 5) -> list[dict]:
    # Подобрать кандидатов с C >= factor * C_req.
    out = []
    if not passport or not family:
        return out
    try:
        fam = passport.get(family, {}) or {}
        target = float(C_req) * float(factor)
        for code, ent in fam.items():
            iso = (ent.get('iso') or {}) if isinstance(ent, dict) else {}
            if family == 'SCO':
                C = iso.get('C_open_m3_s_Pa', None)
            else:
                C = iso.get('C_m3_s_Pa', None)
            try:
                Cv = float(C)
            except Exception:
                continue
            if (Cv > 0.0) and (Cv >= target):
                out.append({'code': code, 'C_max_m3_s_Pa': Cv})
        out.sort(key=lambda d: d['C_max_m3_s_Pa'])
        return out[:int(limit)]
    except Exception:
        return out

def compute_C_req_from_mdot(model, p_up: float, p_dn: float, mdot: float, b: float, m: float, beta_lam: float, T_up: float) -> float:
    """Требуемый C (м³/(с·Па)) по ISO6358 для заданных p_up/p_dn/T_up и |mdot|.

    ISO-модель линейна по C, поэтому считаем mdot_per_C = mdot_iso6358(C=1).
    """
    md = abs(float(mdot))
    if (md <= 0.0) or not np.isfinite(md):
        return float('nan')
    if p_up <= p_dn:
        return float('nan')
    md_per_C = safe_float(model.mdot_iso6358(p_up, p_dn, 1.0, b=b, m=m, beta_lam=beta_lam, T_up=T_up), default=float('nan'))
    if (not np.isfinite(md_per_C)) or (md_per_C <= 0.0):
        return float('nan')
    return md / md_per_C


def analyze_one_run(model, params: dict, test: dict, dt: float, t_end: float) -> tuple[pd.DataFrame, dict]:
    """Запуск модели и получение таблицы по рёбрам.

    ВАЖНО: для вычисления C_req нам нужны df_p и df_mdot, поэтому просим model.simulate(..., record_full=True).
    """
    out = model.simulate(params, test, dt=dt, t_end=t_end, record_full=True)

    # Ожидаемая сигнатура (см. model.simulate):
    # 0 df_main, 1 df_drossel, 2 df_energy, 3 nodes, 4 edges,
    # 5 df_energy_edges, 6 df_energy_groups, 7 df_atm, 8 df_p, 9 df_mdot, 10 df_open, ...
    df_energy_edges = None
    df_p = None
    df_mdot = None
    nodes = None
    edges = None

    try:
        if isinstance(out, (list, tuple)) and len(out) >= 11:
            df_main, df_drossel, df_energy, nodes, edges, df_energy_edges, df_energy_groups, df_atm, df_p, df_mdot, df_open = out[:11]
        else:
            # fallback: попробуем эвристику
            for item in (out if isinstance(out, (list, tuple)) else [out]):
                if isinstance(item, pd.DataFrame):
                    cols = list(item.columns)
                    if any(c in cols for c in ['элемент','edge','ребро']) and any(c in cols for c in ['энергия_Дж','E_diss_J','E_J','energy_J']):
                        df_energy_edges = item
                    # df_p: часто содержит 'АТМ' и 'Ресивер1'
                    if ('АТМ' in cols) and ('Ресивер1' in cols):
                        df_p = item
                    # df_mdot: содержит много строковых колонок с именами рёбер; надёжно определить сложно
                if isinstance(item, list) and item and hasattr(item[0], 'kind'):
                    edges = item
                if isinstance(item, list) and item and hasattr(item[0], 'name'):
                    nodes = item
    except Exception:
        pass

    info = {
        'df_energy_edges': df_energy_edges,
        'df_p': df_p,
        'df_mdot': df_mdot,
        'nodes': nodes,
        'edges': edges,
    }

    rows = []
    if edges is None:
        return pd.DataFrame(), info

    # Precompute mdot column mapping
    mdot_cols = {}
    if df_mdot is not None:
        for c in df_mdot.columns:
            if c in ('t','time','время_с','time_s'):
                continue
            if c.startswith('mdot_'):
                mdot_cols[c.replace('mdot_','')] = c
            else:
                mdot_cols[c] = c

    # Pressure column mapping
    p_cols = {}
    if df_p is not None:
        for c in df_p.columns:
            if c in ('t','time','время_с','time_s'):
                continue
            if c.startswith('p_'):
                p_cols[c.replace('p_','')] = c
            else:
                p_cols[c] = c

    # Energy lookup by edge name
    E_map = {}
    if df_energy_edges is not None:
        key_candidates = ['edge','ребро','элемент','name']
        val_candidates = ['E_diss_J','E_J','dE_J','energy_J','энергия_Дж','эксергия_падение_давления_Дж']
        key_col = next((k for k in key_candidates if k in df_energy_edges.columns), None)
        val_col = next((k for k in val_candidates if k in df_energy_edges.columns), None)
        if key_col and val_col:
            for _,r in df_energy_edges.iterrows():
                E_map[str(r[key_col])] = safe_float(r[val_col], 0.0)

    # Пытаемся загрузить паспорт (нужен для подсказок по замене типоразмера).
    passport_norm = None
    try:
        p_json = params.get('паспорт_компонентов_json', 'component_passport.json')
        passport_raw = None
        if hasattr(model, 'load_component_passport'):
            passport_raw = model.load_component_passport(str(p_json))
        elif hasattr(model, 'normalize_component_passport'):
            # fallback: пробуем прочитать JSON напрямую
            passport_raw = json.loads((HERE / p_json).read_text('utf-8'))
        if passport_raw is not None and hasattr(model, 'normalize_component_passport'):
            passport_norm = model.normalize_component_passport(passport_raw)
    except Exception:
        passport_norm = None

    beta_lam = float(params.get('ISO_beta_lam', 0.999))
    iso_b_def = float(params.get('ISO_b_default', params.get('ISO_default_b', 0.5)))
    iso_m_def = float(params.get('ISO_m_default', params.get('ISO_default_m', 0.5)))

    for ei,e in enumerate(edges):
        name = getattr(e,'name', f'edge_{ei}')
        kind = getattr(e,'kind','')
        cam = getattr(e,'camozzi_код', None)
        C = getattr(e,'C_iso', None)
        b = getattr(e,'b_iso', None)
        m = getattr(e,'m_iso', None)

        # Time series peaks
        mdot_peak = float('nan')
        dp_peak = float('nan')
        p_up_peak = float('nan')
        p_dn_peak = float('nan')
        idx_m = None

        if (df_mdot is not None) and (name in mdot_cols):
            s = df_mdot[mdot_cols[name]].astype(float)
            try:
                idx_m = int(np.nanargmax(np.abs(s.to_numpy())))
            except Exception:
                idx_m = None
            try:
                mdot_peak = float(np.nanmax(np.abs(s)))
            except Exception:
                mdot_peak = float('nan')

        if (df_p is not None) and (nodes is not None):
            n1_obj = nodes[e.n1] if hasattr(e,'n1') else None
            n2_obj = nodes[e.n2] if hasattr(e,'n2') else None
            n1 = getattr(n1_obj,'name', n1_obj)
            n2 = getattr(n2_obj,'name', n2_obj)
            if (n1 in p_cols) and (n2 in p_cols):
                p1 = df_p[p_cols[n1]].astype(float)
                p2 = df_p[p_cols[n2]].astype(float)
                try:
                    dp_peak = float(np.nanmax(np.abs(p1 - p2)))
                except Exception:
                    dp_peak = float('nan')

                if idx_m is None:
                    try:
                        idx_m = int(np.nanargmax(np.abs((p1 - p2).to_numpy())))
                    except Exception:
                        idx_m = 0
                try:
                    pu = float(p1.iloc[idx_m])
                    p2i = float(p2.iloc[idx_m])
                    p_up_peak = max(pu, p2i)
                    p_dn_peak = min(pu, p2i)
                except Exception:
                    pass

        # C_req estimate
        C_use = safe_float(C, default=float('nan'))
        b_use = safe_float(b, default=iso_b_def)
        m_use = safe_float(m, default=iso_m_def)

        C_req = float('nan')
        if np.isfinite(mdot_peak) and np.isfinite(p_up_peak) and np.isfinite(p_dn_peak):
            C_req = compute_C_req_from_mdot(model, p_up_peak, p_dn_peak, mdot_peak, b_use, m_use, beta_lam, T_up=float(params.get('T_AIR', 293.15)))

        margin_C = float('nan')
        if np.isfinite(C_use) and np.isfinite(C_req) and (C_req > 0.0):
            margin_C = C_use / C_req

        # Диапазон доступного C для регулируемых элементов (например, SCO):
        C_min = getattr(e, 'C_min', None)
        C_max = getattr(e, 'C_max', None)
        alpha = getattr(e, 'alpha', None)
        C_max_use = safe_float(C_max, default=C_use)
        margin_C_max = float('nan')
        if np.isfinite(C_max_use) and np.isfinite(C_req) and (C_req > 0.0):
            margin_C_max = C_max_use / C_req

        sizing_hint = ''
        if np.isfinite(C_req):
            if np.isfinite(margin_C_max) and (margin_C_max >= 1.0) and (not (np.isfinite(margin_C) and margin_C >= 1.0)):
                sizing_hint = 'Можно увеличить открытие/коэф. прохода (C_max достаточен)'
            elif np.isfinite(margin_C_max) and (margin_C_max < 1.0):
                sizing_hint = 'Компонент маловат даже на максимуме — нужен больший типоразмер'

        family = infer_family_from_code(str(cam or ''))
        suggested = []
        if (passport_norm is not None) and family and np.isfinite(C_req):
            suggested = suggest_replacements(passport_norm, family, C_req, factor=1.2, limit=5)

        rows.append({
            'edge': name,
            'kind': kind,
            'camozzi': cam,
            'E_diss_J': E_map.get(name, float('nan')),
            'mdot_peak_kg_s': mdot_peak,
            'dp_peak_Pa': dp_peak,
            'C_iso_m3_s_Pa': C_use,
            'b': b_use,
            'm': m_use,
            'C_req_m3_s_Pa': C_req,
            'margin_C': margin_C,
                    'C_min_m3_s_Pa': safe_float(C_min, default=float('nan')) if C_min is not None else float('nan'),
            'C_max_m3_s_Pa': safe_float(C_max, default=float('nan')) if C_max is not None else float('nan'),
            'alpha': safe_float(alpha, default=float('nan')) if alpha is not None else float('nan'),
            'margin_C_max': margin_C_max,
            'sizing_hint': sizing_hint,
            'suggested_replacements': suggested,
        })

    df = pd.DataFrame(rows)
    if 'E_diss_J' in df.columns:
        df['E_diss_J'] = pd.to_numeric(df['E_diss_J'], errors='coerce')
    df = df.sort_values(['E_diss_J','margin_C'], ascending=[False, True], na_position='last').reset_index(drop=True)
    return df, info



def build_recommendations(df: pd.DataFrame, top: int = 20) -> dict:
    """Сформировать список рекомендаций на основе таблицы по рёбрам."""
    rec = {
        'critical': [],
        'needs_measurement': [],
        'notes': [],
    }
    if df.empty:
        rec['notes'].append('Нет данных по рёбрам (проверьте, что simulate() возвращает df_p/df_mdot/df_energy_edges).')
        return rec

    # Критичные: высокая энергия и маленький запас по C
    df2 = df.copy()
    df2['E_diss_J'] = pd.to_numeric(df2.get('E_diss_J', pd.Series([np.nan]*len(df2))), errors='coerce')
    df2['margin_C'] = pd.to_numeric(df2.get('margin_C', pd.Series([np.nan]*len(df2))), errors='coerce')

    crit = df2[(df2['E_diss_J'].fillna(0.0) > 1.0) & (df2['margin_C'].fillna(999.0) < 0.8)].head(top)
    for _,r in crit.iterrows():
        hint = str(r.get('sizing_hint', '') or '')
        repl = r.get('suggested_replacements', [])
        repl_txt = ''
        if isinstance(repl, list) and repl:
            try:
                codes = [str(it.get('code')) for it in repl[:3] if isinstance(it, dict) and it.get('code')]
                if codes:
                    repl_txt = 'Кандидаты по паспорту: ' + ', '.join(codes)
            except Exception:
                repl_txt = ''

        sug = 'Увеличить проход (C или A) либо пересмотреть топологию (параллель/байпас), если это не сознательное демпфирование.'
        if hint:
            sug = hint + '. ' + sug
        if repl_txt:
            sug = sug + ' ' + repl_txt + '.'

        rec['critical'].append({
            'edge': r['edge'],
            'camozzi': r.get('camozzi', None),
            'kind': r.get('kind', None),
            'E_diss_J': safe_float(r.get('E_diss_J', float('nan'))),
            'margin_C': safe_float(r.get('margin_C', float('nan'))),
            'margin_C_max': safe_float(r.get('margin_C_max', float('nan'))),
            'suggestion': sug
        })

    # Требуют измерения/паспортов: camozzi есть, но C_iso отсутствует
    miss = df2[df2['camozzi'].notna() & (pd.to_numeric(df2['C_iso_m3_s_Pa'], errors='coerce').isna())].head(top)
    for _,r in miss.iterrows():
        rec['needs_measurement'].append({
            'edge': r['edge'],
            'camozzi': r.get('camozzi', None),
            'kind': r.get('kind', None),
            'suggestion': 'Нужен паспорт (ISO6358 C,b,m) или кривая расхода; сейчас используется автооценка/площадь.'
        })

    return rec


def run_cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='default_base.json')
    ap.add_argument('--model', default='model_pneumo_v8_energy_audit_vacuum.py')
    ap.add_argument('--test', default='baseline')
    ap.add_argument('--dt', type=float, default=0.001)
    ap.add_argument('--t_end', type=float, default=2.0)
    ap.add_argument('--out', default='design_advisor_out')
    args = ap.parse_args()

    base_path = (HERE / args.base).resolve()
    model_path = (HERE / args.model).resolve()

    params = json.loads(base_path.read_text(encoding='utf-8'))

    model = load_py_module(model_path, 'pneumo_model')

    # Minimal baseline test
    if args.test == 'baseline':
        test = {}
    else:
        # Load from suite if needed
        test = {}

    df, info = analyze_one_run(model, params, test, dt=float(args.dt), t_end=float(args.t_end))
    rec = build_recommendations(df)

    out_dir = (HERE / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_dir / 'design_advisor_edges.csv', index=False)
    (out_dir / 'design_advisor_recommendations.json').write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding='utf-8')

    md = []
    md.append(f"# Design Advisor\n\n")
    md.append(f"- Дата: {datetime.now().isoformat(timespec='seconds')}\n")
    md.append(f"- Base: `{base_path.name}`\n")
    md.append(f"- Model: `{model_path.name}`\n")
    md.append(f"- dt={args.dt}, t_end={args.t_end}\n\n")

    if rec['critical']:
        md.append("## Критичные ограничения по проходу (energy high + margin_C<0.8)\n")
        for it in rec['critical']:
            md.append(f"- **{it['edge']}** ({it.get('camozzi','')}, {it.get('kind','')}): E≈{it['E_diss_J']:.2f} J, margin_C≈{it['margin_C']:.2f}\n")
    else:
        md.append("## Критичные ограничения\n\nНе найдено по текущим порогам.\n")

    md.append("\n## Файлы\n")
    md.append("- design_advisor_edges.csv — таблица по рёбрам\n")
    md.append("- design_advisor_recommendations.json — рекомендации (машиночитаемо)\n")

    (out_dir / 'DESIGN_ADVISOR.md').write_text(''.join(md), encoding='utf-8')

    print(f"OK: {out_dir}")
    return 0


if __name__ == '__main__':
    raise SystemExit(run_cli())
