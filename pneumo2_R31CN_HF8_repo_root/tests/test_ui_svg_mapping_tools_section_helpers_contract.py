from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_svg_mapping_tools_section_helpers as tools_helpers
from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (
    render_svg_mapping_tools_section,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_tools_section_helpers.py"
SCHEME_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
WORKBENCH_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_workbench_section_helpers.py"


class _FakeBlock:
    def __enter__(self) -> "_FakeBlock":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeStreamlit:
    def __init__(self, *, button_presses: dict[str, bool] | None = None) -> None:
        self.button_presses = dict(button_presses or {})
        self.markdowns: list[str] = []
        self.captions: list[str] = []
        self.downloads: list[str] = []
        self.errors: list[str] = []

    def markdown(self, text: str) -> None:
        self.markdowns.append(text)

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def columns(self, spec, gap: str | None = None) -> list[_FakeBlock]:
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeBlock() for _ in range(count)]

    def button(self, label: str, key: str | None = None, help: str | None = None):
        return bool(self.button_presses.get(str(key), False))

    def download_button(self, label: str, data, file_name: str, mime: str, help: str | None = None) -> None:
        self.downloads.append(file_name)

    def error(self, text: str) -> None:
        self.errors.append(text)


def test_render_svg_mapping_tools_section_delegates_to_input_and_post(monkeypatch, tmp_path) -> None:
    fake_st = _FakeStreamlit()
    session_state = {"svg_mapping_source": "generated_template", "svg_mapping_text": '{"edges":{}}'}
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        tools_helpers,
        "render_svg_mapping_input",
        lambda *args, **kwargs: calls.append(("input", kwargs)) or {"edges": {}},
    )
    monkeypatch.setattr(
        tools_helpers,
        "render_svg_post_mapping_sections",
        lambda *args, **kwargs: calls.append(("post", kwargs)) or "ok",
    )

    mapping = render_svg_mapping_tools_section(
        fake_st,
        session_state,
        default_svg_mapping_path=tmp_path / "default.json",
        do_rerun_fn=lambda: calls.append(("rerun", {})),
        log_event_fn=lambda *args, **kwargs: calls.append(("log", kwargs)),
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

    assert mapping == {"edges": {}}
    assert fake_st.markdowns == ["### Анимация по схеме (по mapping JSON)"]
    assert fake_st.captions == ["Источник mapping: generated_template"]
    assert fake_st.downloads == ["mapping.json"]
    assert [name for name, _payload in calls] == ["input", "post"]
    assert calls[1][1]["mapping"] == {"edges": {}}
    assert calls[1][1]["evaluate_quality_fn"] == "quality_fn"


def test_render_svg_mapping_tools_section_handles_reset_default(monkeypatch, tmp_path) -> None:
    default_path = tmp_path / "default.json"
    default_path.write_text('{"edges":{"a":[]}}', encoding="utf-8")
    fake_st = _FakeStreamlit(button_presses={"svg_mapping_reset_default": True})
    session_state: dict[str, object] = {"svg_mapping_text": ""}
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        tools_helpers,
        "render_svg_mapping_input",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        tools_helpers,
        "render_svg_post_mapping_sections",
        lambda *args, **kwargs: "missing_mapping",
    )

    render_svg_mapping_tools_section(
        fake_st,
        session_state,
        default_svg_mapping_path=default_path,
        do_rerun_fn=lambda: calls.append(("rerun", {})),
        log_event_fn=lambda event_name, **kwargs: calls.append((event_name, kwargs)),
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

    assert session_state["svg_mapping_text"] == '{"edges":{"a":[]}}'
    assert session_state["svg_mapping_source"] == str(default_path)
    assert calls == [
        ("svg_mapping_reset_default", {"path": str(default_path)}),
        ("rerun", {}),
    ]
    assert fake_st.errors == []


def test_entrypoints_use_shared_svg_mapping_tools_section_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    scheme_text = SCHEME_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    workbench_text = WORKBENCH_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import render_svg_scheme_section" in surface_text
    assert '"render_svg_scheme_section_fn": render_svg_scheme_section' in surface_text
    assert "render_svg_mapping_tools_section(" not in app_text
    assert "render_svg_mapping_tools_section(" not in heavy_text
    assert "render_svg_edge_mapper_html(" not in app_text
    assert "render_svg_edge_mapper_html(" not in heavy_text
    assert "render_svg_node_mapper_html(" not in app_text
    assert "render_svg_node_mapper_html(" not in heavy_text
    assert 'st.markdown("### Анимация по схеме (по mapping JSON)")' not in app_text
    assert 'st.markdown("### Анимация по схеме (по mapping JSON)")' not in heavy_text
    assert 'key="svg_mapping_reset_default"' not in app_text
    assert 'key="svg_mapping_reset_default"' not in heavy_text
    assert 'file_name="mapping.json"' not in app_text
    assert 'file_name="mapping.json"' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_input_helpers import (" in helper_text
    assert "from pneumo_solver_ui.ui_svg_post_mapping_helpers import (" in helper_text
    assert "render_svg_mapping_input(" in helper_text
    assert "render_svg_post_mapping_sections(" in helper_text
    assert "from pneumo_solver_ui.ui_svg_html_builders import (" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
