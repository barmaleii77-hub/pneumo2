from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.svg_autotrace import analysis_polylines_to_coords


def test_analysis_polylines_to_coords_resolves_node_ids() -> None:
    analysis = {
        "nodes": [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)],
        "polylines": [[0, 1, 2]],
    }
    assert analysis_polylines_to_coords(analysis) == [[(0.0, 0.0), (10.0, 0.0), (10.0, 5.0)]]


def test_pneumo_scheme_pages_use_analysis_dict_not_legacy_tuple_unpack() -> None:
    root = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "pages"
    mnemo = (root / "15_PneumoScheme_Mnemo.py").read_text(encoding="utf-8")
    graph = (root / "16_PneumoScheme_Graph.py").read_text(encoding="utf-8")

    assert 'analysis_polylines_to_coords' in mnemo
    assert 'analysis_polylines_to_coords' in graph
    assert 'polylines, texts = extract_polylines' not in mnemo
    assert 'polylines, texts = _cached_extract_polylines' not in graph
    assert 'analysis = extract_polylines(svg_text)' in mnemo
    assert 'analysis = _cached_extract_polylines(svg_text, mtime)' in graph
