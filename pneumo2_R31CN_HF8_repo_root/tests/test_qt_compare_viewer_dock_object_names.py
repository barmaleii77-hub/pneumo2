from __future__ import annotations

from pathlib import Path


def test_qt_compare_viewer_all_persistent_docks_have_object_names() -> None:
    src = (Path(__file__).resolve().parents[1] / 'pneumo_solver_ui' / 'qt_compare_viewer.py').read_text(encoding='utf-8')

    assert 'dock.setObjectName("dock_controls")' in src
    assert 'dock.setObjectName("dock_deltat_heatmap")' in src
    assert 'dock.setObjectName("dock_influence_heatmap")' in src
    assert 'dock.setObjectName("DockInfluenceT")' in src
    assert 'dock.setObjectName("DockMultivar")' in src
    assert 'dock.setObjectName("dock_qa_suspicious_signals")' in src
    assert 'self.dock_events.setObjectName("dock_events")' in src
