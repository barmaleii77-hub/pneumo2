# -*- coding: utf-8 -*-

import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pneumo_solver_ui.iso6358_core import iso6358_phi


def test_phi_pr_le_zero_is_choked():
    # Вакуум / численная ошибка: pr<=0 -> choked -> phi=1
    assert abs(iso6358_phi(0.0, 0.3, 0.5) - 1.0) < 1e-12
    assert abs(iso6358_phi(-0.1, 0.3, 0.5) - 1.0) < 1e-12


def test_phi_pr_ge_one_is_zero():
    assert abs(iso6358_phi(1.0, 0.3, 0.5) - 0.0) < 1e-12
    assert abs(iso6358_phi(1.1, 0.3, 0.5) - 0.0) < 1e-12


def test_phi_choked_region_pr_le_b_is_one():
    b = 0.4
    for pr in [0.0, 0.1, b, b * 0.999]:
        assert abs(iso6358_phi(pr, b, 0.5) - 1.0) < 1e-12


def test_phi_subsonic_is_between_0_and_1():
    b = 0.4
    for pr in [0.5, 0.7, 0.9]:
        phi = iso6358_phi(pr, b, 0.5)
        assert 0.0 <= phi <= 1.0
