from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui import ui_svg_mapping_review_panel_helpers as review_helpers
from pneumo_solver_ui.ui_svg_mapping_review_panel_helpers import (
    build_svg_mapping_review_rows,
    render_svg_mapping_review_panel,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_review_panel_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_review_section_helpers.py"
POST_MAPPING_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_post_mapping_helpers.py"
SCHEME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
WORKBENCH_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_workbench_section_helpers.py"
TOOLS_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_tools_section_helpers.py"


class _FakeBlock:
    def __enter__(self) -> "_FakeBlock":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeStreamlit:
    def __init__(self, *, button_presses: dict[str, bool] | None = None) -> None:
        self.button_presses = dict(button_presses or {})
        self.markdowns: list[str] = []
        self.infos: list[str] = []
        self.captions: list[str] = []
        self.successes: list[str] = []
        self.errors: list[str] = []
        self.downloads: list[str] = []
        self.dataframes: list[tuple[list[str], int]] = []
        self.rerun_calls = 0

    def columns(self, spec) -> list[_FakeBlock]:
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeBlock() for _ in range(count)]

    def multiselect(self, label: str, options, default, key: str | None = None):
        return list(default)

    def download_button(self, label: str, data, file_name: str, mime: str) -> None:
        self.downloads.append(file_name)

    def markdown(self, text: str) -> None:
        self.markdowns.append(text)

    def selectbox(self, label: str, options, index: int = 0, key: str | None = None):
        return list(options)[index] if options else ""

    def radio(self, label: str, options, index: int = 0, horizontal: bool = False, key: str | None = None):
        return list(options)[index]

    def text_input(self, label: str, value: str = "", key: str | None = None):
        return value or "note-updated"

    def button(self, label: str, key: str | None = None):
        return bool(self.button_presses.get(str(key), False))

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def info(self, text: str) -> None:
        self.infos.append(text)

    def success(self, text: str) -> None:
        self.successes.append(text)

    def error(self, text: str) -> None:
        self.errors.append(text)

    def rerun(self) -> None:
        self.rerun_calls += 1


def test_build_svg_mapping_review_rows_extracts_review_and_quality() -> None:
    rows = build_svg_mapping_review_rows(
        ["edge-a", "edge-b"],
        {"edge-a": [[1, 2]], "edge-b": []},
        {
            "edge-a": {
                "review": {"status": "approved"},
                "quality": {"grade": "PASS", "length_px": 10.0, "detour_ratio": 1.2, "points": 5},
            }
        },
        first_poly_fn=lambda edge_name: [1, 2] if edge_name == "edge-a" else None,
    )

    assert rows == [
        {
            "edge": "edge-a",
            "has_geom": True,
            "status": "approved",
            "grade": "PASS",
            "len_px": 10.0,
            "detour": 1.2,
            "points": 5,
        },
        {
            "edge": "edge-b",
            "has_geom": False,
            "status": "",
            "grade": "",
            "len_px": None,
            "detour": None,
            "points": None,
        },
    ]


def test_render_svg_mapping_review_panel_saves_review(monkeypatch) -> None:
    fake_st = _FakeStreamlit(button_presses={"btn_map_review_save": True})
    session_state: dict[str, str] = {}
    mapping = {"edges": {"edge-a": [[1, 2]]}, "edges_meta": {}}
    edges_meta: dict[str, object] = {}

    monkeypatch.setattr(review_helpers.time, "time", lambda: 123.0)

    render_svg_mapping_review_panel(
        fake_st,
        session_state,
        edge_columns=["edge-a"],
        edges_geo={"edge-a": [[1, 2]]},
        edges_meta=edges_meta,
        mapping=mapping,
        first_poly_fn=lambda edge_name: [1, 2],
        safe_dataframe_fn=lambda frame, height: fake_st.dataframes.append((list(frame.columns), height)),
    )

    payload = json.loads(session_state["svg_mapping_text"])
    review = payload["edges_meta"]["edge-a"]["review"]
    assert review["status"] == "pending"
    assert review["note"] == "note-updated"
    assert review["by"] == "user"
    assert review["ts"] == 123.0
    assert fake_st.rerun_calls == 1
    assert fake_st.successes == ["Review сохранён."]
    assert fake_st.downloads == ["mapping_review_table.csv"]


def test_render_svg_mapping_review_panel_clears_geometry(monkeypatch) -> None:
    fake_st = _FakeStreamlit(button_presses={"btn_map_review_clear_geom": True})
    session_state: dict[str, str] = {}
    mapping = {"edges": {"edge-a": [[1, 2]]}, "edges_meta": {}}
    edges_meta = {"edge-a": {"review": {"status": "pending"}}}

    monkeypatch.setattr(review_helpers.time, "time", lambda: 456.0)

    render_svg_mapping_review_panel(
        fake_st,
        session_state,
        edge_columns=["edge-a"],
        edges_geo={"edge-a": [[1, 2]]},
        edges_meta=edges_meta,
        mapping=mapping,
        first_poly_fn=lambda edge_name: [1, 2],
        safe_dataframe_fn=lambda frame, height: None,
    )

    payload = json.loads(session_state["svg_mapping_text"])
    assert payload["edges"] == {}
    review = payload["edges_meta"]["edge-a"]["review"]
    assert review["status"] == "rejected"
    assert review["by"] == "clear_geom"
    assert review["ts"] == 456.0
    assert fake_st.rerun_calls == 1
    assert fake_st.successes == ["Геометрия удалена (и помечено rejected)."]


def test_entrypoints_use_shared_svg_mapping_review_panel_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")
    post_mapping_text = POST_MAPPING_HELPERS_PATH.read_text(encoding="utf-8")
    scheme_text = SCHEME_HELPERS_PATH.read_text(encoding="utf-8")
    workbench_text = WORKBENCH_HELPERS_PATH.read_text(encoding="utf-8")
    tools_text = TOOLS_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_svg_scheme_section_helpers import (" in heavy_text
    assert "render_svg_scheme_section(" in app_text
    assert "render_svg_scheme_section(" in heavy_text
    assert "render_svg_mapping_review_panel(" not in app_text
    assert "render_svg_mapping_review_panel(" not in heavy_text
    assert 'st.markdown("#### Изменить статус / заметку для одной ветки")' not in app_text
    assert 'st.markdown("#### Изменить статус / заметку для одной ветки")' not in heavy_text
    assert 'key="btn_map_review_save"' not in app_text
    assert 'key="btn_map_review_save"' not in heavy_text
    assert 'key="btn_map_review_clear_geom"' not in app_text
    assert 'key="btn_map_review_clear_geom"' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_post_mapping_helpers import (" in tools_text
    assert "render_svg_post_mapping_sections(" in tools_text
    assert "from pneumo_solver_ui.ui_svg_mapping_review_section_helpers import (" in post_mapping_text
    assert "render_svg_mapping_review_section(" in post_mapping_text
    assert "from pneumo_solver_ui.ui_svg_mapping_review_panel_helpers import (" in section_text
    assert "render_svg_mapping_review_panel(" in section_text
    assert "def build_svg_mapping_review_rows(" in helper_text
    assert "def render_svg_mapping_review_panel(" in helper_text
