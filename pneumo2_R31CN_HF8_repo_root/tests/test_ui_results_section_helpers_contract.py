from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui import ui_results_section_helpers as helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_section_helpers.py"
SURFACE_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_results_surface_section_helpers.py"


class _FakeStreamlit:
    def __init__(self) -> None:
        self.radio = object()


def test_render_results_section_dispatches_graph_branch() -> None:
    calls: list[tuple[str, object]] = []
    original_selector = helpers.render_results_view_selector
    try:
        helpers.render_results_view_selector = lambda **kwargs: "Графики"  # type: ignore[assignment]
        selected = helpers.render_results_section(
            _FakeStreamlit(),
            options=["Графики", "Потоки"],
            session_state={"demo": True},
            cur_hash="hash-1",
            test_pick="test-1",
            log_event_fn=lambda *args, **kwargs: None,
            render_results_graph_section_fn=lambda st, **kwargs: calls.append(("graph", kwargs["token"])),
            results_graph_section_kwargs={"token": "graph-token"},
            render_secondary_results_views_fn=lambda st, **kwargs: calls.append(("secondary", kwargs["view_res"])),
            secondary_results_views_kwargs={"token": "secondary-token"},
        )
    finally:
        helpers.render_results_view_selector = original_selector  # type: ignore[assignment]

    assert selected == "Графики"
    assert calls == [("graph", "graph-token")]


def test_render_results_section_dispatches_secondary_branch() -> None:
    calls: list[tuple[str, object]] = []
    original_selector = helpers.render_results_view_selector
    try:
        helpers.render_results_view_selector = lambda **kwargs: "Анимация"  # type: ignore[assignment]
        selected = helpers.render_results_section(
            _FakeStreamlit(),
            options=["Графики", "Анимация"],
            session_state={"demo": True},
            cur_hash="hash-2",
            test_pick="test-2",
            log_event_fn=lambda *args, **kwargs: None,
            render_results_graph_section_fn=lambda st, **kwargs: calls.append(("graph", kwargs["token"])),
            results_graph_section_kwargs={"token": "graph-token"},
            render_secondary_results_views_fn=lambda st, **kwargs: calls.append(("secondary", kwargs["view_res"])),
            secondary_results_views_kwargs={
                "flow_view_label": "Потоки",
                "energy_audit_view_label": "Энерго-аудит",
                "animation_view_label": "Анимация",
            },
        )
    finally:
        helpers.render_results_view_selector = original_selector  # type: ignore[assignment]

    assert selected == "Анимация"
    assert calls == [("secondary", "Анимация")]


def test_entrypoints_use_shared_results_section_helper() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")
    helper_text = HELPERS_PATH.read_text(encoding="utf-8")
    surface_text = SURFACE_HELPERS_PATH.read_text(encoding="utf-8")
    section_text = SECTION_HELPERS_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_results_section_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_results_section_helpers import (" not in heavy_text
    assert "from pneumo_solver_ui.ui_results_surface_helpers import (" not in app_text
    assert "from pneumo_solver_ui.ui_results_surface_helpers import (" not in heavy_text
    assert "from pneumo_solver_ui.ui_results_surface_section_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_results_surface_section_helpers import (" in heavy_text
    assert "render_results_section(" not in app_text
    assert "render_results_section(" not in heavy_text
    assert "render_results_surface(" not in app_text
    assert "render_results_surface(" not in heavy_text
    assert "render_results_view_selector(" not in app_text
    assert "render_results_view_selector(" not in heavy_text
    assert "render_results_graph_section(" not in app_text
    assert "render_results_graph_section(" not in heavy_text
    assert "render_secondary_results_views(" not in app_text
    assert "render_secondary_results_views(" not in heavy_text
    assert "view_res == " not in app_text
    assert "view_res == " not in heavy_text
    assert 'graph_view_label: str = "Графики"' in helper_text
    assert "def render_results_section(" in helper_text
    assert "render_results_view_selector(" in helper_text
    assert "render_results_section_fn(st, **results_section_bound_kwargs)" in surface_text
    assert "render_results_surface(" in section_text
    assert "render_results_graph_section_fn(st, **results_graph_section_kwargs)" in helper_text
    assert "render_secondary_results_views_fn(" in helper_text
