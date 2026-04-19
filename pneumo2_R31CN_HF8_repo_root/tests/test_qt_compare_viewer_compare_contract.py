from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from pneumo_solver_ui import qt_compare_viewer as viewer_mod
from pneumo_solver_ui.compare_session import CompareSession, dumps as dump_compare_session, loads as load_compare_session
from pneumo_solver_ui.compare_contract import (
    build_compare_contract,
    compare_contract_hash,
    current_vs_historical_mismatch,
    extract_compare_run_ref,
    format_compare_contract_summary,
    format_compare_mismatch_banner,
    load_compare_contract,
    save_compare_contract,
)


class _MemorySettings:
    def __init__(self, *args, **kwargs) -> None:
        self._values: dict[str, object] = {}

    def value(self, key: str, default=None):
        return self._values.get(key, default)

    def setValue(self, key: str, value) -> None:
        self._values[str(key)] = value


def _ref(
    label: str,
    *,
    objective: str = "obj-a",
    gate: str = "penalty",
    baseline: str = "base-a",
    source: str = "source-a",
) -> dict:
    return {
        "label": label,
        "source_path": f"C:/runs/{label}.npz",
        "run_id": label,
        "run_contract_hash": f"run-{label}",
        "objective_contract_hash": objective,
        "hard_gate_key": gate,
        "hard_gate_tolerance": "0.1",
        "active_baseline_hash": baseline,
        "suite_snapshot_hash": "suite-a",
        "scenario_lineage_hash": "scenario-a",
        "ring_source_hash": source,
    }


def test_compare_contract_hash_is_stable_and_sensitive_to_contract_refs() -> None:
    a = build_compare_contract([_ref("left"), _ref("right")], selected_metrics=["p_fr", "z_fl"])
    same_without_hash = dict(a)
    same_without_hash["compare_contract_hash"] = "ignored"

    assert len(a["compare_contract_hash"]) == 64
    assert compare_contract_hash(same_without_hash) == a["compare_contract_hash"]

    changed = build_compare_contract(
        [_ref("left"), _ref("right", objective="obj-b")],
        selected_metrics=["p_fr", "z_fl"],
    )
    changed_gate = build_compare_contract(
        [_ref("left"), _ref("right", gate="hard_gate_b")],
        selected_metrics=["p_fr", "z_fl"],
    )
    changed_baseline = build_compare_contract(
        [_ref("left"), _ref("right", baseline="base-b")],
        selected_metrics=["p_fr", "z_fl"],
    )

    assert changed["compare_contract_hash"] != a["compare_contract_hash"]
    assert changed_gate["compare_contract_hash"] != a["compare_contract_hash"]
    assert changed_baseline["compare_contract_hash"] != a["compare_contract_hash"]
    assert changed["mismatch_banner"]["banner_id"] == "BANNER-HIST-002"
    assert "objective_contract_hash" in changed["mismatch_banner"]["mismatch_dimensions"]


def test_compare_contract_summary_surfaces_selected_run_and_source_hash() -> None:
    contract = build_compare_contract(
        [_ref("selected-a", source="ring-src-a"), _ref("selected-b", source="ring-src-b")],
        selected_metrics=["p_fr"],
    )

    text = format_compare_contract_summary(contract)

    assert "Метки выбранных расчётов: selected-a, selected-b" in text
    assert "Хэш источника: ring-src-a, ring-src-b" in text
    assert "Хэш цели: obj-a" in text
    assert "Хэш базового прогона: base-a" in text
    assert "Сохранение: сессия сравнения; файл правил сравнения" in text
    for service_text in ("Хэш baseline", "Действия экспорта", "compare_contract.json"):
        assert service_text not in text


def test_compare_contract_sidecar_round_trips_without_rehashing_export_evidence(tmp_path: Path) -> None:
    contract = build_compare_contract([_ref("left"), _ref("right")], selected_table="main")
    contract["export_only_note"] = "evidence"
    path = tmp_path / "compare_contract.json"

    save_compare_contract(path, contract)
    loaded = load_compare_contract(path)

    assert loaded["compare_contract_hash"] == contract["compare_contract_hash"]
    assert loaded["run_refs"][0]["run_contract_hash"] == "run-left"
    assert loaded["selected_table"] == "main"


def test_compare_session_current_context_path_round_trips_and_ignores_future_fields() -> None:
    sess = CompareSession(
        npz_paths=["C:/runs/history.npz"],
        labels=["history"],
        current_context_ref={"run_id": "current", "objective_contract_hash": "obj-current"},
        current_context_path="C:/runs/latest_compare_current_context.json",
        current_context_ref_source_path="C:/runs/latest_compare_current_context.json",
        current_context_ref_source_status="missing",
        run_refs=[_ref("history", objective="obj-old")],
        session_source="current_context_sidecar",
    )
    obj = json.loads(dump_compare_session(sess))
    obj["future_compare_field"] = {"ignored": True}

    loaded = load_compare_session(json.dumps(obj, ensure_ascii=False))

    assert loaded.current_context_path == "C:/runs/latest_compare_current_context.json"
    assert loaded.current_context_ref_source_path == "C:/runs/latest_compare_current_context.json"
    assert loaded.current_context_ref_source_status == "missing"
    assert loaded.current_context_ref["run_id"] == "current"
    assert loaded.run_refs[0]["run_id"] == "history"
    assert not hasattr(loaded, "future_compare_field")


def test_current_vs_historical_mismatch_uses_historical_banner_policy() -> None:
    current = _ref("current", objective="obj-current", gate="gate-current", baseline="base-current")
    historical = _ref("history", objective="obj-old", gate="gate-old", baseline="base-current")

    summary = current_vs_historical_mismatch(current, historical)

    assert summary["banner_id"] == "BANNER-HIST-002"
    assert summary["severity"] == "warning"
    assert set(summary["mismatch_dimensions"]) >= {"objective_contract_hash", "hard_gate_key"}
    banner_text = format_compare_mismatch_banner(summary)
    assert "сохранённого прогона" in banner_text
    assert "хэш цели" in banner_text


def test_extract_compare_run_ref_keeps_baseline_objective_and_run_refs(tmp_path: Path) -> None:
    npz = tmp_path / "T01_osc.npz"
    meta = {
        "selected_run_contract": {
            "run_id": "run-001",
            "run_contract_hash": "run-hash",
            "objective_contract_hash": "obj-hash",
            "active_baseline_hash": "base-hash",
            "suite_snapshot_hash": "suite-hash",
        },
        "objective_contract": {
            "objective_contract_hash": "obj-hash",
            "penalty_key": "max_pressure",
            "penalty_tol": 0.2,
        },
        "active_baseline_contract": {
            "active_baseline_hash": "base-hash",
            "suite_snapshot_hash": "suite-hash",
            "contract_path": "active_baseline_contract.json",
        },
        "scenario_lineage_hash": "scenario-hash",
        "compare_contract_path": "compare_contract.json",
    }

    ref = extract_compare_run_ref(meta, npz_path=npz, label="T01")

    assert ref["run_id"] == "run-001"
    assert ref["run_contract_hash"] == "run-hash"
    assert ref["objective_contract_hash"] == "obj-hash"
    assert ref["hard_gate_key"] == "max_pressure"
    assert ref["active_baseline_hash"] == "base-hash"
    assert ref["compare_contract_path"] == "compare_contract.json"
    assert ref["baseline_ref"]["active_baseline_hash"] == "base-hash"
    assert ref["baseline_ref"]["suite_snapshot_hash"] == "suite-hash"
    assert ref["objective_ref"]["objective_contract_hash"] == "obj-hash"
    assert ref["objective_ref"]["hard_gate_tolerance"] == 0.2


def _write_npz(path: Path, *, label: str, objective: str) -> None:
    meta = {
        "test_name": label,
        "selected_run_contract": {
            "run_id": label,
            "run_contract_hash": f"run-{label}",
            "objective_contract_hash": objective,
            "active_baseline_hash": "base-a",
            "suite_snapshot_hash": "suite-a",
            "scenario_lineage_hash": "scenario-a",
            "ring_source_hash": f"ring-{label}",
        },
        "objective_contract": {
            "objective_contract_hash": objective,
            "penalty_key": "pressure_gate",
            "penalty_tol": 0.1,
        },
    }
    np.savez(
        path,
        main_cols=np.asarray(["время_с", "pressure"], dtype=object),
        main_values=np.asarray([[0.0, 1.0], [0.1, 1.2]], dtype=float),
        meta_json=json.dumps(meta, ensure_ascii=False),
    )


def test_qt_compare_viewer_surfaces_compare_contract_and_mismatch_banner(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(viewer_mod.QtCore, "QSettings", _MemorySettings)
    left = tmp_path / "left.npz"
    right = tmp_path / "right.npz"
    _write_npz(left, label="left", objective="obj-a")
    _write_npz(right, label="right", objective="obj-b")

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewer = viewer_mod.CompareViewer([left, right])
    try:
        viewer.show()
        app.processEvents()

        assert len(viewer.runs) == 2
        assert viewer.dock_compare_contract.objectName() == "dock_compare_contract"
        assert viewer.dock_compare_contract.isVisible()
        assert "Правила сравнения" in [action.text() for action in viewer.menu_view_docks.actions()]
        assert viewer.compare_contract_hash
        summary_text = viewer.txt_compare_contract.toPlainText()
        assert "Хэш правил сравнения:" in summary_text
        assert "Метки выбранных расчётов: left, right" in summary_text
        assert "Хэш расчёта: run-left, run-right" in summary_text
        assert "Хэш источника: ring-left, ring-right" in summary_text
        assert "Хэш цели: obj-a, obj-b" in summary_text
        assert "Хэш базового прогона: base-a" in summary_text
        assert "Предупреждение: контекст отличается: хэш цели" in summary_text
        assert "Сохранение: сессия сравнения; файл правил сравнения" in summary_text
        for service_text in ("Compare contract", "Контракт расчёта", "compare_contract.json", "workspace"):
            assert service_text not in summary_text
        assert viewer.lbl_compare_mismatch.isVisible()
        assert "сохранённого прогона" in viewer.lbl_compare_mismatch.text()
        assert "Правила " in viewer.lbl_status_quality.text()
        assert "Compare " not in viewer.lbl_status_quality.text()
        visible_status = "\n".join(
            [
                viewer.lbl_status_selection.text(),
                viewer.lbl_status_quality.text(),
                viewer.lbl_status_layout.text(),
                viewer.lbl_compare_current_context_source.text(),
            ]
        )
        for raw_token in ("current_context_ref", "selected_run_contract", "--current-context"):
            assert raw_token not in visible_status

        viewer._current_time_window = lambda: (0.0, 0.1)
        exports = viewer._export_workspace_snapshot_set(tmp_path / "snapshots")
        contract_path = tmp_path / "snapshots" / "compare_contract.json"
        assert contract_path in exports
        payload = load_compare_contract(contract_path)
        assert payload["compare_contract_hash"] == viewer.compare_contract_hash
        assert payload["mismatch_banner"]["banner_id"] == "BANNER-HIST-002"
        assert payload["selected_table"] == str(viewer.current_table)
        assert payload["selected_signals"] == list(viewer._selected_signals())
        assert payload["selected_time_window"] == [0.0, 0.1]
        assert len(payload["run_refs"]) == 2
        assert payload["run_refs"][0]["baseline_ref"]["active_baseline_hash"] == "base-a"
        assert payload["run_refs"][0]["objective_ref"]["objective_contract_hash"] == "obj-a"
        assert payload["run_refs"][1]["objective_ref"]["objective_contract_hash"] == "obj-b"
        assert payload["baseline_ref"]["active_baseline_hash"] == "base-a"
        assert payload["objective_ref"]["objective_contract_hash"] == "obj-a"
    finally:
        viewer.close()
        app.processEvents()


def test_qt_compare_viewer_contract_dock_surfaces_current_context_sidecar(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(viewer_mod.QtCore, "QSettings", _MemorySettings)
    history = tmp_path / "history.npz"
    _write_npz(history, label="history", objective="obj-old")
    sidecar = tmp_path / "latest_compare_current_context.json"
    current_ref = _ref("current", objective="obj-current")
    sidecar.write_text(
        json.dumps(
            {
                "schema": "desktop_results_compare_current_context",
                "current_context_ref": current_ref,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    session = CompareSession(
        current_context_ref=viewer_mod._load_current_context_ref_safely(sidecar),
        current_context_path=viewer_mod._current_context_sidecar_path_safely(sidecar),
        session_source="current_context_sidecar",
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewer = viewer_mod.CompareViewer([history], session=session)
    try:
        viewer.show()
        app.processEvents()

        assert viewer.lbl_compare_current_context_source.objectName() == "compareCurrentContextSource"
        assert (
            viewer.btn_open_compare_current_context_sidecar.objectName()
            == "btnOpenCompareCurrentContextSidecar"
        )
        assert "Текущее сравнение: файл найден" in viewer.lbl_compare_current_context_source.text()
        assert "latest_compare_current_context.json" in viewer.lbl_compare_current_context_source.text()
        assert "ссылок:" in viewer.lbl_compare_current_context_source.text()
        assert "current_context_ref" not in viewer.lbl_compare_current_context_source.text()
        assert "Текущий контекст" not in viewer.lbl_compare_current_context_source.text()
        assert "sidecar" not in viewer.lbl_compare_current_context_source.text()
        assert viewer.btn_open_compare_current_context_sidecar.isEnabled()
        assert viewer._compare_current_context_path == str(sidecar.resolve())

        payload = viewer._current_compare_contract_payload()
        assert payload["current_context_ref"]["run_id"] == "current"
        assert payload["current_context_ref_source"] == "sidecar"
        assert payload["current_context_ref_source_path"] == str(sidecar.resolve())
        assert payload["mismatch_banner"]["banner_id"] == "BANNER-HIST-002"

        exports = viewer._export_workspace_snapshot_set(tmp_path / "current_context_snapshots")
        contract_path = tmp_path / "current_context_snapshots" / "compare_contract.json"
        assert contract_path in exports
        exported = load_compare_contract(contract_path)
        assert exported["current_context_ref"]["run_id"] == "current"
        assert exported["current_context_ref_source"] == "sidecar"
        assert exported["current_context_ref_source_path"] == str(sidecar.resolve())
        assert exported["current_context_ref_source_status"] == "ready"
        assert exported["mismatch_banner"]["banner_id"] == "BANNER-HIST-002"

        restored = viewer._current_compare_session()
        assert restored is not None
        assert restored.current_context_ref["run_id"] == "current"
        assert restored.current_context_path == str(sidecar.resolve())
        assert restored.current_context_ref_source_path == str(sidecar.resolve())
        assert restored.current_context_ref_source_status == "ready"
    finally:
        viewer.close()
        app.processEvents()


def test_qt_compare_viewer_contract_dock_marks_missing_current_context_sidecar(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(viewer_mod.QtCore, "QSettings", _MemorySettings)
    history = tmp_path / "history.npz"
    _write_npz(history, label="history", objective="obj-old")
    missing_sidecar = tmp_path / "latest_compare_current_context.json"
    session = CompareSession(
        current_context_ref=_ref("current", objective="obj-current"),
        current_context_ref_source_path=str(missing_sidecar.resolve()),
        current_context_ref_source_status="missing",
        session_source="current_context_sidecar",
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewer = viewer_mod.CompareViewer([history], session=session)
    try:
        viewer.show()
        app.processEvents()

        assert "Текущее сравнение: файл не найден" in viewer.lbl_compare_current_context_source.text()
        assert "latest_compare_current_context.json" in viewer.lbl_compare_current_context_source.text()
        assert "current_context_ref" not in viewer.lbl_compare_current_context_source.text()
        assert "Текущий контекст" not in viewer.lbl_compare_current_context_source.text()
        assert "sidecar" not in viewer.lbl_compare_current_context_source.text()
        assert not viewer.btn_open_compare_current_context_sidecar.isEnabled()
        assert viewer.btn_open_compare_current_context_sidecar.toolTip() == "Сведения текущего сравнения недоступны."

        payload = viewer._current_compare_contract_payload()
        assert payload["current_context_ref"]["run_id"] == "current"
        assert payload["current_context_ref_source"] == "sidecar"
        assert payload["current_context_ref_source_status"] == "missing"
        assert payload["current_context_ref_source_path"] == str(missing_sidecar.resolve())
        assert payload["mismatch_banner"]["banner_id"] == "BANNER-HIST-002"

        restored = viewer._current_compare_session()
        assert restored is not None
        assert restored.current_context_ref["run_id"] == "current"
        assert restored.current_context_path == str(missing_sidecar.resolve())
        assert restored.current_context_ref_source_path == str(missing_sidecar.resolve())
        assert restored.current_context_ref_source_status == "missing"
    finally:
        viewer.close()
        app.processEvents()


def test_qt_compare_viewer_contract_dock_keeps_session_only_current_context_refs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(viewer_mod.QtCore, "QSettings", _MemorySettings)
    history = tmp_path / "history.npz"
    _write_npz(history, label="history", objective="obj-old")
    session = CompareSession(
        current_context_ref=_ref("current", objective="obj-current"),
        current_context_ref_source_status="session",
        session_source="compare_session",
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewer = viewer_mod.CompareViewer([history], session=session)
    try:
        viewer.show()
        app.processEvents()

        assert "Текущее сравнение: сведения из сохранённого сравнения" in viewer.lbl_compare_current_context_source.text()
        assert "current_context_ref" not in viewer.lbl_compare_current_context_source.text()
        assert "Текущий контекст" not in viewer.lbl_compare_current_context_source.text()
        assert "refs" not in viewer.lbl_compare_current_context_source.text()
        assert not viewer.btn_open_compare_current_context_sidecar.isEnabled()

        payload = viewer._current_compare_contract_payload()
        assert payload["current_context_ref"]["run_id"] == "current"
        assert payload["current_context_ref_source"] == "session"
        assert payload["current_context_ref_source_status"] == "session"
        assert "current_context_ref_source_path" not in payload
        assert payload["mismatch_banner"]["banner_id"] == "BANNER-HIST-002"

        restored = viewer._current_compare_session()
        assert restored is not None
        assert restored.current_context_ref["run_id"] == "current"
        assert restored.current_context_path == ""
        assert restored.current_context_ref_source_path == ""
        assert restored.current_context_ref_source_status == "session"
    finally:
        viewer.close()
        app.processEvents()


def test_qt_compare_viewer_missing_session_npz_keeps_contract_and_uses_missing_banner(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(viewer_mod.QtCore, "QSettings", _MemorySettings)
    missing = tmp_path / "missing_history.npz"
    contract = build_compare_contract(
        [_ref("history")],
        selected_table="main",
        selected_metrics=["pressure"],
        selected_time_window=[0.0, 0.1],
    )
    sess = CompareSession(
        npz_paths=[str(missing)],
        labels=["history"],
        table="main",
        signals=["pressure"],
        reference_label="history",
        time_window=(0.0, 0.1),
        compare_contract=contract,
        compare_contract_hash=contract["compare_contract_hash"],
        run_refs=list(contract["run_refs"]),
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewer = viewer_mod.CompareViewer([missing], session=sess)
    try:
        viewer.show()
        app.processEvents()

        assert viewer.runs == []
        assert viewer.compare_contract_hash == contract["compare_contract_hash"]
        assert viewer.compare_contract["run_refs"] == contract["run_refs"]
        assert viewer.compare_contract["mismatch_banner"]["banner_id"] == "BANNER-HIST-003"
        assert viewer.lbl_compare_mismatch.isVisible()
        assert "Автоматическая подмена" in viewer.lbl_compare_mismatch.text()

        restored = viewer._current_compare_session()
        assert restored is not None
        assert restored.npz_paths == [str(missing)]
        assert restored.compare_contract_hash == contract["compare_contract_hash"]
        assert restored.run_refs == contract["run_refs"]
    finally:
        viewer.close()
        app.processEvents()
