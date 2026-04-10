from __future__ import annotations

import os
import shutil
import warnings
from pathlib import Path

import pytest
from pandas.errors import PerformanceWarning

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtGui, QtWidgets

from pneumo_solver_ui import qt_compare_viewer as viewer_mod
from pneumo_solver_ui import qt_plotly_view as plotly_view_mod


ROOT = Path(__file__).resolve().parents[1]
ANIM_LATEST_NPZ = ROOT / "pneumo_solver_ui" / "workspace" / "exports" / "anim_latest.npz"
ANIM_LATEST_JSON = ROOT / "pneumo_solver_ui" / "workspace" / "exports" / "anim_latest.json"
ANIM_LATEST_ROAD_CSV = ROOT / "pneumo_solver_ui" / "workspace" / "exports" / "anim_latest_road_csv.csv"


class _MemorySettings:
    def __init__(self, *args, **kwargs) -> None:
        self._values: dict[str, object] = {}

    def value(self, key: str, default=None):
        return self._values.get(key, default)

    def setValue(self, key: str, value) -> None:
        self._values[str(key)] = value


def _copy_real_bundle_variants(tmp_path: Path, *, copies: int = 3) -> list[Path]:
    if ANIM_LATEST_ROAD_CSV.exists():
        shutil.copy2(ANIM_LATEST_ROAD_CSV, tmp_path / ANIM_LATEST_ROAD_CSV.name)

    paths: list[Path] = []
    for idx in range(copies):
        dst = tmp_path / f"anim_copy_{idx + 1}.npz"
        shutil.copy2(ANIM_LATEST_NPZ, dst)
        if ANIM_LATEST_JSON.exists():
            shutil.copy2(ANIM_LATEST_JSON, dst.with_name(dst.stem + ".json"))
        paths.append(dst)
    return paths


def _select_table(viewer: viewer_mod.CompareViewer, app: QtWidgets.QApplication) -> str:
    for name in ("p", "open", "main"):
        idx = viewer.combo_table.findText(name)
        if idx >= 0:
            viewer.combo_table.setCurrentIndex(idx)
            app.processEvents()
            return str(viewer.current_table)
    app.processEvents()
    return str(viewer.current_table)


def _select_first_signals(viewer: viewer_mod.CompareViewer, app: QtWidgets.QApplication, *, count: int = 3) -> list[str]:
    picked = min(int(count), int(viewer.list_signals.count()))
    viewer.list_signals.clearSelection()
    for idx in range(picked):
        item = viewer.list_signals.item(idx)
        if item is not None:
            item.setSelected(True)
    viewer._on_signal_selection_changed()
    app.processEvents()
    return list(viewer._selected_signals())


def _count_non_white_samples(image: QtGui.QImage, *, x0: int, y0: int, x1: int, y1: int, step: int = 8) -> int:
    count = 0
    for y in range(max(0, y0), min(int(image.height()), y1), max(1, int(step))):
        for x in range(max(0, x0), min(int(image.width()), x1), max(1, int(step))):
            color = image.pixelColor(x, y)
            if min(color.red(), color.green(), color.blue()) < 245:
                count += 1
    return count


@pytest.mark.skipif(
    not ANIM_LATEST_NPZ.exists(),
    reason="real anim_latest bundle is not available in workspace/exports",
)
def test_qt_compare_viewer_real_bundle_runtime_smoke_syncs_live_analysis_docks(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(viewer_mod.QtCore, "QSettings", _MemorySettings)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewer = viewer_mod.CompareViewer(_copy_real_bundle_variants(tmp_path))
    try:
        viewer.show()
        app.processEvents()

        assert len(viewer.runs) == 3
        assert len(viewer._selected_runs()) == 3
        assert viewer.tbl_events.rowCount() > 0
        assert viewer.lbl_qa_summary.text().startswith("QA:")
        assert viewer.statusBar() is not None
        assert "Runs 3" in viewer.lbl_status_selection.text()
        assert "Table " in viewer.lbl_status_selection.text()
        assert "Events " in viewer.lbl_status_quality.text()
        assert "QA " in viewer.lbl_status_quality.text()
        assert "Focus all" in viewer.lbl_status_layout.text()
        assert "Docks 7/7" in viewer.lbl_status_layout.text()
        assert viewer.lbl_workspace_assistant_title.text() != ""
        assert viewer.lbl_workspace_assistant.text() != ""
        assert viewer.btn_workspace_focus_all.isChecked() is True

        viewer.act_view_focus_heatmaps.trigger()
        app.processEvents()
        assert viewer.dock_heatmap.isVisible()
        assert viewer.dock_influence.isVisible()
        assert viewer.dock_inflheat.isVisible()
        assert not viewer.dock_multivar.isVisible()
        assert "Focus heatmaps" in viewer.lbl_status_layout.text()
        assert "Docks 4/7" in viewer.lbl_status_layout.text()
        assert viewer.btn_workspace_focus_heatmaps.isChecked() is True

        table_name = _select_table(viewer, app)
        selected_signals = _select_first_signals(viewer, app, count=3)
        assert len(selected_signals) == 3
        viewer._rebuild_influence()
        app.processEvents()

        assert len(getattr(viewer, "_heat_run_labels", []) or []) == 3
        assert len(getattr(viewer, "_heat_sig_labels", []) or []) == 3
        assert viewer.tbl_events.rowCount() > 0
        assert "baseline=" in viewer.lbl_events_info.text()
        assert "Runs 3" in viewer.lbl_status_selection.text()
        assert f"Table {table_name}" in viewer.lbl_status_selection.text()
        assert "Signals 3" in viewer.lbl_status_selection.text()
        assert viewer.lbl_workspace_assistant_title.text() == "Heatmap comparison"
        assert "3 selected signals" in viewer.lbl_workspace_assistant.text()
        insights_plain = viewer.txt_workspace_insights.toPlainText()
        assert "Delta hotspot" in insights_plain
        assert "Peak" in insights_plain
        assert "Top meta driver" in insights_plain
        assert ("corr=" in insights_plain) or ("Need influence refresh" in insights_plain) or ("Need 3+ runs" in insights_plain)

        viewer.act_view_focus_multivar.trigger()
        app.processEvents()
        assert viewer.dock_multivar.isVisible()
        assert not viewer.dock_heatmap.isVisible()
        assert "Focus multivar" in viewer.lbl_status_layout.text()
        assert "Docks 2/7" in viewer.lbl_status_layout.text()
        assert viewer.btn_workspace_focus_multivar.isChecked() is True
        assert viewer.lbl_workspace_assistant_title.text() == "Multivariate scouting"

        viewer._update_multivar_views()
        app.processEvents()

        assert table_name == str(viewer.current_table)
        assert viewer._mv_df_full is not None
        assert len(viewer._mv_df_full) == 3
        assert "Runs: 3" in viewer.lbl_mv_status.text()
        assert "Signals: 3" in viewer.lbl_mv_status.text()
        assert "Runs 3" in viewer.lbl_status_selection.text()
        assert "Signals 3" in viewer.lbl_status_selection.text()
        assert "Events " in viewer.lbl_status_quality.text()
        assert "Ref " in viewer.lbl_status_layout.text()
        assert "3 runs and 3 signals" in viewer.lbl_workspace_assistant.text()
        insights_plain = viewer.txt_workspace_insights.toPlainText()
        assert "Quality / next step" in insights_plain
        assert ("Ready for all-to-all scouting" in insights_plain) or ("QA flagged" in insights_plain) or ("Trust attention required" in insights_plain)
    finally:
        viewer.close()
        app.processEvents()


@pytest.mark.skipif(
    not ANIM_LATEST_NPZ.exists(),
    reason="real anim_latest bundle is not available in workspace/exports",
)
def test_qt_compare_viewer_real_bundle_multivar_update_avoids_fragmentation_warnings(monkeypatch, tmp_path: Path) -> None:
    if (viewer_mod.PlotlyWebView is None) or (not bool(getattr(viewer_mod, "HAVE_QTWEBENGINE", False))):
        pytest.skip("multivariate runtime requires Plotly + QtWebEngine")

    monkeypatch.setattr(viewer_mod.QtCore, "QSettings", _MemorySettings)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewer = viewer_mod.CompareViewer(_copy_real_bundle_variants(tmp_path))
    try:
        viewer.show()
        app.processEvents()

        _select_table(viewer, app)
        selected_signals = _select_first_signals(viewer, app, count=3)
        assert len(selected_signals) == 3

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            viewer._update_multivar_views()
            app.processEvents()

        perf_warnings = [w for w in caught if isinstance(w.message, PerformanceWarning)]
        assert perf_warnings == []
        assert viewer._mv_df_full is not None
        assert len(viewer._mv_df_full) == 3
        assert "Runs: 3" in viewer.lbl_mv_status.text()
    finally:
        viewer.close()
        app.processEvents()


@pytest.mark.skipif(
    not ANIM_LATEST_NPZ.exists(),
    reason="real anim_latest bundle is not available in workspace/exports",
)
def test_qt_compare_viewer_real_bundle_can_export_workspace_snapshot_set(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(viewer_mod.QtCore, "QSettings", _MemorySettings)

    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = tmp_path / "snapshots"

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewer = viewer_mod.CompareViewer(_copy_real_bundle_variants(bundle_dir))
    try:
        viewer.resize(1600, 960)
        viewer.show()
        app.processEvents()

        _select_table(viewer, app)
        selected_signals = _select_first_signals(viewer, app, count=3)
        assert len(selected_signals) == 3

        exports = viewer._export_workspace_snapshot_set(snapshot_dir)
        export_names = [path.name for path in exports]
        assert export_names == [
            "compare_workspace_overview.png",
            "compare_workspace_heatmaps.png",
            "compare_workspace_multivariate.png",
            "compare_workspace_qa.png",
        ]

        for path in exports:
            assert path.exists()
            assert path.stat().st_size > 10_000
            image = QtGui.QImage(str(path))
            assert not image.isNull()
            assert image.width() >= 1200
            assert image.height() >= 700

        if bool(getattr(viewer_mod, "HAVE_QTWEBENGINE", False)) and bool(getattr(plotly_view_mod, "HAVE_KALEIDO", False)):
            multivar_image = QtGui.QImage(str(snapshot_dir / "compare_workspace_multivariate.png"))
            assert not multivar_image.isNull()
            non_white = _count_non_white_samples(
                multivar_image,
                x0=int(multivar_image.width() * 0.52),
                y0=int(multivar_image.height() * 0.18),
                x1=int(multivar_image.width() * 0.97),
                y1=int(multivar_image.height() * 0.92),
                step=8,
            )
            assert non_white > 200

        assert viewer.menu_view.title() == "View"
        assert viewer.dock_controls.isVisible()
        assert str(viewer.current_table) in {"p", "open", "main"}
    finally:
        viewer.close()
        app.processEvents()
