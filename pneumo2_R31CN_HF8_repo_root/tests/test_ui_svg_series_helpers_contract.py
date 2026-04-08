from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui.ui_svg_series_helpers import prepare_svg_animation_series


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"
HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_series_helpers.py"
SECTION_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_animation_section_helpers.py"
POST_MAPPING_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_post_mapping_helpers.py"
SCHEME_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_scheme_section_helpers.py"
WORKBENCH_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_workbench_section_helpers.py"
TOOLS_HELPERS_PATH = REPO_ROOT / "pneumo_solver_ui" / "ui_svg_mapping_tools_section_helpers.py"


def test_prepare_svg_animation_series_builds_edges_and_missing_lists() -> None:
    df_mdot = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "edge_a": [1.0, 2.0],
            "edge_b": [3.0, 4.0],
        }
    )
    df_open = pd.DataFrame(
        {
            "время_с": [0.0, 1.0],
            "edge_b": [0, 1],
        }
    )
    result = prepare_svg_animation_series(
        df_mdot=df_mdot,
        selected_edges=["edge_a", "edge_b"],
        scale=60.0,
        unit="Нл/мин",
        mapping={"edges": {"edge_b": [[[0.0, 0.0], [1.0, 1.0]]]}, "nodes": {}},
        df_open=df_open,
        df_p=None,
        selected_nodes=[],
        p_atm=101325.0,
        pressure_divisor=101325.0,
        pressure_unit="атм (изб.)",
    )

    assert result["time_s"] == [0.0, 1.0]
    assert result["edge_series"] == [
        {"name": "edge_a", "q": [60.0, 120.0], "open": None, "unit": "Нл/мин"},
        {"name": "edge_b", "q": [180.0, 240.0], "open": [0, 1], "unit": "Нл/мин"},
    ]
    assert result["missing_edges"] == ["edge_a"]
    assert result["node_series"] == []
    assert result["missing_nodes"] == []


def test_prepare_svg_animation_series_builds_nodes_with_interpolation_and_units() -> None:
    df_mdot = pd.DataFrame({"время_с": [0.0, 1.0, 2.0], "edge_a": [1.0, 1.0, 1.0]})
    df_p = pd.DataFrame(
        {
            "время_с": [0.0, 2.0],
            "node_a": [101325.0, 202650.0],
            "node_b": [101325.0, 151987.5],
        }
    )
    result = prepare_svg_animation_series(
        df_mdot=df_mdot,
        selected_edges=["edge_a"],
        scale=1.0,
        unit="x",
        mapping={"edges": {"edge_a": [[[0.0, 0.0], [1.0, 1.0]]]}, "nodes": {"node_a": [1.0, 2.0]}},
        df_open=None,
        df_p=df_p,
        selected_nodes=["node_a", "node_b"],
        p_atm=101325.0,
        pressure_divisor=101325.0,
        pressure_unit="атм (изб.)",
    )

    assert result["node_series"] == [
        {"name": "node_a", "p": [0.0, 0.5, 1.0], "unit": "атм (изб.)"},
        {"name": "node_b", "p": [0.0, 0.25, 0.5], "unit": "атм (изб.)"},
    ]
    assert result["missing_nodes"] == ["node_b"]


def test_entrypoints_use_shared_svg_series_helper() -> None:
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
    assert "prepare_svg_animation_series(" not in app_text
    assert "prepare_svg_animation_series(" not in heavy_text
    assert 'edge_series = []' not in app_text
    assert 'edge_series = []' not in heavy_text
    assert 'missing_nodes = []' not in app_text
    assert 'missing_nodes = []' not in heavy_text
    assert 'p_g = (p_src - P_ATM) / ATM_PA' not in app_text
    assert 'p_g = (p_src - P_ATM) / BAR_PA' not in heavy_text
    assert 'if df_open is not None and c in df_open.columns:' not in app_text
    assert 'if df_open is not None and c in df_open.columns:' not in heavy_text
    assert "from pneumo_solver_ui.ui_svg_mapping_workbench_section_helpers import (" in scheme_text
    assert "render_svg_mapping_workbench_section(" in scheme_text
    assert "from pneumo_solver_ui.ui_svg_mapping_tools_section_helpers import (" in workbench_text
    assert "render_svg_mapping_tools_section(" in workbench_text
    assert "from pneumo_solver_ui.ui_svg_post_mapping_helpers import (" in tools_text
    assert "render_svg_post_mapping_sections(" in tools_text
    assert "from pneumo_solver_ui.ui_svg_animation_section_helpers import (" in post_mapping_text
    assert "render_svg_animation_section(" in post_mapping_text
    assert "from pneumo_solver_ui.ui_svg_series_helpers import (" in section_text
    assert "prepare_svg_animation_series(" in section_text
    assert "pressure_divisor=ATM_PA" in app_text
    assert "pressure_divisor=BAR_PA" in heavy_text
    assert "def prepare_svg_animation_series(" in helper_text
