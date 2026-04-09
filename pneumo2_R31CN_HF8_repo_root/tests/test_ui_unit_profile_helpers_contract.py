from __future__ import annotations

from pathlib import Path

import pytest

from pneumo_solver_ui.ui_unit_profile_helpers import (
    build_gauge_pressure_profile,
    build_param_unit_labeler,
    build_plot_unit_transformer,
    build_pressure_gauge_converters,
    build_si_ui_converters,
    build_ui_unit_profile,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_unit_profile_helpers_build_expected_transformers_and_converters() -> None:
    infer = build_plot_unit_transformer(
        pressure_unit_label="бар (изб.)",
        pressure_offset_pa=101325.0,
        pressure_divisor_pa=100000.0,
        length_unit_label="мм",
        length_scale=1000.0,
    )
    unit, transform, yaxis = infer("давление_узел_Па")
    assert unit == "бар (изб.)"
    assert yaxis == "бар (изб.)"
    assert transform is not None
    assert transform(201325.0) == pytest.approx(1.0)

    unit_mm, transform_mm, _ = infer("координата_m")
    assert unit_mm == "мм"
    assert transform_mm is not None
    assert transform_mm(0.25) == pytest.approx(250.0)

    pa_to_g, g_to_pa = build_pressure_gauge_converters(
        pressure_offset_pa=101325.0,
        pressure_divisor_pa=100000.0,
    )
    assert pa_to_g(201325.0) == pytest.approx(1.0)
    assert g_to_pa(1.5) == pytest.approx(251325.0)


def test_unit_profile_helpers_build_param_units_and_si_ui_adapters() -> None:
    param_unit = build_param_unit_labeler(
        pressure_unit_label="атм изб.",
        is_pressure_param_fn=lambda name: name.startswith("давление_"),
        is_volume_param_fn=lambda name: name.startswith("объём_"),
        is_small_volume_param_fn=lambda name: name.endswith("линии"),
    )
    assert param_unit("давление_Pmin") == "атм изб."
    assert param_unit("объём_линии") == "мл"

    si_to_ui, ui_to_si = build_si_ui_converters(
        p_atm=101325.0,
        bar_pa=100000.0,
    )
    assert si_to_ui("p", 201325.0, "pressure_bar_g") == pytest.approx(1.0)
    assert ui_to_si("x", 123.0, "length_mm") == pytest.approx(0.123)

    p_atm = 101325.0
    si_to_ui_dyn, ui_to_si_dyn = build_si_ui_converters(
        p_atm=lambda: p_atm,
        bar_pa=lambda: 100000.0,
    )
    p_atm = 111325.0
    assert si_to_ui_dyn("p", 211325.0, "pressure_bar_g") == pytest.approx(1.0)
    assert ui_to_si_dyn("p", 1.0, "pressure_bar_g") == pytest.approx(211325.0)


def test_unit_profile_helpers_build_composed_profiles() -> None:
    pressure_profile = build_gauge_pressure_profile(
        unit_label="атм изб.",
        pressure_offset_pa=101325.0,
        pressure_divisor_pa=101325.0,
    )
    assert pressure_profile.unit_label == "атм изб."
    assert pressure_profile.pressure_from_pa(202650.0) == pytest.approx(1.0)
    assert pressure_profile.pressure_to_pa_abs(1.0) == pytest.approx(202650.0)

    unit_profile = build_ui_unit_profile(
        pressure_unit_label="бар (изб.)",
        pressure_offset_pa=101325.0,
        pressure_divisor_pa=100000.0,
        length_unit_label="мм",
        length_scale=1000.0,
        is_pressure_param_fn=lambda name: name.startswith("давление_"),
        is_volume_param_fn=lambda name: name.startswith("объём_"),
        is_small_volume_param_fn=lambda name: name.endswith("линии"),
        p_atm=101325.0,
        bar_pa=100000.0,
    )
    unit, transform, _ = unit_profile.infer_unit_and_transform("давление_узел_Па")
    assert unit == "бар (изб.)"
    assert transform is not None
    assert transform(201325.0) == pytest.approx(1.0)
    assert unit_profile.param_unit("давление_Pmin") == "бар (изб.)"
    assert unit_profile.si_to_ui("x", 0.123, "length_mm") == pytest.approx(123.0)
    assert unit_profile.ui_to_si("p", 1.0, "pressure_bar_g") == pytest.approx(201325.0)


def test_active_entrypoints_use_shared_unit_profile_helpers() -> None:
    helper_source = (REPO_ROOT / "pneumo_solver_ui" / "ui_unit_profile_helpers.py").read_text(encoding="utf-8")
    app_source = (REPO_ROOT / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    heavy_source = (REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")

    assert "def build_plot_unit_transformer" in helper_source
    assert "def build_pressure_gauge_converters" in helper_source
    assert "def build_gauge_pressure_profile" in helper_source
    assert "def build_param_unit_labeler" in helper_source
    assert "def build_si_ui_converters" in helper_source
    assert "def build_ui_unit_profile" in helper_source

    assert "from pneumo_solver_ui.ui_unit_profile_helpers import (" in app_source
    assert "from pneumo_solver_ui.ui_unit_profile_helpers import (" in heavy_source
    assert "build_ui_unit_profile(" in app_source
    assert "build_ui_unit_profile(" in heavy_source
    assert "build_gauge_pressure_profile(" not in app_source
    assert "build_gauge_pressure_profile(" in heavy_source
