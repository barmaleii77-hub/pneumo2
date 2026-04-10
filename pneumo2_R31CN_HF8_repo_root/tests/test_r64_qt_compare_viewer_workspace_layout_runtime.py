from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets

from pneumo_solver_ui import qt_compare_viewer as viewer_mod


class _MemorySettings:
    def __init__(self, *args, **kwargs) -> None:
        self._values: dict[str, object] = {}

    def value(self, key: str, default=None):
        return self._values.get(key, default)

    def setValue(self, key: str, value) -> None:
        self._values[str(key)] = value


def test_compare_viewer_view_menu_exposes_workspace_presets_and_dock_families(monkeypatch) -> None:
    monkeypatch.setattr(viewer_mod.QtCore, "QSettings", _MemorySettings)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewer = viewer_mod.CompareViewer([])
    try:
        viewer.show()
        app.processEvents()

        assert getattr(viewer, "menu_view", None) is not None
        assert viewer.menu_view.title() == "View"
        assert viewer.statusBar() is not None
        assert viewer.statusBar().objectName() == "workspaceStatusBar"
        assert viewer.lbl_status_selection.objectName() == "statusChipSelection"
        assert viewer.lbl_status_quality.objectName() == "statusChipQuality"
        assert viewer.lbl_status_layout.objectName() == "statusChipLayout"
        assert "QStatusBar#workspaceStatusBar" in viewer.styleSheet()
        assert "Runs 0" in viewer.lbl_status_selection.text()
        assert "Focus all" in viewer.lbl_status_layout.text()
        assert "Docks 7/7" in viewer.lbl_status_layout.text()
        assert viewer.lbl_workspace_assistant_title.text() == "Load compare bundle"
        assert "2+ NPZ runs" in viewer.lbl_workspace_assistant.text()
        assert viewer.btn_workspace_focus_all.isChecked() is True
        assert viewer.btn_workspace_focus_heatmaps.isChecked() is False
        assert viewer.btn_workspace_focus_multivar.isChecked() is False
        assert viewer.btn_workspace_focus_qa.isChecked() is False
        assert viewer.txt_workspace_insights.objectName() == "workspaceInsightsBrowser"
        insights_plain = viewer.txt_workspace_insights.toPlainText()
        assert "Delta hotspot" in insights_plain
        assert "Need comparison context" in insights_plain
        assert "Top meta driver" in insights_plain
        assert "Load a compare set" in insights_plain

        dock_action_texts = [action.text() for action in viewer.menu_view_docks.actions()]
        assert dock_action_texts == [
            "Controls",
            "Δ(t) Heatmap",
            "Influence(t)",
            "Influence(t) Heatmap",
            "Multivariate",
            "QA",
            "Events",
        ]

        viewer.act_view_focus_heatmaps.trigger()
        app.processEvents()

        assert viewer.dock_controls.isVisible()
        assert viewer.dock_heatmap.isVisible()
        assert viewer.dock_influence.isVisible()
        assert viewer.dock_inflheat.isVisible()
        assert not viewer.dock_multivar.isVisible()
        assert not viewer.dock_qa.isVisible()
        assert not viewer.dock_events.isVisible()
        assert "Focus heatmaps" in viewer.lbl_status_layout.text()
        assert "Docks 4/7" in viewer.lbl_status_layout.text()
        assert viewer.btn_workspace_focus_heatmaps.isChecked() is True
        assert viewer.btn_workspace_focus_all.isChecked() is False

        viewer.btn_workspace_focus_multivar.click()
        app.processEvents()

        assert viewer.dock_controls.isVisible()
        assert viewer.dock_multivar.isVisible()
        assert not viewer.dock_heatmap.isVisible()
        assert not viewer.dock_qa.isVisible()
        assert "Focus multivar" in viewer.lbl_status_layout.text()
        assert "Docks 2/7" in viewer.lbl_status_layout.text()
        assert viewer.btn_workspace_focus_multivar.isChecked() is True

        viewer.act_view_focus_qa.trigger()
        app.processEvents()

        assert viewer.dock_controls.isVisible()
        assert viewer.dock_qa.isVisible()
        assert viewer.dock_events.isVisible()
        assert not viewer.dock_heatmap.isVisible()
        assert not viewer.dock_influence.isVisible()
        assert not viewer.dock_inflheat.isVisible()
        assert not viewer.dock_multivar.isVisible()
        assert "Focus qa/events" in viewer.lbl_status_layout.text()
        assert "Docks 3/7" in viewer.lbl_status_layout.text()
        assert viewer.btn_workspace_focus_qa.isChecked() is True

        viewer.act_view_show_all_docks.trigger()
        app.processEvents()

        for dock in (
            viewer.dock_controls,
            viewer.dock_heatmap,
            viewer.dock_influence,
            viewer.dock_inflheat,
            viewer.dock_multivar,
            viewer.dock_qa,
            viewer.dock_events,
        ):
            assert dock.isVisible()
            assert dock.isFloating() is False
        assert "Focus all" in viewer.lbl_status_layout.text()
        assert "Docks 7/7" in viewer.lbl_status_layout.text()
        assert viewer.btn_workspace_focus_all.isChecked() is True

        assert viewer.dockWidgetArea(viewer.dock_controls) == QtCore.Qt.LeftDockWidgetArea
        assert viewer.dockWidgetArea(viewer.dock_heatmap) == QtCore.Qt.RightDockWidgetArea
        assert viewer.dockWidgetArea(viewer.dock_qa) == QtCore.Qt.RightDockWidgetArea

        heat_family = {dock.objectName() for dock in viewer.tabifiedDockWidgets(viewer.dock_heatmap)}
        assert heat_family == {"DockInfluenceT", "dock_influence_heatmap", "DockMultivar"}

        qa_family = {dock.objectName() for dock in viewer.tabifiedDockWidgets(viewer.dock_qa)}
        assert qa_family == {"dock_events"}

        viewer.dock_heatmap.hide()
        app.processEvents()
        assert not viewer.dock_heatmap.isVisible()

        viewer.act_view_reset_workspace.trigger()
        app.processEvents()

        assert viewer.dock_heatmap.isVisible()
        assert viewer.dock_controls.isFloating() is False
        assert viewer.dock_heatmap.isFloating() is False
        assert viewer.dock_qa.isFloating() is False
        assert "Focus all" in viewer.lbl_status_layout.text()
        assert "Docks 7/7" in viewer.lbl_status_layout.text()
    finally:
        viewer.close()
        app.processEvents()
