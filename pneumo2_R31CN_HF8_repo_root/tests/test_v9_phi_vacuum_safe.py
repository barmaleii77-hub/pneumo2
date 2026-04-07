# -*- coding: utf-8 -*-

import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_v9_camozzi_phi_is_vacuum_safe():
    import pneumo_solver_ui.model_pneumo_v9_doublewishbone_camozzi as m

    phi0 = float(m.iso6358_phi(0.0, 0.5, m=0.6))
    phineg = float(m.iso6358_phi(-0.1, 0.5, m=0.6))
    assert phi0 > 0.99
    assert phineg > 0.99


def test_v9_reference_phi_is_vacuum_safe():
    import pneumo_solver_ui.model_pneumo_v9_mech_doublewishbone_r48_reference as m

    phi0 = float(m.iso6358_phi(0.0, 0.5, m=0.6))
    phineg = float(m.iso6358_phi(-0.1, 0.5, m=0.6))
    assert phi0 > 0.99
    assert phineg > 0.99
