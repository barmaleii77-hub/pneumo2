from __future__ import annotations

from pneumo_solver_ui.camozzi_catalog_ui import CamozziCylinderChoice, _apply_choice
from pneumo_solver_ui.opt_worker_v3_margins_energy import make_base_and_ranges
from pneumo_solver_ui.spring_geometry_ui import build_spring_family_overrides
from pneumo_solver_ui.suspension_family_contract import (
    SPRING_STATIC_MODE_AUTO_MIDSTROKE,
    SPRING_STATIC_MODE_KEY,
    SPRING_STATIC_MODE_MANUAL,
    cylinder_family_key,
    family_param_description,
    family_param_meta,
    normalize_component_family_contract,
    spring_family_key,
)
from pneumo_solver_ui.ui_param_helpers import param_desc


def test_normalize_component_family_contract_seeds_family_keys_from_legacy() -> None:
    base = {
        "диаметр_поршня_Ц1": 0.032,
        "диаметр_штока_Ц1": 0.016,
        "диаметр_поршня_Ц2": 0.05,
        "диаметр_штока_Ц2": 0.014,
        "ход_штока": 0.25,
        "пружина_масштаб": 0.18,
        "пружина_длина_солид_м": 0.22,
    }
    ranges = {
        "диаметр_поршня_Ц1": [0.02, 0.04],
        "диаметр_штока_Ц1": [0.01, 0.02],
        "пружина_масштаб": [0.1, 1.0],
    }
    base_out, ranges_out, audit = normalize_component_family_contract(base, ranges)
    assert base_out[SPRING_STATIC_MODE_KEY] == SPRING_STATIC_MODE_AUTO_MIDSTROKE
    assert base_out[cylinder_family_key("bore", "Ц1", "перед")] == 0.032
    assert base_out[cylinder_family_key("bore", "Ц1", "зад")] == 0.032
    assert base_out[cylinder_family_key("stroke", "Ц2", "зад")] == 0.25
    assert base_out[spring_family_key("масштаб", "Ц2", "зад")] == 0.18
    assert base_out[spring_family_key("длина_солид_м", "Ц1", "перед")] == 0.22
    assert ranges_out[cylinder_family_key("bore", "Ц1", "перед")] == [0.02, 0.04]
    assert ranges_out[spring_family_key("масштаб", "Ц1", "зад")] == [0.1, 1.0]
    assert audit["family_count"] == 4
    assert cylinder_family_key("bore", "Ц1", "перед") in audit["seeded_base_keys"]


def test_make_base_and_ranges_exposes_family_contract_keys() -> None:
    base, ranges = make_base_and_ranges(101325.0)
    assert cylinder_family_key("bore", "Ц1", "перед") in base
    assert cylinder_family_key("rod", "Ц2", "зад") in base
    assert spring_family_key("масштаб", "Ц1", "перед") in base
    assert SPRING_STATIC_MODE_KEY in base
    assert cylinder_family_key("bore", "Ц1", "перед") in ranges


def test_camozzi_choice_can_target_single_axle_family() -> None:
    choice = CamozziCylinderChoice(
        variant_key="round_tube_through_rod",
        bore_mm=50,
        rod_mm=20,
        stroke_front_mm=80,
        stroke_rear_mm=125,
    )
    front = _apply_choice(choice, "Ц1 перед")
    assert front[cylinder_family_key("bore", "Ц1", "перед")] == 0.05
    assert front[cylinder_family_key("stroke", "Ц1", "перед")] == 0.08
    assert cylinder_family_key("bore", "Ц1", "зад") not in front
    assert "диаметр_поршня_Ц1" not in front

    both = _apply_choice(choice, "Ц2 обе оси")
    assert both[cylinder_family_key("bore", "Ц2", "перед")] == 0.05
    assert both[cylinder_family_key("bore", "Ц2", "зад")] == 0.05
    assert both["диаметр_поршня_Ц2"] == 0.05
    assert both["ход_штока_Ц2_зад_м"] == 0.125


def test_spring_geometry_builds_family_specific_overrides() -> None:
    manual = build_spring_family_overrides(
        target="Ц2 зад",
        static_mode=SPRING_STATIC_MODE_MANUAL,
        d_wire_m=0.008,
        D_mean_m=0.06,
        N_active=8.0,
        N_total=10.0,
        pitch_m=0.012,
        G_Pa=79e9,
        L_solid_m=0.08,
        margin_bind_m=0.005,
    )
    assert manual[SPRING_STATIC_MODE_KEY] == SPRING_STATIC_MODE_MANUAL
    assert manual[spring_family_key("геом_диаметр_проволоки_м", "Ц2", "зад")] == 0.008
    assert "пружина_геом_диаметр_проволоки_м" not in manual

    all_families = build_spring_family_overrides(
        target="Все 4 семейства",
        static_mode="auto",
        d_wire_m=0.009,
        D_mean_m=0.061,
        N_active=7.0,
        N_total=9.0,
        pitch_m=0.013,
        G_Pa=78e9,
        L_solid_m=0.081,
        margin_bind_m=0.006,
    )
    assert all_families[SPRING_STATIC_MODE_KEY] == SPRING_STATIC_MODE_AUTO_MIDSTROKE
    assert all_families["пружина_геом_диаметр_проволоки_м"] == 0.009
    assert all_families[spring_family_key("геом_диаметр_проволоки_м", "Ц1", "перед")] == 0.009
    assert all_families[spring_family_key("длина_солид_м", "Ц2", "зад")] == 0.081


def test_family_param_descriptions_are_human_readable() -> None:
    cyl_key = cylinder_family_key("bore", "Ц1", "перед")
    spr_key = spring_family_key("масштаб", "Ц2", "зад")
    meta = family_param_meta(cyl_key)
    assert meta is not None
    assert meta["группа"] == "Цилиндры по семействам"
    assert "независимый тип" in meta["описание"]
    assert "семейства" in family_param_description(spr_key)
    assert "семейства" in param_desc(spr_key)
