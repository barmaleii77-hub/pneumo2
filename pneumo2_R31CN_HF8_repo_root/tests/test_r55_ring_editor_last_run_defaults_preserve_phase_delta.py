from __future__ import annotations

import ast
from pathlib import Path

import numpy as np

from pneumo_solver_ui.scenario_ring import generate_ring_tracks

ROOT = Path(__file__).resolve().parents[1]
UI_SRC = (ROOT / 'pneumo_solver_ui' / 'ui_scenario_ring.py').read_text(encoding='utf-8')


def _default_spec_literal() -> dict:
    mod = ast.parse(UI_SRC)
    for node in mod.body:
        if isinstance(node, ast.FunctionDef) and node.name == '_default_ring_spec':
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and target.id == 'spec':
                            return ast.literal_eval(stmt.value)
    raise AssertionError('spec literal in _default_ring_spec not found')


def test_last_run_default_turn_segment_keeps_explicit_180deg_left_right_phase_delta() -> None:
    spec = _default_spec_literal()
    s2 = dict(spec['segments'][1])
    road = dict(s2['road'])

    assert road['phaseL_deg'] == 0.0
    assert road['phaseR_deg'] == 180.0
    assert road['rand_pL'] is True
    assert road['rand_pR'] is True
    assert road['rand_pL_p'] == 0.5
    assert road['rand_pR_p'] == 0.5

    single = {
        'v0_kph': float(spec['v0_kph']),
        'dx_m': float(spec['dx_m']),
        'segments': [
            {
                'drive_mode': 'STRAIGHT',
                'length_m': 3.0,
                'speed_kph': 40.0,
                'road': road,
            }
        ],
    }
    tracks = generate_ring_tracks(single, dx_m=float(spec['dx_m']), seed=int(spec['seed']))
    z_left = np.asarray(tracks['zL_m'], dtype=float)
    z_right = np.asarray(tracks['zR_m'], dtype=float)

    # The latest accepted ring-editor defaults intentionally keep the last Windows run
    # phase-randomization toggles enabled. The generator fix must therefore preserve the
    # authored 180° anti-phase relation instead of silently replacing it with an RNG delta.
    assert z_left.shape == z_right.shape
    assert np.max(np.abs(z_left + z_right)) <= 1e-9
