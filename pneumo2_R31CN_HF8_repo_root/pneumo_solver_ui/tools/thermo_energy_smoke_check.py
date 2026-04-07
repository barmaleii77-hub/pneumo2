# -*- coding: utf-8 -*-
"""thermo_energy_smoke_check.py

Быстрая проверка термодинамической части v8-модели:
- баланс внутренней энергии газа (ошибка_энергии_газа_отн)
- неотрицательность генерации энтропии смешения (энтропия_смешение_Дж_К)
- контракт record_full: model.simulate(..., record_full=True) -> 11 элементов

Запуск (из корня проекта):
    python -m pneumo_solver_ui.tools.thermo_energy_smoke_check
или (из папки pneumo_solver_ui):
    python tools/thermo_energy_smoke_check.py

Коды возврата:
 0 - PASS
 2 - FAIL (пороговые условия не выполнены)
 3 - ERROR (исключение)

Env:
- PNEUMO_THERMO_E_REL_MAX   (default 1e-3)
- PNEUMO_THERMO_TEND        (default 0.2)
- PNEUMO_THERMO_DT          (default 0.01)
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _fenv(name: str, default: float) -> float:
    try:
        return float(str(os.environ.get(name, default)).strip())
    except Exception:
        return float(default)


def main(argv: list[str] | None = None) -> int:
    try:
        # Надёжно находим корень pneumo_solver_ui независимо от способа запуска
        here = Path(__file__).resolve().parent
        root = here.parent

        # Импортируем как пакет, чтобы работали относительные импорты и ресурсы
        import sys
        if str(root.parent) not in sys.path:
            sys.path.insert(0, str(root.parent))

        from pneumo_solver_ui import opt_worker_v3_margins_energy as worker
        from pneumo_solver_ui import model_pneumo_v8_energy_audit_vacuum_patched_smooth_all as model

        base = json.loads((root / 'default_base.json').read_text(encoding='utf-8'))

        dt = _fenv('PNEUMO_THERMO_DT', 0.01)
        t_end = _fenv('PNEUMO_THERMO_TEND', 0.2)
        e_rel_max = _fenv('PNEUMO_THERMO_E_REL_MAX', 1e-3)

        test = worker.make_test_roll(t_step=0.05, ay=2.0)

        metrics = worker.eval_candidate_once(model, base, test, dt=dt, t_end=t_end)
        e_rel = float(metrics.get('ошибка_энергии_газа_отн', 1e9))
        s_mix = float(metrics.get('энтропия_смешение_Дж_К', -1e9))

        out_full = model.simulate(base, test, dt=dt, t_end=t_end, record_full=True)
        ok_full = isinstance(out_full, tuple) and len(out_full) == 11

        ok = (e_rel <= e_rel_max) and (s_mix >= -1e-9) and ok_full

        print(f"thermo_energy_smoke_check: e_rel={e_rel:.3e} (<= {e_rel_max:g}), S_mix={s_mix:.6g} (>=0), record_full_len={len(out_full) if isinstance(out_full, tuple) else '??'}")
        return 0 if ok else 2
    except Exception as e:  # noqa: BLE001
        print(f"thermo_energy_smoke_check: ERROR: {e}")
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
