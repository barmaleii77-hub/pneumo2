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
        assert viewer.menu_view.title() == "\u0412\u0438\u0434"
        assert viewer.statusBar() is not None
        assert viewer.statusBar().isSizeGripEnabled() is True
        assert viewer.statusBar().objectName() == "workspaceStatusBar"
        assert viewer.lbl_status_selection.objectName() == "statusChipSelection"
        assert viewer.lbl_status_quality.objectName() == "statusChipQuality"
        assert viewer.lbl_status_layout.objectName() == "statusChipLayout"
        assert "QStatusBar#workspaceStatusBar" in viewer.styleSheet()
        assert "\u041f\u0440\u043e\u0433\u043e\u043d\u044b 0" in viewer.lbl_status_selection.text()
        assert "\u0424\u043e\u043a\u0443\u0441 \u041e\u0431\u0437\u043e\u0440" in viewer.lbl_status_layout.text()
        assert "\u041f\u0430\u043d\u0435\u043b\u0438 12/12" in viewer.lbl_status_layout.text()
        assert viewer.lbl_workspace_assistant_title.text() != ""
        assert viewer.lbl_workspace_assistant.text() != ""
        assert viewer.btn_workspace_focus_all.isChecked() is True
        assert viewer.btn_workspace_focus_heatmaps.isChecked() is False
        assert viewer.btn_workspace_focus_multivar.isChecked() is False
        assert viewer.btn_workspace_focus_qa.isChecked() is False
        assert viewer.txt_workspace_insights.objectName() == "workspaceInsightsBrowser"
        assert viewer.dock_controls.widget().__class__.__name__ == "QScrollArea"

        insights_plain = viewer.txt_workspace_insights.toPlainText()
        assert "Delta hotspot" in insights_plain
        assert "Need comparison context" in insights_plain
        assert "Top meta driver" in insights_plain
        assert "Load a compare set" in insights_plain

        dock_action_texts = [action.text() for action in viewer.menu_view_docks.actions()]
        assert dock_action_texts[:7] == [
            "\u041f\u0443\u043b\u044c\u0442",
            "\u0422\u0435\u043f\u043b\u043e\u043a\u0430\u0440\u0442\u0430 \u0394(t)",
            "\u041f\u0438\u043a\u0438 |\u0394|",
            "\u0425\u043e\u0434 \u043a\u043b\u0430\u043f\u0430\u043d\u043e\u0432",
            "\u0412\u043b\u0438\u044f\u043d\u0438\u0435(t)",
            "\u041c\u0435\u0442\u0440\u0438\u043a\u0438 \u043f\u0440\u043e\u0433\u043e\u043d\u043e\u0432",
            "\u0421\u0442\u0430\u0442\u0438\u043a\u0430 / \u0445\u043e\u0434 \u0448\u0442\u043e\u043a\u0430",
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
        assert "\u0424\u043e\u043a\u0443\u0441 \u0422\u0435\u043f\u043b\u043e\u043a\u0430\u0440\u0442\u044b" in viewer.lbl_status_layout.text()
        assert "\u041f\u0430\u043d\u0435\u043b\u0438 8/12" in viewer.lbl_status_layout.text()
        assert viewer.btn_workspace_focus_heatmaps.isChecked() is True
        assert viewer.btn_workspace_focus_all.isChecked() is False

        viewer.btn_workspace_focus_multivar.click()
        app.processEvents()

        assert viewer.dock_controls.isVisible()
        assert viewer.dock_multivar.isVisible()
        assert not viewer.dock_heatmap.isVisible()
        assert not viewer.dock_qa.isVisible()
        assert "\u0424\u043e\u043a\u0443\u0441 \u041c\u043d\u043e\u0433\u043e\u043c\u0435\u0440\u043d\u044b\u0439" in viewer.lbl_status_layout.text()
        assert "\u041f\u0430\u043d\u0435\u043b\u0438 2/12" in viewer.lbl_status_layout.text()
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
        assert "\u0424\u043e\u043a\u0443\u0441 \u041f\u0440\u043e\u0432\u0435\u0440\u043a\u0430 / \u0441\u043e\u0431\u044b\u0442\u0438\u044f" in viewer.lbl_status_layout.text()
        assert "\u041f\u0430\u043d\u0435\u043b\u0438 4/12" in viewer.lbl_status_layout.text()
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
        assert "\u0424\u043e\u043a\u0443\u0441 \u041e\u0431\u0437\u043e\u0440" in viewer.lbl_status_layout.text()
        assert "\u041f\u0430\u043d\u0435\u043b\u0438 12/12" in viewer.lbl_status_layout.text()
        assert viewer.btn_workspace_focus_all.isChecked() is True

        assert viewer.dockWidgetArea(viewer.dock_controls) == QtCore.Qt.LeftDockWidgetArea
        assert viewer.dockWidgetArea(viewer.dock_heatmap) == QtCore.Qt.RightDockWidgetArea
        assert viewer.dockWidgetArea(viewer.dock_qa) == QtCore.Qt.RightDockWidgetArea

        heat_family = {dock.objectName() for dock in viewer.tabifiedDockWidgets(viewer.dock_heatmap)}
        assert heat_family == {
            "DockInfluenceT",
            "DockMultivar",
            "dock_influence_heatmap",
            "dock_open_timeline",
            "dock_peak_heatmap",
            "dock_run_metrics",
            "dock_static_stroke",
        }

        qa_family = {dock.objectName() for dock in viewer.tabifiedDockWidgets(viewer.dock_qa)}
        assert qa_family == {"dock_events", "dock_geometry_acceptance"}

        viewer.dock_heatmap.hide()
        app.processEvents()
        assert not viewer.dock_heatmap.isVisible()

        viewer.act_view_reset_workspace.trigger()
        app.processEvents()

        assert viewer.dock_heatmap.isVisible()
        assert viewer.dock_controls.isFloating() is False
        assert viewer.dock_heatmap.isFloating() is False
        assert viewer.dock_qa.isFloating() is False
        assert "\u0424\u043e\u043a\u0443\u0441 \u041e\u0431\u0437\u043e\u0440" in viewer.lbl_status_layout.text()
        assert "\u041f\u0430\u043d\u0435\u043b\u0438 12/12" in viewer.lbl_status_layout.text()
    finally:
        viewer.close()
        app.processEvents()
