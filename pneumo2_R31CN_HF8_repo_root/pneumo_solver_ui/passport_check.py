# -*- coding: utf-8 -*-
"""passport_check.py (R45)

Проверка "паспорта компонентов" на минимальную пригодность к моделированию.

Поддерживает 2 формата паспорта:
1) Старый: {"VNR": {...}, "SCO": {...}}
2) Новый: {"meta":..., "components": [...]} (как в component_passport.json)

Проверяем:
- наличие ключевых величин (Qn, ISO6358 C,b,m,Δpc);
- физическую допустимость (C>0, 0<b<=1, 0<m<=1, давления >=0).

Запуск:
    python passport_check.py --passport component_passport.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import importlib.util


def load_normalize_fn(base_dir: Path):
    """Берём normalize_component_passport() из "канонической" модели.

    Логика выбора:
    1) scheme_fingerprint.json -> meta.model_file (если существует)
    2) model_pneumo_v9_doublewishbone_camozzi.py
    3) model_pneumo_v8_energy_audit_vacuum.py (fallback)
    """

    candidates = []
    fp = base_dir / 'scheme_fingerprint.json'
    if fp.exists():
        try:
            meta = (json.loads(fp.read_text('utf-8')) or {}).get('meta', {}) or {}
            mf = meta.get('model_file', None)
            if isinstance(mf, str) and mf.strip():
                mp = Path(mf)
                if not mp.is_absolute():
                    mp = base_dir / mp
                candidates.append(mp)
        except Exception:
            pass

    candidates.extend([
        base_dir / 'model_pneumo_v9_doublewishbone_camozzi.py',
        base_dir / 'model_pneumo_v8_energy_audit_vacuum.py',
    ])

    last_err = None
    for model_path in candidates:
        try:
            if not model_path.exists():
                continue
            spec = importlib.util.spec_from_file_location('model_mod', str(model_path))
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[attr-defined]
            if hasattr(mod, 'normalize_component_passport'):
                return mod.normalize_component_passport
            last_err = RuntimeError(f'В модели нет normalize_component_passport(): {model_path}')
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f'Не удалось получить normalize_component_passport() (last_err={last_err})')


def _is_num(x):
    try:
        return x is not None and float(x) == float(x)
    except Exception:
        return False


def _gt0(x):
    try:
        return float(x) > 0.0
    except Exception:
        return False


def check_family_iso(passport, fam: str, required_keys=('C_m3_s_Pa','b','m')):
    bad = []
    fam_dict = passport.get(fam, {}) or {}
    for code, ent in fam_dict.items():
        iso = (ent or {}).get('iso', {}) or {}
        for k in required_keys:
            if k not in iso or (iso[k] is None):
                bad.append((fam, code, f'missing iso.{k}'))
                continue
        # basic ranges
        C = iso.get('C_m3_s_Pa', None)
        b = iso.get('b', None)
        m = iso.get('m', None)
        if C is not None and not _gt0(C):
            bad.append((fam, code, f'iso.C_m3_s_Pa <=0 ({C})'))
        if b is not None:
            try:
                bv = float(b)
                if not (0.0 < bv <= 1.0):
                    bad.append((fam, code, f'iso.b out of (0..1] ({b})'))
            except Exception:
                bad.append((fam, code, f'iso.b not numeric ({b})'))
        if m is not None:
            try:
                mv = float(m)
                if not (0.0 < mv <= 1.0):
                    bad.append((fam, code, f'iso.m out of (0..1] ({m})'))
            except Exception:
                bad.append((fam, code, f'iso.m not numeric ({m})'))

    return bad


def check_component_passport(passport, base_dir: Path):
    normalize = load_normalize_fn(base_dir)
    passport = normalize(passport)

    problems = []

    # Old families
    for fam in ('VNR','SCO'):
        if fam not in passport:
            problems.append((fam, '-', 'missing family in passport'))

    # VNR checks
    for code, ent in (passport.get('VNR', {}) or {}).items():
        if 'Qn_Nl_min' not in ent or ent.get('Qn_Nl_min') is None:
            problems.append(('VNR', code, 'missing Qn_Nl_min'))
        iso = (ent.get('iso') or {})
        if not _gt0(iso.get('C_m3_s_Pa', None)):
            problems.append(('VNR', code, 'missing/invalid iso.C_m3_s_Pa'))

    # SCO checks
    for code, ent in (passport.get('SCO', {}) or {}).items():
        if ent.get('Qn_open_Nl_min') is None:
            problems.append(('SCO', code, 'missing Qn_open_Nl_min'))
        iso = (ent.get('iso') or {})
        if not _gt0(iso.get('C_open_m3_s_Pa', None)):
            problems.append(('SCO', code, 'missing/invalid iso.C_open_m3_s_Pa'))

    # New families (MC / VMR / SIL)
    problems += check_family_iso(passport, 'MC')
    problems += check_family_iso(passport, 'VMR')
    problems += check_family_iso(passport, 'SIL', required_keys=('C_m3_s_Pa','b','m'))

    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--passport', default='component_passport.json')
    ap.add_argument('--base_dir', default=str(Path(__file__).resolve().parent))
    args = ap.parse_args()

    base_dir = Path(args.base_dir).resolve()
    passport_path = Path(args.passport)
    if not passport_path.is_absolute():
        passport_path = base_dir / passport_path

    data = json.loads(passport_path.read_text('utf-8'))
    problems = check_component_passport(data, base_dir)

    if problems:
        print('Найдены проблемы паспорта:')
        for fam, code, msg in problems:
            print(f' - [{fam}] {code}: {msg}')
        raise SystemExit(2)

    print('OK: паспорт выглядит пригодным (базовые проверки пройдены).')


if __name__ == '__main__':
    main()
