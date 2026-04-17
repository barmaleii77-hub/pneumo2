from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.browser_perf_artifacts import (
    VIEWPORT_GATING_REPORT_JSON_NAME,
    write_browser_perf_artifacts,
    write_browser_perf_trace_artifact,
)
from pneumo_solver_ui.desktop_animator.truth_contract import (
    ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME,
    build_frame_budget_evidence,
)
from pneumo_solver_ui.release_gate import _runtime_evidence_step
from pneumo_solver_ui.runtime_evidence import (
    WINDOWS_RUNTIME_PROOF_JSON_NAME,
    collect_windows_runtime_proof,
    build_windows_path_budget,
    build_windows_runtime_proof,
    validate_runtime_evidence_dir,
    write_collected_windows_runtime_proof,
    write_windows_runtime_proof,
)


def _hidden_gated_snapshot() -> dict:
    return {
        "updated_utc": "2026-04-17T00:00:00Z",
        "dataset_id": "runtime-evidence",
        "components": {
            "playhead_ctrl": {"viewport_state": "visible", "wakeups": 3, "render_count": 3},
            "details_pane": {
                "viewport_state": "offscreen",
                "wakeups": 0,
                "render_count": 0,
                "schedule_raf_count": 0,
                "schedule_timeout_count": 0,
            },
        },
    }


def _hidden_active_snapshot() -> dict:
    snap = _hidden_gated_snapshot()
    snap["components"]["details_pane"].update({"wakeups": 2, "render_count": 1})
    return snap


def _passing_windows_checks() -> dict[str, bool]:
    return {
        "native_titlebar_system_menu": True,
        "snap_half_third_quarter": True,
        "docking_undocking_floating": True,
        "second_monitor_workflow": True,
        "mixed_dpi_or_pmv2": True,
        "keyboard_f6_focus": True,
        "resize_affordances": True,
        "portable_path_budget": True,
        "send_bundle_latest_pointer": True,
    }


def test_runtime_evidence_validator_passes_full_measured_artifact_set(tmp_path: Path) -> None:
    write_browser_perf_trace_artifact(
        tmp_path,
        {"traceEvents": [{"name": "present", "ts": 100}]},
        trace_session_id="full-pass",
    )
    write_browser_perf_artifacts(tmp_path, _hidden_gated_snapshot(), updated_utc="2026-04-17T00:00:01Z")
    frame_budget = build_frame_budget_evidence(
        panels={
            "dock_hud": {"count": 4, "hz": 60.0, "visible": True},
            "dock_plot": {"count": 0, "hz": 0.0, "visible": False},
        },
        visible_aux=1,
        total_aux_docks=2,
        playing=True,
        many_visible_budget=False,
        frame_budget_active=False,
        window_s=1.0,
        source_dt_s=1.0 / 60.0,
        frame_cadence={"target_interval_ms": 16, "measured_present_hz": 59.7, "present_dt_ema_ms": 16.75},
        updated_utc="2026-04-17T00:00:02Z",
        provenance={"producer": "pytest"},
    )
    (tmp_path / ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME).write_text(
        json.dumps(frame_budget, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    proof = build_windows_runtime_proof(
        checks=_passing_windows_checks(),
        layout_profiles=["normal", "maximized", "snap-left"],
        monitors=[{"name": "primary", "dpi": 1.0}, {"name": "secondary", "dpi": 1.5}],
        dpi={"awareness": "per-monitor-v2"},
        path_budget=build_windows_path_budget(tmp_path),
        artifacts={"send_bundle_latest_pointer": "diagnostics/latest_send_bundle.zip"},
        updated_utc="2026-04-17T00:00:03Z",
    )
    write_windows_runtime_proof(tmp_path, proof)

    report = validate_runtime_evidence_dir(
        tmp_path,
        require_browser_trace=True,
        require_viewport_gating=True,
        require_animator_frame_budget=True,
        require_windows_runtime=True,
    )
    assert report["ok"] is True
    assert report["hard_fail_count"] == 0
    assert (tmp_path / VIEWPORT_GATING_REPORT_JSON_NAME).exists()
    assert (tmp_path / WINDOWS_RUNTIME_PROOF_JSON_NAME).exists()


def test_runtime_evidence_validator_hard_fails_missing_required_artifacts(tmp_path: Path) -> None:
    report = validate_runtime_evidence_dir(
        tmp_path,
        require_browser_trace=True,
        require_viewport_gating=True,
        require_animator_frame_budget=True,
        require_windows_runtime=True,
    )

    assert report["ok"] is False
    assert report["hard_fail_count"] == 4
    assert {row["name"] for row in report["hard_fails"]} == {
        "browser_perf_trace",
        "viewport_gating",
        "animator_frame_budget",
        "windows_runtime_proof",
    }


def test_release_gate_runtime_evidence_step_fails_missing_browser_trace(tmp_path: Path) -> None:
    result = _runtime_evidence_step(
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        evidence_dir=tmp_path / "exports",
        require_browser_trace=True,
        require_viewport_gating=False,
        require_animator_frame_budget=False,
        require_windows_runtime=False,
    )
    payload = json.loads(Path(result.log_path or "").read_text(encoding="utf-8"))

    assert result.ok is False
    assert payload["hard_fails"][0]["name"] == "browser_perf_trace"


def test_release_gate_runtime_evidence_step_fails_hidden_viewport_activity(tmp_path: Path) -> None:
    exports = tmp_path / "exports"
    write_browser_perf_artifacts(exports, _hidden_active_snapshot(), updated_utc="2026-04-17T00:00:05Z")
    result = _runtime_evidence_step(
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        evidence_dir=exports,
        require_browser_trace=False,
        require_viewport_gating=True,
        require_animator_frame_budget=False,
        require_windows_runtime=False,
    )
    payload = json.loads(Path(result.log_path or "").read_text(encoding="utf-8"))

    assert result.ok is False
    assert payload["hard_fails"][0]["name"] == "viewport_gating"


def test_animator_frame_budget_degraded_cadence_is_release_gate_fail(tmp_path: Path) -> None:
    frame_budget = build_frame_budget_evidence(
        panels={"dock_hud": {"count": 4, "hz": 10.0, "visible": True}},
        visible_aux=1,
        total_aux_docks=1,
        playing=True,
        many_visible_budget=False,
        frame_budget_active=False,
        window_s=1.0,
        source_dt_s=1.0 / 60.0,
        frame_cadence={"target_interval_ms": 16, "measured_present_hz": 10.0, "present_dt_ema_ms": 100.0},
        updated_utc="2026-04-17T00:00:06Z",
        provenance={"producer": "pytest"},
    )
    (tmp_path / ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME).write_text(
        json.dumps(frame_budget, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report = validate_runtime_evidence_dir(tmp_path, require_animator_frame_budget=True)

    assert frame_budget["frame_cadence"]["cadence_budget_ok"] is False
    assert frame_budget["release_gate"]["status"] == "frame_budget_failed"
    assert report["ok"] is False
    assert report["hard_fails"][0]["name"] == "animator_frame_budget"


def test_animator_frame_budget_missing_cadence_is_release_gate_fail(tmp_path: Path) -> None:
    frame_budget = build_frame_budget_evidence(
        panels={"dock_hud": {"count": 4, "hz": 60.0, "visible": True}},
        visible_aux=1,
        total_aux_docks=1,
        playing=True,
        many_visible_budget=False,
        frame_budget_active=False,
        window_s=1.0,
        source_dt_s=1.0 / 60.0,
        updated_utc="2026-04-17T00:00:07Z",
        provenance={"producer": "pytest"},
    )
    (tmp_path / ANIMATOR_FRAME_BUDGET_EVIDENCE_JSON_NAME).write_text(
        json.dumps(frame_budget, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result = _runtime_evidence_step(
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        evidence_dir=tmp_path,
        require_browser_trace=False,
        require_viewport_gating=False,
        require_animator_frame_budget=True,
        require_windows_runtime=False,
    )

    assert result.ok is False


def test_release_gate_runtime_evidence_step_fails_failed_windows_proof(tmp_path: Path) -> None:
    checks = _passing_windows_checks()
    checks["mixed_dpi_or_pmv2"] = False
    write_windows_runtime_proof(
        tmp_path,
        build_windows_runtime_proof(
            checks=checks,
            path_budget={"status": "PASS", "max_full_path_chars": 120},
            updated_utc="2026-04-17T00:00:08Z",
        ),
    )
    result = _runtime_evidence_step(
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        evidence_dir=tmp_path,
        require_browser_trace=False,
        require_viewport_gating=False,
        require_animator_frame_budget=False,
        require_windows_runtime=True,
    )
    payload = json.loads(Path(result.log_path or "").read_text(encoding="utf-8"))

    assert result.ok is False
    assert payload["hard_fails"][0]["name"] == "windows_runtime_proof"


def test_windows_runtime_proof_records_required_failures(tmp_path: Path) -> None:
    checks = _passing_windows_checks()
    checks["second_monitor_workflow"] = False
    proof = build_windows_runtime_proof(
        checks=checks,
        path_budget={"status": "PASS", "max_full_path_chars": 120},
        updated_utc="2026-04-17T00:00:04Z",
    )
    out = write_windows_runtime_proof(tmp_path, proof)
    payload = json.loads((tmp_path / WINDOWS_RUNTIME_PROOF_JSON_NAME).read_text(encoding="utf-8"))

    assert out["hard_fail"] is True
    assert payload["release_gate"] == "FAIL"
    assert "second_monitor_workflow" in payload["failed_checks"]


def test_windows_runtime_collector_sets_path_budget_and_latest_pointer(tmp_path: Path) -> None:
    latest = tmp_path / "latest_send_bundle.zip"
    latest.write_bytes(b"zip")
    checks = _passing_windows_checks()
    checks.pop("portable_path_budget")
    checks.pop("send_bundle_latest_pointer")

    proof = collect_windows_runtime_proof(
        checks=checks,
        path_budget_root=tmp_path,
        latest_send_bundle_path=latest,
        layout_profiles=["normal", "snap-left"],
        monitors=[{"name": "primary", "dpi": 1.0}],
        dpi={"awareness": "per-monitor-v2"},
        updated_utc="2026-04-17T00:00:09Z",
    )
    out = write_collected_windows_runtime_proof(
        tmp_path / "exports",
        checks=checks,
        path_budget_root=tmp_path,
        latest_send_bundle_path=latest,
        updated_utc="2026-04-17T00:00:10Z",
    )

    assert proof["release_gate"] == "PASS"
    assert proof["checks"]["portable_path_budget"] is True
    assert proof["checks"]["send_bundle_latest_pointer"] is True
    assert out["exists"] is True


def test_release_gate_runtime_evidence_step_is_a_hard_fail_on_missing_viewport(tmp_path: Path) -> None:
    result = _runtime_evidence_step(
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        evidence_dir=tmp_path / "exports",
        require_browser_trace=False,
        require_viewport_gating=True,
        require_animator_frame_budget=False,
        require_windows_runtime=False,
    )
    payload = json.loads(Path(result.log_path or "").read_text(encoding="utf-8"))

    assert result.ok is False
    assert result.rc == 1
    assert payload["hard_fail_count"] == 1
    assert payload["hard_fails"][0]["name"] == "viewport_gating"


def test_release_gate_runtime_evidence_step_passes_full_required_set(tmp_path: Path) -> None:
    test_runtime_evidence_validator_passes_full_measured_artifact_set(tmp_path)
    result = _runtime_evidence_step(
        project_root=tmp_path,
        logs_dir=tmp_path / "logs",
        evidence_dir=tmp_path,
        require_browser_trace=True,
        require_viewport_gating=True,
        require_animator_frame_budget=True,
        require_windows_runtime=True,
    )

    assert result.ok is True
