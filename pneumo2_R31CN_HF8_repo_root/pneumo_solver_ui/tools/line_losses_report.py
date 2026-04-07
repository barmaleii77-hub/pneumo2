#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""line_losses_report.py

Отчёт по применённым "потерям линий" (шланги/фитинги) — см. pneumo_solver_ui/line_losses.py.

Зачем:
- быстро увидеть, какие рёбра сети подпали под ruleset из lines_map_default.json;
- получить таблицу с фактором (0..1), длиной, диаметром, количеством фитингов;
- как следствие — понять, где узкое место можно лечить увеличением D или сокращением L.

Запуск:
    python -m pneumo_solver_ui.tools.line_losses_report

Параметры:
- default_base.json (line_losses_enable, line_losses_json, line_losses_Klen/Kfit/...)
"""

from __future__ import annotations

import json
import sys
import importlib.util
from pathlib import Path


def _load_json(path: Path):
    return json.loads(path.read_text('utf-8'))


def _load_model_from_fingerprint(root: Path):
    # 1) scheme_fingerprint meta.model_file
    fp = root / 'scheme_fingerprint.json'
    candidates = []
    if fp.exists():
        try:
            meta = json.loads(fp.read_text('utf-8')).get('meta', {})
            mf = meta.get('model_file')
            if mf:
                p = Path(mf)
                if not p.is_absolute():
                    p = root / p
                candidates.append(p)
        except Exception:
            pass

    # 2) fallbacks
    candidates += [
        root / 'model_pneumo_v9_doublewishbone_camozzi.py',
        root / 'model_pneumo_v9_mech_doublewishbone_worldroad.py',
        root / 'model_pneumo_v8_energy_audit_vacuum.py',
    ]

    for p in candidates:
        if not p.exists():
            continue
        spec = importlib.util.spec_from_file_location('model_mod', str(p))
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore
        return mod, p

    raise RuntimeError('No suitable model file found')


def main() -> int:
    root = Path(__file__).resolve().parents[1]  # .../pneumo_solver_ui
    base = _load_json(root / 'default_base.json')

    # Ensure enabled
    base['line_losses_enable'] = True

    try:
        model, model_path = _load_model_from_fingerprint(root)
    except Exception as ex:
        print(f"[line_losses_report] ERROR: cannot load model: {ex}")
        return 2

    try:
        # build_network_full mutates base (adds _line_losses_report)
        model.build_network_full(base)
        rep = base.get('_line_losses_report', {})
    except Exception as ex:
        print(f"[line_losses_report] ERROR: build_network_full failed: {ex}")
        return 3

    enabled = bool(rep.get('enabled', False))
    if not enabled:
        print(f"[line_losses_report] line_losses not enabled or failed. model={model_path}")
        if rep.get('error'):
            print(f"error: {rep['error']}")
        return 1

    affected = rep.get('affected', []) or []
    print(f"# Line losses report\n")
    print(f"Model: {model_path.name}")
    print(f"Map: {rep.get('map_file', 'n/a')}")
    print(f"Klen={rep.get('Klen')}  Kfit={rep.get('Kfit')}  min_factor={rep.get('min_factor')}\n")

    if not affected:
        print("No edges matched any segment rules.")
        return 0

    print("| edge | factor | L_m | D_mm | n_fittings | note |")
    print("|---|---:|---:|---:|---:|---|")
    for a in affected:
        name = str(a.get('edge', ''))
        factor = float(a.get('factor', 1.0))
        L_m = a.get('L_m')
        D_mm = a.get('D_mm')
        nf = a.get('n_fittings')
        note = str(a.get('note', ''))
        print(f"| {name} | {factor:.3f} | {L_m} | {D_mm} | {nf} | {note} |")

    return 0


if __name__ == '__main__':
    sys.exit(main())
