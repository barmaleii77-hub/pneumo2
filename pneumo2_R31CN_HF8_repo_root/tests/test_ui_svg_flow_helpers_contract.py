from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pneumo_solver_ui import ui_svg_flow_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
INPUT_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_input_helpers.py"


class _FakeUpload:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def getvalue(self) -> bytes:
        return self._payload


class _FakeStreamlit:
    def __init__(self, *, selected_mode: str = "add", selected_nodes=None, upload=None) -> None:
        self.selected_mode = selected_mode
        self.selected_nodes = list(selected_nodes or [])
        self.upload = upload
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.downloads: list[dict[str, object]] = []

    def radio(self, label, *, options, format_func, horizontal, key):
        assert label == "Клик по схеме"
        assert options == ["add", "replace"]
        assert horizontal is True
        assert key == "svg_click_mode"
        assert format_func("add") == "Добавлять к выбору"
        assert format_func("replace") == "Заменять выбор"
        return self.selected_mode

    def multiselect(self, label, *, options, default, key):
        assert label == "Узлы давления для отображения на схеме"
        assert key == "anim_nodes_svg"
        assert default == ui_svg_flow_helpers.default_svg_pressure_nodes(options)
        return [item for item in self.selected_nodes if item in options]

    def info(self, text):
        self.infos.append(text)

    def warning(self, text):
        self.warnings.append(text)

    def file_uploader(self, label, *, type, key):
        assert label == "SVG файл схемы (опционально, если хотите заменить)"
        assert type == ["svg"]
        assert key == "svg_scheme_upl"
        return self.upload

    def download_button(self, label, *, data, file_name, mime):
        self.downloads.append(
            {
                "label": label,
                "data": data,
                "file_name": file_name,
                "mime": mime,
            }
        )


def test_svg_flow_column_and_default_helpers() -> None:
    df_mdot = pd.DataFrame({"время_с": [0.0], "edge_a": [1.0], "edge_b": [2.0]})
    df_p = pd.DataFrame({"время_с": [0.0], "Ресивер2": [1.0], "custom_node": [2.0]})

    assert ui_svg_flow_helpers.svg_edge_columns(df_mdot) == ["edge_a", "edge_b"]
    assert ui_svg_flow_helpers.svg_pressure_node_columns(df_p) == ["Ресивер2", "custom_node"]
    assert ui_svg_flow_helpers.default_svg_pressure_nodes(["Ресивер2", "custom_node"]) == ["Ресивер2"]
    assert ui_svg_flow_helpers.default_svg_pressure_nodes(["n1", "n2"], limit=1) == ["n1"]


def test_svg_flow_render_helpers_and_mapping_template(tmp_path: Path) -> None:
    svg_text = '<?xml version="1.0" encoding="utf-8"?><svg viewBox="1 2 300 400"><g /></svg>'
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "pneumo_scheme.svg").write_text(svg_text, encoding="utf-8")

    fake_st = _FakeStreamlit(selected_mode="replace", selected_nodes=["custom_node"])

    assert ui_svg_flow_helpers.render_svg_click_mode_selector(fake_st) == "replace"
    selected_nodes = ui_svg_flow_helpers.render_svg_pressure_node_selector(
        fake_st,
        ["Ресивер1", "custom_node"],
    )
    assert selected_nodes == ["custom_node"]

    loaded_svg_text, svg_inline = ui_svg_flow_helpers.render_svg_source_template_controls(
        fake_st,
        base_dir=tmp_path,
        edge_columns=["edge_a", "edge_b"],
        selected_node_names=selected_nodes,
    )

    assert loaded_svg_text == svg_text
    assert svg_inline == '<svg viewBox="1 2 300 400"><g /></svg>'
    assert fake_st.warnings == []
    assert len(fake_st.downloads) == 1
    download = fake_st.downloads[0]
    assert download["label"] == "Скачать шаблон mapping JSON"
    assert download["file_name"] == "pneumo_svg_mapping_template.json"
    assert download["mime"] == "application/json"
    payload = json.loads(download["data"].decode("utf-8"))
    assert payload == {
        "version": 2,
        "viewBox": "1 2 300 400",
        "edges": {"edge_a": [], "edge_b": []},
        "nodes": {"custom_node": None},
    }


def test_svg_flow_source_helper_handles_missing_and_uploaded_sources(tmp_path: Path) -> None:
    fake_missing = _FakeStreamlit()
    assert ui_svg_flow_helpers.render_svg_pressure_node_selector(fake_missing, []) == []
    assert fake_missing.infos == ["Подписи давления на схеме доступны только при record_full=True (df_p)."]

    missing_text, missing_inline = ui_svg_flow_helpers.render_svg_source_template_controls(
        fake_missing,
        base_dir=tmp_path,
        edge_columns=["edge_a"],
        selected_node_names=[],
    )
    assert (missing_text, missing_inline) == (None, None)
    assert fake_missing.warnings == [
        "SVG не найден. Положите файл в assets/pneumo_scheme.svg или загрузите через uploader."
    ]

    uploaded_svg = b'<?xml version="1.0"?><svg viewBox="0 0 10 20"></svg>'
    fake_upload = _FakeStreamlit(upload=_FakeUpload(uploaded_svg))
    upload_text, upload_inline = ui_svg_flow_helpers.render_svg_source_template_controls(
        fake_upload,
        base_dir=tmp_path,
        edge_columns=["edge_a"],
        selected_node_names=["n1"],
    )
    assert upload_text == uploaded_svg.decode("utf-8")
    assert upload_inline == '<svg viewBox="0 0 10 20"></svg>'


def test_entrypoints_use_shared_svg_flow_helpers() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    input_text = INPUT_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import render_svg_scheme_section" in surface_text
    assert '"render_svg_scheme_section_fn": render_svg_scheme_section' in surface_text
    assert "render_svg_click_mode_selector(" not in app_text
    assert "render_svg_click_mode_selector(" not in heavy_text
    assert "render_svg_pressure_node_selector(" not in app_text
    assert "render_svg_pressure_node_selector(" not in heavy_text
    assert "render_svg_source_template_controls(" not in app_text
    assert "render_svg_source_template_controls(" not in heavy_text
    assert 'default_svg_path = HERE / "assets" / "pneumo_scheme.svg"' not in app_text
    assert 'default_svg_path = HERE / "assets" / "pneumo_scheme.svg"' not in heavy_text
    assert "svg_upl = st.file_uploader(" not in app_text
    assert "svg_upl = st.file_uploader(" not in heavy_text
    assert "template_mapping = {" not in app_text
    assert "template_mapping = {" not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_scheme_input_helpers import (" in section_text
    assert "render_svg_scheme_inputs(" in section_text
    assert "from pneumo_solver_ui.ui_svg_flow_helpers import (" in input_text
    assert "render_svg_click_mode_selector(" in input_text
    assert "render_svg_pressure_node_selector(" in input_text
    assert "render_svg_source_template_controls(" in input_text
