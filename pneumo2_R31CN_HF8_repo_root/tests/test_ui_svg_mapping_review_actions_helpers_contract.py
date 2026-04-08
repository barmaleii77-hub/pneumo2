from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui import ui_svg_mapping_review_actions_helpers as action_helpers
from pneumo_solver_ui.ui_svg_mapping_review_actions_helpers import (
    approve_all_pass_svg_mapping_routes,
    recompute_svg_mapping_route_quality,
    render_svg_mapping_review_actions,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_review_actions_helpers.py"
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
        self.captions: list[str] = []
        self.successes: list[str] = []
        self.errors: list[str] = []
        self.rerun_calls = 0

    def columns(self, spec) -> list[_FakeBlock]:
        count = spec if isinstance(spec, int) else len(spec)
        return [_FakeBlock() for _ in range(count)]

    def button(self, label: str, key: str | None = None):
        return bool(self.button_presses.get(str(key), False))

    def caption(self, text: str) -> None:
        self.captions.append(text)

    def success(self, text: str) -> None:
        self.successes.append(text)

    def error(self, text: str) -> None:
        self.errors.append(text)

    def rerun(self) -> None:
        self.rerun_calls += 1


def test_recompute_svg_mapping_route_quality_updates_meta_and_session(monkeypatch) -> None:
    session_state = {
        "route_q_min_turn_deg": 45.0,
        "route_q_max_detour": 8.0,
        "route_q_max_attach_dist": 35.0,
    }
    mapping = {"edges_meta": {}}
    edges_meta: dict[str, object] = {}

    monkeypatch.setattr(action_helpers.time, "time", lambda: 123.0)

    recompute_svg_mapping_route_quality(
        session_state,
        edges_geo={"edge-a": [[1, 2]], "edge-b": [[2, 3]]},
        edges_meta=edges_meta,
        mapping=mapping,
        first_poly_fn=lambda edge_name: [edge_name] if edge_name == "edge-a" else None,
        evaluate_quality_fn=lambda poly, **kwargs: {"grade": "PASS", "poly": poly},
    )

    payload = json.loads(session_state["svg_mapping_text"])
    review = payload["edges_meta"]["edge-a"]["review"]
    assert payload["edges_meta"]["edge-a"]["quality"]["grade"] == "PASS"
    assert review["status"] == "pending"
    assert review["by"] == "quality_recompute"
    assert review["ts"] == 123.0
    assert "edge-b" not in payload["edges_meta"]


def test_approve_all_pass_svg_mapping_routes_marks_only_pass(monkeypatch) -> None:
    session_state: dict[str, object] = {}
    mapping = {"edges_meta": {}}
    edges_meta = {
        "edge-a": {"quality": {"grade": "PASS"}, "review": {"status": "pending"}},
        "edge-b": {"quality": {"grade": "WARN"}, "review": {"status": "pending"}},
    }

    monkeypatch.setattr(action_helpers.time, "time", lambda: 456.0)

    approved = approve_all_pass_svg_mapping_routes(
        session_state,
        edges_meta=edges_meta,
        mapping=mapping,
    )

    payload = json.loads(session_state["svg_mapping_text"])
    assert approved == 1
    assert payload["edges_meta"]["edge-a"]["review"]["status"] == "approved"
    assert payload["edges_meta"]["edge-a"]["review"]["by"] == "approve_pass"
    assert payload["edges_meta"]["edge-a"]["review"]["ts"] == 456.0
    assert payload["edges_meta"]["edge-b"]["review"]["status"] == "pending"


def test_render_svg_mapping_review_actions_handles_buttons(monkeypatch) -> None:
    fake_st = _FakeStreamlit(button_presses={"btn_map_recompute_quality": True})
    session_state: dict[str, object] = {}
    calls: list[str] = []

    monkeypatch.setattr(
        action_helpers,
        "recompute_svg_mapping_route_quality",
        lambda *args, **kwargs: calls.append("recompute"),
    )

    render_svg_mapping_review_actions(
        fake_st,
        session_state,
        edges_geo={"edge-a": [[1, 2]]},
        edges_meta={},
        mapping={},
        first_poly_fn=lambda edge_name: [1, 2],
        evaluate_quality_fn=lambda *args, **kwargs: {},
    )

    assert calls == ["recompute"]
    assert fake_st.rerun_calls == 1
    assert fake_st.successes == ["Quality пересчитан и сохранён в mapping JSON (text area ниже обновится после rerun)."]
    assert fake_st.errors == []


def test_entrypoints_use_shared_svg_mapping_review_actions_helper() -> None:
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
    assert "render_svg_mapping_review_actions(" not in app_text
    assert "render_svg_mapping_review_actions(" not in heavy_text
    assert 'key="btn_map_recompute_quality"' not in app_text
    assert 'key="btn_map_recompute_quality"' not in heavy_text
    assert 'key="btn_map_approve_pass"' not in app_text
    assert 'key="btn_map_approve_pass"' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_post_mapping_helpers import (" in tools_text
    assert "render_svg_post_mapping_sections(" in tools_text
    assert "from pneumo_solver_ui.ui_svg_mapping_review_section_helpers import (" in post_mapping_text
    assert "render_svg_mapping_review_section(" in post_mapping_text
    assert "from pneumo_solver_ui.ui_svg_mapping_review_actions_helpers import (" in section_text
    assert "render_svg_mapping_review_actions(" in section_text
    assert "def recompute_svg_mapping_route_quality(" in helper_text
    assert "def approve_all_pass_svg_mapping_routes(" in helper_text
    assert "def render_svg_mapping_review_actions(" in helper_text
