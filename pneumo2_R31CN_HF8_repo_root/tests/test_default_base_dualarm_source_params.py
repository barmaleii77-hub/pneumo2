from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = ROOT / "pneumo_solver_ui" / "default_base.json"


REQUIRED_KEYS = (
    "dw_upper_pivot_inboard_перед_м",
    "dw_upper_pivot_inboard_зад_м",
    "dw_upper_pivot_z_перед_м",
    "dw_upper_pivot_z_зад_м",
    "dw_upper_arm_len_перед_м",
    "dw_upper_arm_len_зад_м",
)
REQUIRED_AUTOVERIF_PACKAGING_KEYS = (
    "autoverif_packaging_enabled",
    "autoverif_spring_host_min_clearance_m",
    "autoverif_spring_pair_min_clearance_m",
    "autoverif_spring_cap_min_margin_m",
    "autoverif_midstroke_t0_max_error_m",
    "autoverif_coilbind_min_margin_m",
)


def test_default_base_declares_upper_arm_source_data_keys() -> None:
    data = json.loads(DEFAULT_BASE.read_text(encoding="utf-8"))
    for key in REQUIRED_KEYS:
        assert key in data, key
        assert isinstance(data[key], (int, float)), key


def test_default_base_declares_packaging_autoverif_defaults() -> None:
    data = json.loads(DEFAULT_BASE.read_text(encoding="utf-8"))
    for key in REQUIRED_AUTOVERIF_PACKAGING_KEYS:
        assert key in data, key
