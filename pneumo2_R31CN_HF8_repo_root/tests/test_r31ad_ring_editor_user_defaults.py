from __future__ import annotations

import ast
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / 'pneumo_solver_ui' / 'ui_scenario_ring.py'
SRC = SRC_PATH.read_text(encoding='utf-8')


def _default_spec_literal() -> dict:
    mod = ast.parse(SRC)
    for node in mod.body:
        if isinstance(node, ast.FunctionDef) and node.name == '_default_ring_spec':
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and target.id == 'spec':
                            return ast.literal_eval(stmt.value)
    raise AssertionError('spec literal in _default_ring_spec not found')


def test_ring_default_spec_matches_latest_user_setup() -> None:
    spec = _default_spec_literal()
    assert spec['closure_policy'] == 'closed_c1_periodic'
    assert spec['v0_kph'] == 40.0
    assert spec['seed'] == 123
    assert spec['dx_m'] == 0.02
    assert spec['dt_s'] == 0.01
    assert spec['n_laps'] == 1
    assert len(spec['segments']) == 4

    s1, s2, s3, s4 = spec['segments']
    assert s1['road']['mode'] == 'ISO8608'
    assert s1['road']['iso_class'] == 'E'
    assert s2['road']['mode'] == 'SINE'
    assert s2['road']['aL_mm'] == 50.0
    assert s2['road']['aR_mm'] == 50.0
    assert s2['road']['lambdaL_m'] == 1.5
    assert s2['road']['lambdaR_m'] == 1.5
    assert s2['road']['phaseR_deg'] == 180.0
    assert s2['road']['rand_pL'] is True
    assert s2['road']['rand_pR'] is True
    assert s3['road']['iso_class'] == 'E'
    assert s4['road']['iso_class'] == 'E'


def test_ring_editor_lap_default_comes_from_spec_not_magic_three() -> None:
    assert 'value=int(st.session_state.get("ring_n_laps", spec.get("n_laps", 1)))' in SRC
