from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_svg_post_mapping_helpers as post_helpers
from pneumo_solver_ui.ui_svg_post_mapping_helpers import render_svg_post_mapping_sections


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_post_mapping_helpers.py"
SCHEME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
WORKBENCH_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_workbench_section_helpers.py"
TOOLS_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_tools_section_helpers.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.warnings: list[str] = []

    def warning(self, text: str) -> None:
        self.warnings.append(text)


def test_render_svg_post_mapping_sections_warns_without_mapping() -> None:
    fake_st = _FakeStreamlit()

    result = render_svg_post_mapping_sections(
        fake_st,
        {"state": "ok"},
        mapping=None,
        edge_columns=["edge-a"],
        selected_node_names=["node-a"],
        df_mdot="df_mdot",
        df_open="df_open",
        df_p="df_p",
        p_atm=101325.0,
        model_module="model",
        pressure_divisor=101325.0,
        pressure_unit="atm",
        dataset_id="dataset-1",
        safe_dataframe_fn="safe_df",
        flow_scale_and_unit_fn="flow_fn",
        get_component_fn="component_fn",
        render_svg_flow_animation_html_fn="html_fn",
        svg_inline="<svg />",
        evaluate_quality_fn="quality_fn",
    )

    assert result == "missing_mapping"
    assert fake_st.warnings == ["Нужен mapping JSON. Создайте его в разметчиках выше или загрузите файл."]


def test_render_svg_post_mapping_sections_delegates_to_child_sections(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        post_helpers,
        "render_svg_mapping_review_section",
        lambda *args, **kwargs: calls.append(("review", kwargs)),
    )
    monkeypatch.setattr(
        post_helpers,
        "render_svg_animation_section",
        lambda *args, **kwargs: calls.append(("animation", kwargs)),
    )

    result = render_svg_post_mapping_sections(
        fake_st,
        {"state": "ok"},
        mapping={"edges": {}},
        edge_columns=["edge-a"],
        selected_node_names=["node-a"],
        df_mdot="df_mdot",
        df_open="df_open",
        df_p="df_p",
        p_atm=101325.0,
        model_module="model",
        pressure_divisor=101325.0,
        pressure_unit="atm",
        dataset_id="dataset-1",
        safe_dataframe_fn="safe_df",
        flow_scale_and_unit_fn="flow_fn",
        get_component_fn="component_fn",
        render_svg_flow_animation_html_fn="html_fn",
        svg_inline="<svg />",
        evaluate_quality_fn="quality_fn",
    )

    assert result == "ok"
    assert [name for name, _payload in calls] == ["review", "animation"]
    assert calls[0][1]["evaluate_quality_fn"] == "quality_fn"
    assert calls[1][1]["selected_node_names"] == ["node-a"]
    assert calls[1][1]["pressure_divisor"] == 101325.0
    assert calls[1][1]["svg_inline"] == "<svg />"


def test_entrypoints_use_shared_svg_post_mapping_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    scheme_text = SCHEME_HELPERS_PATH.read_text(encoding="utf-8")
    workbench_text = WORKBENCH_HELPERS_PATH.read_text(encoding="utf-8")
    tools_text = TOOLS_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import render_svg_scheme_section" in surface_text
    assert '"render_svg_scheme_section_fn": render_svg_scheme_section' in surface_text
    assert 'st.warning("Нужен mapping JSON. Создайте его в разметчиках выше или загрузите файл.")' not in app_text
    assert 'st.warning("Нужен mapping JSON. Создайте его в разметчиках выше или загрузите файл.")' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_post_mapping_helpers import (" in tools_text
    assert "render_svg_post_mapping_sections(" in tools_text
    assert "render_svg_mapping_review_section(" in helper_text
    assert "render_svg_animation_section(" in helper_text
