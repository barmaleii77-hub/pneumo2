from __future__ import annotations

import math
from pathlib import Path

from pneumo_solver_ui.desktop_geometry_reference_model import (
    CylinderFamilyReferenceRow,
    build_cylinder_match_recommendations,
    build_cylinder_force_bias_estimate,
    build_current_cylinder_package_rows,
    build_current_cylinder_precharge_rows,
    build_current_spring_reference_snapshot,
    load_camozzi_catalog_rows,
)
from pneumo_solver_ui.desktop_geometry_reference_runtime import DesktopGeometryReferenceRuntime
from pneumo_solver_ui.suspension_family_contract import (
    cylinder_axle_geometry_key,
    cylinder_family_key,
    cylinder_precharge_key,
    spring_family_key,
)


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def test_desktop_geometry_reference_runtime_builds_reference_snapshots() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    geometry = runtime.geometry_snapshot(dw_min_mm=-80.0, dw_max_mm=80.0)
    component_fit = runtime.component_fit_rows(dw_min_mm=-80.0, dw_max_mm=80.0)
    cylinders = runtime.current_cylinder_rows()
    cylinder_packages = runtime.current_cylinder_package_rows()
    cylinder_precharge = runtime.current_cylinder_precharge_rows()
    springs = runtime.current_spring_snapshot()
    catalog = runtime.cylinder_catalog_rows()
    guide = runtime.parameter_guide_rows("давление", limit=8)

    assert geometry.base_path.name.endswith(".json")
    assert len(geometry.families) == 4
    assert any(row.motion_ratio_peak > 0.0 for row in geometry.families)
    assert len(component_fit) == 4
    assert all(row.family for row in component_fit)
    assert all(row.action_summary for row in component_fit)
    assert len(cylinders) == 4
    assert all(row.cap_area_cm2 > 0.0 for row in cylinders)
    assert len(cylinder_packages) == 4
    assert all(row.family for row in cylinder_packages)
    assert len(cylinder_precharge) == 4
    assert all(row.family for row in cylinder_precharge)
    assert len(springs.families) == 4
    assert all(row.family for row in springs.families)
    assert all(hasattr(row, "inner_diameter_mm") for row in springs.families)
    assert all(hasattr(row, "outer_diameter_mm") for row in springs.families)
    assert all(hasattr(row, "free_length_mm") for row in springs.families)
    assert all(hasattr(row, "top_offset_mm") for row in springs.families)
    assert all(hasattr(row, "rebound_preload_min_mm") for row in springs.families)
    assert len(catalog) > 0
    assert all(row.cap_area_cm2 > 0.0 for row in catalog[:5])
    assert len(guide) > 0
    assert any("давление" in row.label.lower() or "давление" in row.description.lower() for row in guide)


def test_desktop_geometry_reference_runtime_filters_catalog_variants_and_search() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    variant_labels = runtime.catalog_variant_labels()
    assert variant_labels

    first_variant = variant_labels[0]
    filtered = runtime.cylinder_catalog_rows(variant_label=first_variant, search_query="46.5")

    assert filtered
    assert all(row.variant_label == first_variant for row in filtered)
    assert all(math.isclose(row.TG_mm, 46.5, rel_tol=0.0, abs_tol=1e-9) for row in filtered)


def test_desktop_geometry_reference_runtime_builds_family_match_recommendations() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    recommendations = runtime.cylinder_match_recommendations("Ц1 перед", limit=3)

    assert len(recommendations) == 3
    assert all(item.family == "Ц1 перед" for item in recommendations)
    assert recommendations[0].score <= recommendations[1].score <= recommendations[2].score
    assert all(item.bore_mm > 0 and item.rod_mm > 0 for item in recommendations)
    assert all(item.notes for item in recommendations)
    assert all(hasattr(item, "net_force_delta_N") for item in recommendations)
    assert all(hasattr(item, "bias_direction") for item in recommendations)


def test_desktop_geometry_reference_runtime_builds_cross_component_fit_summary() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    rows = runtime.component_fit_rows(dw_min_mm=-60.0, dw_max_mm=60.0)

    assert len(rows) == 4
    assert any(row.status in {"ok", "warn"} for row in rows)
    assert all(row.recommended_catalog_label for row in rows)
    assert all(row.notes for row in rows)
    assert all(row.action_summary for row in rows)
    assert all(hasattr(row, "cylinder_outer_diameter_mm") for row in rows)
    assert all(hasattr(row, "spring_to_cylinder_clearance_mm") for row in rows)
    assert all(hasattr(row, "recommended_net_force_delta_N") for row in rows)
    assert all(hasattr(row, "recommended_bias_direction") for row in rows)
    assert all(
        any(marker in " ".join(row.notes) for marker in ("clearance", "diameter", "ID"))
        for row in rows
    )


def test_cylinder_precharge_reference_rows_estimate_force_bias_from_absolute_pressures() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)
    base = runtime.load_base_payload()
    base[cylinder_precharge_key("Ц1", "CAP", "перед")] = 701325.0
    base[cylinder_precharge_key("Ц1", "ROD", "перед")] = 401325.0

    rows = {row.family: row for row in build_current_cylinder_precharge_rows(base)}
    row = rows["Ц1 перед"]

    assert math.isclose(row.cap_precharge_abs_kpa, 701.325, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(row.rod_precharge_abs_kpa, 401.325, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(row.cap_precharge_bar_g, 6.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.rod_precharge_bar_g, 3.0, rel_tol=0.0, abs_tol=1e-9)
    assert row.cap_force_N > row.rod_force_N > 0.0
    assert row.net_force_N > 0.0
    assert row.bias_direction == "extend"
    assert any("bias" in note for note in row.notes)


def test_cylinder_force_bias_estimate_supports_catalog_rows() -> None:
    row = next(item for item in load_camozzi_catalog_rows() if item.bore_mm == 50 and item.rod_mm == 20)

    estimate = build_cylinder_force_bias_estimate(
        row,
        cap_pressure_bar_gauge=6.0,
        rod_pressure_bar_gauge=3.0,
        clamp_negative=False,
    )

    assert estimate.cap_force_N > estimate.rod_force_N > 0.0
    assert estimate.net_force_N > 0.0
    assert estimate.bias_direction == "extend"
    assert any("bias" in note for note in estimate.notes)


def test_cylinder_match_recommendations_keep_current_bias_preferred_when_precharge_known() -> None:
    catalog_rows = tuple(
        item
        for item in load_camozzi_catalog_rows()
        if item.variant_label == "Round tube (tie-rod)" and (item.bore_mm, item.rod_mm) in {(50, 20), (63, 20)}
    )
    current_catalog = next(item for item in catalog_rows if (item.bore_mm, item.rod_mm) == (50, 20))
    current = CylinderFamilyReferenceRow(
        family="Ц1 перед",
        bore_mm=float(current_catalog.bore_mm),
        rod_mm=float(current_catalog.rod_mm),
        stroke_mm=120.0,
        cap_area_cm2=float(current_catalog.cap_area_cm2),
        annulus_area_cm2=float(current_catalog.annulus_area_cm2),
    )
    current_bias = build_cylinder_force_bias_estimate(
        current,
        cap_pressure_bar_gauge=6.0,
        rod_pressure_bar_gauge=3.0,
        clamp_negative=False,
    )
    current_precharge = build_current_cylinder_precharge_rows(
        {
            cylinder_family_key("bore", "Ц1", "перед"): 0.050,
            cylinder_family_key("rod", "Ц1", "перед"): 0.020,
            cylinder_precharge_key("Ц1", "CAP", "перед"): 701325.0,
            cylinder_precharge_key("Ц1", "ROD", "перед"): 401325.0,
        }
    )[0]

    recommendations = build_cylinder_match_recommendations(
        current,
        catalog_rows,
        current_precharge=current_precharge,
        limit=2,
    )

    assert len(recommendations) == 2
    assert recommendations[0].bore_mm == 50
    assert recommendations[0].rod_mm == 20
    assert math.isclose(recommendations[0].net_force_N, current_bias.net_force_N, rel_tol=0.0, abs_tol=1e-6)
    assert math.isclose(recommendations[0].net_force_delta_N, 0.0, rel_tol=0.0, abs_tol=1e-6)
    assert recommendations[0].bias_direction == "extend"
    assert any("bias" in note for note in recommendations[0].notes)
    assert recommendations[1].net_force_delta_N > 0.0


def test_cylinder_package_reference_rows_report_body_vs_dead_lengths() -> None:
    base: dict[str, float] = {
        cylinder_family_key("bore", "Ц1", "перед"): 0.040,
        cylinder_family_key("rod", "Ц1", "перед"): 0.020,
        cylinder_family_key("stroke", "Ц1", "перед"): 0.120,
        cylinder_axle_geometry_key("outer_diameter_m", "Ц1", "перед"): 0.048,
        cylinder_axle_geometry_key("dead_cap_length_m", "Ц1", "перед"): 0.030,
        cylinder_axle_geometry_key("dead_rod_length_m", "Ц1", "перед"): 0.025,
        cylinder_axle_geometry_key("dead_height_m", "Ц1", "перед"): 0.028,
        cylinder_axle_geometry_key("body_length_m", "Ц1", "перед"): 0.178,
    }

    rows = {row.family: row for row in build_current_cylinder_package_rows(base)}
    row = rows["Ц1 перед"]

    assert math.isclose(row.outer_diameter_mm, 48.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.dead_cap_length_mm, 30.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.dead_rod_length_mm, 25.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.dead_height_mm, 28.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.expected_body_length_mm, 175.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.body_length_mm, 178.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.body_length_gap_mm, 3.0, rel_tol=0.0, abs_tol=1e-9)
    assert any("body" in note for note in row.notes)


def test_spring_reference_snapshot_keeps_missing_diameter_data_unknown() -> None:
    snapshot = build_current_spring_reference_snapshot({})

    assert len(snapshot.families) == 4
    assert all(not math.isfinite(row.inner_diameter_mm) for row in snapshot.families)
    assert all(not math.isfinite(row.outer_diameter_mm) for row in snapshot.families)


def test_spring_reference_snapshot_exposes_install_contract_and_free_length_gap() -> None:
    base: dict[str, float] = {
        spring_family_key("геом_диаметр_проволоки_м", "Ц1", "перед"): 0.008,
        spring_family_key("геом_диаметр_средний_м", "Ц1", "перед"): 0.060,
        spring_family_key("геом_число_витков_активных", "Ц1", "перед"): 8.0,
        spring_family_key("геом_число_витков_полное", "Ц1", "перед"): 10.0,
        spring_family_key("геом_шаг_витка_м", "Ц1", "перед"): 0.012,
        spring_family_key("геом_G_Па", "Ц1", "перед"): 79.0e9,
        spring_family_key("длина_свободная_м", "Ц1", "перед"): 0.120,
        spring_family_key("верхний_отступ_от_крышки_м", "Ц1", "перед"): 0.015,
        spring_family_key("преднатяг_на_отбое_минимум_м", "Ц1", "перед"): 0.010,
        spring_family_key("запас_до_coil_bind_минимум_м", "Ц1", "перед"): 0.005,
    }

    rows = {row.family: row for row in build_current_spring_reference_snapshot(base).families}
    row = rows["Ц1 перед"]

    assert math.isclose(row.free_length_mm, 120.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.free_length_from_pitch_mm, 116.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.free_length_pitch_gap_mm, 4.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.top_offset_mm, 15.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.rebound_preload_min_mm, 10.0, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(row.bind_margin_target_mm, 5.0, rel_tol=0.0, abs_tol=1e-9)


def test_desktop_geometry_reference_runtime_exposes_family_contract_parameter_guides() -> None:
    runtime = DesktopGeometryReferenceRuntime(ui_root=UI_ROOT)

    rows = runtime.parameter_guide_rows("coil bind", limit=20)
    precharge_rows = runtime.parameter_guide_rows("предзаряд", limit=20)

    assert rows
    assert any("Пружины по семействам" == row.section_title for row in rows)
    assert any("coil" in row.key.lower() or "coil" in row.description.lower() for row in rows)
    assert precharge_rows
    assert any("Пневматика по семействам" == row.section_title for row in precharge_rows)
    assert any(row.current_value_text for row in precharge_rows)


def test_desktop_geometry_reference_center_keeps_tabbed_desktop_workspace_contract() -> None:
    tool_src = (UI_ROOT / "tools" / "desktop_geometry_reference_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    model_src = (UI_ROOT / "desktop_geometry_reference_model.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    runtime_src = (UI_ROOT / "desktop_geometry_reference_runtime.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "class DesktopGeometryReferenceCenter" in tool_src
    assert "ttk.Notebook" in tool_src
    assert "create_scrollable_tab(self.notebook" in tool_src
    assert 'self.notebook.add(geometry_tab_host, text="Подвеска")' in tool_src
    assert 'self.notebook.add(cylinder_tab_host, text="Цилиндры")' in tool_src
    assert 'self.notebook.add(spring_tab_host, text="Пружины")' in tool_src
    assert 'self.notebook.add(guide_tab_host, text="Параметры")' in tool_src
    assert "DesktopGeometryReferenceRuntime()" in tool_src
    assert "def _refresh_geometry_tab(self) -> None:" in tool_src
    assert "def _refresh_cylinder_tab(self) -> None:" in tool_src
    assert "def _on_recommendation_selected(self, _event: object) -> None:" in tool_src
    assert "def _refresh_spring_tab(self) -> None:" in tool_src
    assert "def _refresh_parameter_guide(self) -> None:" in tool_src
    assert 'text="Сквозная совместимость компонентов по семействам"' in tool_src
    assert "self.component_fit_summary_var" in tool_src
    assert "self.component_fit_tree = self._build_tree(" in tool_src
    assert '("cyl_od", "Cylinder OD, мм", 110, "e")' in tool_src
    assert '("spring_id", "Spring ID, мм", 110, "e")' in tool_src
    assert '("clearance", "ID-OD, мм", 90, "e")' in tool_src
    assert '("od", "OD, мм", 90, "e")' in tool_src
    assert '("body", "Body, мм", 90, "e")' in tool_src
    assert '("body_need", "Stroke+dead, мм", 110, "e")' in tool_src
    assert '("body_gap", "Δbody, мм", 90, "e")' in tool_src
    assert '("dnet", "ΔFnet rec, Н", 110, "e")' in tool_src
    assert '("bias", "Bias rec", 90, "w")' in tool_src
    assert '("B", "B, мм", 80, "e")' in tool_src
    assert '("E", "E, мм", 80, "e")' in tool_src
    assert '("TG", "TG, мм", 80, "e")' in tool_src
    assert 'text="Текущий precharge / force bias из base"' in tool_src
    assert "self.cylinder_precharge_summary_var" in tool_src
    assert "self.current_cylinder_precharge_tree = self._build_tree(" in tool_src
    assert '("pcap_abs", "Pcap abs, кПа", 100, "e")' in tool_src
    assert '("f_net", "Fnet, Н", 100, "e")' in tool_src
    assert "text=\"Рекомендованные каталожные варианты для текущего family\"" in tool_src
    assert '("dnet", "ΔFnet, Н", 100, "e")' in tool_src
    assert '("bias", "Bias", 80, "w")' in tool_src
    assert '("inner", "ID, мм", 80, "e")' in tool_src
    assert '("outer", "OD, мм", 80, "e")' in tool_src
    assert 'text="Текущий spring install contract из base"' in tool_src
    assert "self.spring_install_summary_var" in tool_src
    assert "self.current_spring_install_tree = self._build_tree(" in tool_src
    assert '("free_gap", "ΔLfree, мм", 90, "e")' in tool_src
    assert '("rebound", "Rebound min, мм", 110, "e")' in tool_src
    assert '(\"current\", \"Текущее\", 140, \"w\")' in tool_src
    assert "self.cylinder_recommendation_var" in tool_src
    assert "self.recommendation_tree = self._build_tree(" in tool_src
    assert "def on_host_close(self) -> None:" in tool_src
    assert "def main() -> int:" in tool_src

    assert "class GeometryReferenceSnapshot" in model_src
    assert "class CylinderCatalogRow" in model_src
    assert "class CylinderForceBiasEstimate" in model_src
    assert "class CylinderMatchRecommendation" in model_src
    assert "class CylinderPackageReferenceRow" in model_src
    assert "class CylinderPrechargeReferenceRow" in model_src
    assert "class ComponentFitReferenceRow" in model_src
    assert "class SpringReferenceSnapshot" in model_src
    assert "def build_geometry_reference_snapshot(" in model_src
    assert "def build_cylinder_force_bias_estimate(" in model_src
    assert "def build_current_cylinder_package_rows(" in model_src
    assert "def build_current_cylinder_precharge_rows(" in model_src
    assert "def build_current_cylinder_reference_rows(" in model_src
    assert "def build_current_cylinder_outer_diameter_rows(" in model_src
    assert "def build_cylinder_match_recommendations(" in model_src
    assert "def build_component_fit_reference_rows(" in model_src
    assert "def build_current_spring_reference_snapshot(" in model_src
    assert "def build_parameter_guide_rows(" in model_src
    assert "def _build_family_parameter_guide_rows(" in model_src

    assert "class DesktopGeometryReferenceRuntime" in runtime_src
    assert "def geometry_snapshot(" in runtime_src
    assert "def current_cylinder_package_rows(" in runtime_src
    assert "def current_cylinder_rows(" in runtime_src
    assert "def current_cylinder_precharge_rows(" in runtime_src
    assert "def current_spring_snapshot(" in runtime_src
    assert "def component_fit_rows(" in runtime_src
    assert "def cylinder_catalog_rows(" in runtime_src
    assert "def cylinder_match_recommendations(" in runtime_src
    assert "def parameter_guide_rows(" in runtime_src
