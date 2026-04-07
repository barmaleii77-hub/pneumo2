# -*- coding: utf-8 -*-
"""pipeline_npz_oneclick_v1.py

Один запуск -> полный пайплайн калибровки по NPZ-логам из UI:
  1) инспектируем osc_dir, определяем time_col
  2) (опционально) генерируем mapping (minimal/main_all/extended)
  3) (опционально) выбираем holdout тесты по доле
  4) запускаем fit_worker_v3_suite_identify.py
  5) генерируем markdown отчёт из fit_details.json
  6) (опционально) запускаем profile likelihood по выбранным параметрам

Скрипт намеренно сделан как "orchestrator" через subprocess, чтобы:
- не зависеть от внутренней структуры воркеров,
- быть устойчивым к изменениям кода в fit/profile/oed.

Пример:
  python calibration/pipeline_npz_oneclick_v1.py --osc_dir osc_logs/RUN_... \
      --mode extended --auto_scale mad --holdout_frac 0.2

"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _load_json(path: Path) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_json(obj: Any, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _run(cmd: List[str], cwd: Optional[Path] = None):
    print('\n>>>', ' '.join(cmd))
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)


def _read_tests_index(osc_dir: Path) -> List[str]:
    import pandas as pd
    idx_path = osc_dir / 'tests_index.csv'
    if not idx_path.exists():
        raise FileNotFoundError(f'Не найден {idx_path}')
    df = pd.read_csv(idx_path, encoding='utf-8-sig')
    if 'имя_теста' not in df.columns:
        raise RuntimeError(f"tests_index.csv не содержит 'имя_теста'. Есть: {list(df.columns)}")
    return [str(x) for x in df['имя_теста'].tolist()]


def _choose_holdout(tests: List[str], frac: float, seed: int) -> List[str]:
    tests_u = list(dict.fromkeys([t.strip() for t in tests if t.strip()]))
    if not tests_u:
        return []
    k = int(round(len(tests_u) * float(frac)))
    k = max(0, min(k, len(tests_u)))
    rng = random.Random(int(seed))
    rng.shuffle(tests_u)
    return sorted(tests_u[:k])


def main():
    ap = argparse.ArgumentParser()

    # core I/O
    ap.add_argument('--osc_dir', required=True, help='Папка RUN_... с tests_index.csv и Txx_osc.npz')
    ap.add_argument('--out_dir', default='', help='Куда сложить результаты (по умолчанию calibration_runs/RUN_YYYYMMDD_HHMMSS)')

    # project files (defaults assume запуск из корня проекта)
    ap.add_argument('--model', default='model_pneumo_v8_energy_audit_vacuum_patched_smooth_all.py')
    ap.add_argument('--worker', default='opt_worker_v3_margins_energy.py')
    ap.add_argument('--suite_json', default='default_suite.json')
    ap.add_argument('--base_json', default='default_base.json')
    ap.add_argument('--fit_ranges_json', default='default_ranges.json')

    # mapping
    ap.add_argument('--mapping_json', default='', help='Если задано — используем его, иначе генерируем автоматически')
    ap.add_argument('--signals_csv', default='', help='Если задано — mapping генерируется из signals.csv (meas_table/meas_col/model_key/w_raw)')
    ap.add_argument('--mode', default='minimal', help='Режим автогенерации mapping: minimal/main_all/extended')
    ap.add_argument('--time_col', default='auto')

    # fit options
    ap.add_argument('--loss', default='soft_l1')
    ap.add_argument('--f_scale', type=float, default=1.0)
    ap.add_argument('--n_init', type=int, default=32)
    ap.add_argument('--n_best', type=int, default=6)
    ap.add_argument('--max_nfev', type=int, default=220)
    ap.add_argument('--record_stride', type=int, default=1)
    ap.add_argument('--use_smoothing_defaults', action='store_true')

    ap.add_argument('--auto_scale', default='mad', help='none/mad/std/range')

    # holdout
    ap.add_argument('--holdout_tests', default='', help='Список тестов через запятую')
    ap.add_argument('--holdout_frac', type=float, default=0.0, help='Доля holdout тестов (0..1), если holdout_tests не задан')
    ap.add_argument('--holdout_seed', type=int, default=1)

    # profile
    ap.add_argument('--run_profile', action='store_true', help='Запустить profile likelihood после fit')
    ap.add_argument('--profile_params', default='', help='Список параметров через запятую. Если пусто — возьмём топ-3 по std (если cov доступна).')
    ap.add_argument('--profile_span', type=float, default=0.35)
    ap.add_argument('--profile_n_points', type=int, default=21)

    args = ap.parse_args()

    osc_dir = Path(args.osc_dir)
    if not osc_dir.exists():
        raise SystemExit(f'osc_dir не существует: {osc_dir}')

    project_root = Path('.')

    # output folder
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        ts = time.strftime('%Y%m%d_%H%M%S')
        out_dir = project_root / 'calibration_runs' / f'RUN_{ts}'
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- quick sanity of osc_dir -------------------------------------------------
    # Пользователь часто по ошибке передаёт --osc_dir . (корень проекта),
    # или запускает пайплайн до того, как сохранены осциллограммы.
    # В таких случаях лучше завершиться «мягко»: создать out_dir, положить подсказки,
    # и не поднимать CalledProcessError (UI/автопилот это воспринимают как авар...
    npz_files = sorted(osc_dir.glob('T*_osc.npz'))
    if not npz_files:
        mapping_path = out_dir / 'mapping_auto.json'
        if not mapping_path.exists():
            try:
                tpl = (project_root / 'calibration' / 'mapping_npz_extended_template.json').read_text(encoding='utf-8')
                mapping_path.write_text(tpl, encoding='utf-8')
            except Exception:
                mapping_path.write_text(json.dumps({"__comment": "template (no NPZ)"}, ensure_ascii=False, indent=2), encoding='utf-8')

        hint = out_dir / 'NO_NPZ_FOUND.md'
        hint.write_text(
            "# NPZ logs not found\n\n"
            f"osc_dir: `{osc_dir}`\n\n"
            "В папке не найден ни один файл вида `T01_osc.npz`.\n\n"
            "Что сделать:\n"
            "1. Передайте правильный путь: папка, где лежат `tests_index.csv` и `Txx_osc.npz`.\n"
            "2. Если у вас другой формат, сначала экспортируйте/соберите NPZ.\n\n"
            "Пайплайн завершён без ошибок, чтобы UI мог показать подсказки.\n",
            encoding='utf-8',
        )
        print(f"[WARN] NPZ logs not found in osc_dir: {osc_dir}. Wrote template mapping: {mapping_path} and hint: {hint}")
        return 0

    # mapping
    if args.mapping_json:
        mapping_path = Path(args.mapping_json)
    else:
        mapping_path = out_dir / 'mapping_auto.json'
        if args.signals_csv:
            # mapping из signals.csv
            _run([
                sys.executable,
                str(project_root / 'calibration' / 'signals_csv_to_mapping_v1.py'),
                '--signals_csv', str(Path(args.signals_csv)),
                '--out_mapping', str(mapping_path),
                '--osc_dir', str(osc_dir),
                '--test_num', '1',
                '--drop_missing',
            ], cwd=project_root)
        else:
            # эвристическая автогенерация по NPZ
            _run([
                sys.executable,
                str(project_root / 'calibration' / 'npz_autosuggest_mapping_v2.py'),
                '--osc_dir', str(osc_dir),
                '--test_num', '1',
                '--mode', str(args.mode),
                '--out_mapping', str(mapping_path),
            ], cwd=project_root)

    # holdout list
    holdout_tests = [s.strip() for s in str(args.holdout_tests).split(',') if s.strip()]
    if (not holdout_tests) and float(args.holdout_frac) > 0.0:
        tests = _read_tests_index(osc_dir)
        holdout_tests = _choose_holdout(tests, frac=float(args.holdout_frac), seed=int(args.holdout_seed))

    holdout_arg = ','.join(holdout_tests)
    _save_json({'holdout_tests': holdout_tests}, out_dir / 'holdout_selection.json')

    # fit
    fit_out = out_dir / 'fitted_base.json'
    fit_report = out_dir / 'fit_report.json'
    fit_details = out_dir / 'fit_details.json'

    fit_cmd = [
        sys.executable, str(project_root / 'calibration' / 'fit_worker_v3_suite_identify.py'),
        '--model', str(project_root / args.model),
        '--worker', str(project_root / args.worker),
        '--suite_json', str(project_root / args.suite_json),
        '--osc_dir', str(osc_dir),
        '--base_json', str(project_root / args.base_json),
        '--fit_ranges_json', str(project_root / args.fit_ranges_json),
        '--mapping_json', str(mapping_path),
        '--time_col', str(args.time_col),
        '--n_init', str(int(args.n_init)),
        '--n_best', str(int(args.n_best)),
        '--loss', str(args.loss),
        '--f_scale', str(float(args.f_scale)),
        '--max_nfev', str(int(args.max_nfev)),
        '--record_stride', str(int(args.record_stride)),
        '--auto_scale', str(args.auto_scale),
        '--details_json', str(fit_details),
        '--out_json', str(fit_out),
        '--report_json', str(fit_report),
    ]
    if holdout_arg:
        fit_cmd += ['--holdout_tests', holdout_arg]
    if args.use_smoothing_defaults:
        fit_cmd += ['--use_smoothing_defaults']

    _run(fit_cmd, cwd=project_root)

    # report markdown
    out_md = out_dir / 'report.md'
    _run([
        sys.executable, str(project_root / 'calibration' / 'report_from_details_v1.py'),
        '--fit_report', str(fit_report),
        '--fit_details', str(fit_details),
        '--out_md', str(out_md),
        '--out_tests_csv', str(out_dir / 'tests.csv'),
        '--out_signals_csv', str(out_dir / 'signals.csv'),
    ], cwd=project_root)

    # optional: profile
    if args.run_profile:
        prof_dir = out_dir / 'profile_out'
        prof_dir.mkdir(parents=True, exist_ok=True)
        prof_json = out_dir / 'profile_report.json'

        profile_params = [s.strip() for s in str(args.profile_params).split(',') if s.strip()]
        if not profile_params:
            # try to pick top-3 by std from cov
            try:
                rep = _load_json(fit_report)
                keys = rep.get('keys', [])
                cov = rep.get('cov')
                if keys and cov is not None:
                    import numpy as np
                    cov_arr = np.asarray(cov, dtype=float)
                    if cov_arr.ndim == 2 and cov_arr.shape[0] == cov_arr.shape[1] == len(keys):
                        std = np.sqrt(np.clip(np.diag(cov_arr), 0.0, np.inf))
                        order = list(np.argsort(-std))
                        profile_params = [str(keys[i]) for i in order[: min(3, len(keys))] if np.isfinite(std[i]) and std[i] > 0]
            except Exception:
                profile_params = []

        if profile_params:
            _run([
                sys.executable, str(project_root / 'calibration' / 'profile_worker_v1_likelihood.py'),
                '--model', str(project_root / args.model),
                '--worker', str(project_root / args.worker),
                '--suite_json', str(project_root / args.suite_json),
                '--osc_dir', str(osc_dir),
                '--theta_star_json', str(fit_out),
                '--fit_ranges_json', str(project_root / args.fit_ranges_json),
                '--mapping_json', str(mapping_path),
                '--time_col', str(args.time_col),
                '--profile_params', ','.join(profile_params),
                '--span', str(float(args.profile_span)),
                '--n_points', str(int(args.profile_n_points)),
                '--loss', 'linear',
                '--out_json', str(prof_json),
                '--out_dir', str(prof_dir),
            ] + (['--use_smoothing_defaults'] if args.use_smoothing_defaults else []), cwd=project_root)
        else:
            print('run_profile: пропущено, не удалось выбрать параметры')

    print('\nDONE. Outputs in:', out_dir)


if __name__ == '__main__':
    main()
