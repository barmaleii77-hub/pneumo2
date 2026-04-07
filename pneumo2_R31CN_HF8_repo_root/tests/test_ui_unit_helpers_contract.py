from __future__ import annotations

from pathlib import Path

import pytest

from pneumo_solver_ui.ui_unit_helpers import (
    gauge_to_pa_abs,
    infer_plot_unit_and_transform,
    is_length_param_name,
    pa_abs_to_gauge,
    param_unit_label,
    si_to_ui_value,
    ui_to_si_value,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


def test_infer_plot_unit_and_transform_supports_atm_and_mm_modes() -> None:
    unit, transform, yaxis_title = infer_plot_unit_and_transform(
        "давление_узел_Па",
        pressure_unit_label="атм (изб.)",
        pressure_offset_pa=101325.0,
        pressure_divisor_pa=101325.0,
        length_unit_label="м",
        length_scale=1.0,
    )
    assert unit == "атм (изб.)"
    assert yaxis_title == "атм (изб.)"
    assert transform is not None
    assert transform(202650.0) == pytest.approx(1.0)

    length_unit, length_transform, length_yaxis = infer_plot_unit_and_transform(
        "координата_m",
        pressure_unit_label="бар (изб.)",
        pressure_offset_pa=101325.0,
        pressure_divisor_pa=100000.0,
        length_unit_label="мм",
        length_scale=1000.0,
    )
    assert length_unit == "мм"
    assert length_yaxis == "мм"
    assert length_transform is not None
    assert length_transform(0.25) == pytest.approx(250.0)


def test_pressure_and_ui_value_conversions_cover_legacy_and_bar_modes() -> None:
    assert pa_abs_to_gauge(201325.0, pressure_offset_pa=101325.0, pressure_divisor_pa=100000.0) == pytest.approx(1.0)
    assert gauge_to_pa_abs(1.5, pressure_offset_pa=101325.0, pressure_divisor_pa=100000.0) == pytest.approx(251325.0)

    assert si_to_ui_value("p", 201325.0, "pressure_bar_g", p_atm=101325.0, bar_pa=100000.0) == pytest.approx(1.0)
    assert si_to_ui_value("p", 202650.0, "pressure_atm_g", p_atm=101325.0, bar_pa=100000.0) == pytest.approx(1.0)
    assert si_to_ui_value("x", 0.123, "length_mm", p_atm=101325.0, bar_pa=100000.0) == pytest.approx(123.0)
    assert ui_to_si_value("p", 1.0, "pressure_bar_g", p_atm=101325.0, bar_pa=100000.0) == pytest.approx(201325.0)
    assert ui_to_si_value("p", 1.0, "pressure_atm_g", p_atm=101325.0, bar_pa=100000.0) == pytest.approx(202650.0)
    assert ui_to_si_value("x", 123.0, "length_mm", p_atm=101325.0, bar_pa=100000.0) == pytest.approx(0.123)


def test_param_unit_label_and_length_detection_match_ui_contract() -> None:
    assert is_length_param_name("колея") is True
    assert is_length_param_name("ход_штока") is True
    assert is_length_param_name("координата_m") is True
    assert is_length_param_name("давление_Pmax") is False

    unit = param_unit_label(
        "давление_Pmin_питание_Ресивер2",
        pressure_unit_label="бар (изб.)",
        is_pressure_param_fn=lambda name: name.startswith("давление_"),
        is_volume_param_fn=lambda name: name.startswith("объём_"),
        is_small_volume_param_fn=lambda name: name.endswith("линии"),
    )
    assert unit == "бар (изб.)"

    volume_unit = param_unit_label(
        "объём_линии",
        pressure_unit_label="бар (изб.)",
        is_pressure_param_fn=lambda name: False,
        is_volume_param_fn=lambda name: True,
        is_small_volume_param_fn=lambda name: True,
    )
    assert volume_unit == "мл"


def test_entrypoints_use_shared_unit_helpers_without_local_duplicates() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_unit_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_unit_helpers import (" in heavy_text

    for pattern in [
        "def _infer_unit_and_transform(",
        "def pa_abs_to_atm_g(",
        "def atm_g_to_pa_abs(",
        "def param_unit(",
        "def _si_to_ui(",
        "def _ui_to_si(",
    ]:
        assert pattern not in app_text

    for pattern in [
        "def _infer_unit_and_transform(",
        "def pa_abs_to_bar_g(",
        "def bar_g_to_pa_abs(",
        "def pa_abs_to_atm_g(",
        "def atm_g_to_pa_abs(",
        "def is_length_param(",
        "def param_unit(",
        "def _si_to_ui(",
        "def _ui_to_si(",
    ]:
        assert pattern not in heavy_text

    assert "_infer_unit_and_transform = partial(" in app_text
    assert "_infer_unit_and_transform = partial(" in heavy_text
    assert "param_unit = partial(" in app_text
    assert "param_unit = partial(" in heavy_text
