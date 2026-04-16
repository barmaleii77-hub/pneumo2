from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.anim_export_meta import extract_anim_sidecar_meta
from pneumo_solver_ui.desktop_animator.cylinder_truth_gate import (
    ALLOWED_GRAPHICS_TRUTH_STATES,
    evaluate_all_cylinder_truth_gates,
)
from pneumo_solver_ui.desktop_animator.truth_contract import (
    CAPTURE_EXPORT_HANDOFF_ID,
    build_animator_truth_summary,
    build_capture_export_manifest,
    build_frame_budget_evidence,
)


def _partial_truth_meta() -> dict:
    return {
        "solver_points": {"visible_suspension_skeleton_families": ["cyl1_top", "cyl1_bot"]},
        "hardpoints": {"families": {"cyl1_top": {}, "cyl1_bot": {}}},
        "packaging": {
            "status": "partial",
            "cylinders": {
                "cyl1": {
                    "contract_complete": False,
                    "length_status_by_corner": {
                        "FL": "filled_from_endpoint_distance",
                        "FR": "filled_from_endpoint_distance",
                    },
                    "resolved_geometry": {
                        "bore_diameter_m": 0.032,
                        "rod_diameter_m": 0.016,
                        "outer_diameter_m": 0.038,
                        "body_length_front_m": 0.293,
                    },
                    "advanced_fields_missing": ["rod_eye_length_m"],
                    "mount_families": {"top": "cyl1_top", "bottom": "cyl1_bot"},
                }
            },
        },
        "anim_export_validation": {"validation_level": "WARN"},
        "anim_export_contract_artifacts": {
            "sidecar": "anim_latest.contract.sidecar.json",
            "validation_json": "anim_latest.contract.validation.json",
            "capture_export_manifest": "capture_export_manifest.json",
        },
        "analysis_context_hash": "analysis_hash_123",
        "analysis_report_path": "analysis/report.json",
        "optimizer_run_dir": "runs/opt/demo",
    }


def test_truth_summary_uses_allowed_badges_and_keeps_partial_cylinders_axis_only() -> None:
    meta = _partial_truth_meta()
    gates = evaluate_all_cylinder_truth_gates(meta)
    summary = build_animator_truth_summary(meta, cylinder_gates=gates, updated_utc="2026-04-17T00:00:00+00:00")

    assert gates["cyl1"]["enabled"] is False
    assert gates["cyl1"]["mode"] == "axis_only"
    assert gates["cyl1"]["truth_state"] == "approximate_inferred_with_warning"
    assert summary["overall_truth_state"] == "approximate_inferred_with_warning"
    assert {badge["truth_state"] for badge in summary["truth_badges"]} <= set(ALLOWED_GRAPHICS_TRUTH_STATES)
    assert any("do not fabricate geometry" in warning for warning in summary["warnings"])
    assert summary["truth_mode_hash"]


def test_capture_export_manifest_handoff_contains_hashes_refs_and_blocking_truth_warning(tmp_path: Path) -> None:
    npz_path = tmp_path / "anim_latest.npz"
    pointer_path = tmp_path / "anim_latest.json"
    npz_path.write_bytes(b"npz-demo")
    pointer_path.write_text('{"npz_path":"anim_latest.npz"}', encoding="utf-8")

    meta = _partial_truth_meta()
    truth = build_animator_truth_summary(meta, updated_utc="2026-04-17T00:00:00+00:00")
    manifest = build_capture_export_manifest(
        meta=meta,
        updated_utc="2026-04-17T00:00:00+00:00",
        npz_path=npz_path,
        pointer_path=pointer_path,
        artifact_refs=meta["anim_export_contract_artifacts"],
        truth_summary=truth,
    )

    assert manifest["schema"] == "capture_export_manifest.v1"
    assert manifest["handoff_id"] == CAPTURE_EXPORT_HANDOFF_ID
    assert manifest["from_workspace"] == "WS-ANIMATOR"
    assert manifest["to_workspace"] == "WS-DIAGNOSTICS"
    assert manifest["capture_hash"]
    assert manifest["analysis_context_hash"] == "analysis_hash_123"
    assert manifest["truth_mode_hash"] == truth["truth_mode_hash"]
    assert manifest["analysis_artifact_refs"]["analysis_report_path"] == "analysis/report.json"
    assert manifest["optimizer_artifact_refs"]["optimizer_run_dir"] == "runs/opt/demo"
    assert "truth_warning_required" in manifest["blocking_states"]


def test_frame_budget_evidence_records_hidden_dock_gating_and_provenance() -> None:
    evidence = build_frame_budget_evidence(
        panels={
            "dock_hud": {"count": 5, "hz": 24.0, "visible": True},
            "dock_telemetry": {"count": 0, "hz": 0.0, "visible": False},
        },
        visible_aux=1,
        total_aux_docks=4,
        playing=True,
        many_visible_budget=True,
        frame_budget_active=True,
        window_s=1.5,
        source_dt_s=1.0 / 120.0,
        frame_cadence={"target_interval_ms": 16, "measured_present_hz": 59.5, "present_dt_ema_ms": 16.8},
        updated_utc="2026-04-17T00:00:00+00:00",
        provenance={"producer": "pytest", "hidden_dock_gate": "_dock_is_exposed"},
    )

    assert evidence["schema"] == "animator_frame_budget_evidence.v1"
    assert evidence["handoff_id"] == CAPTURE_EXPORT_HANDOFF_ID
    assert evidence["evidence_state"] == "measured"
    assert evidence["frame_budget"]["frame_budget_active"] is True
    assert evidence["frame_budget"]["source_dt_s"] == 1.0 / 120.0
    assert evidence["frame_cadence"]["cadence_measured"] is True
    assert evidence["frame_cadence"]["cadence_budget_ok"] is True
    assert evidence["release_gate"]["status"] == "frame_budget_measured"
    assert evidence["hidden_dock_gating"]["visible_aux"] == 1
    assert evidence["hidden_dock_gating"]["hidden_aux_docks"] == 3
    assert evidence["hidden_dock_gating"]["gated"] is True
    assert evidence["provenance"]["hidden_dock_gate"] == "_dock_is_exposed"
    assert evidence["evidence_hash"]


def test_anim_sidecar_meta_preserves_analysis_and_optimizer_artifact_refs() -> None:
    meta = extract_anim_sidecar_meta(
        {
            "test": {
                "type": "ring",
                "analysis_context_hash": "analysis_hash_123",
                "analysis_report_path": "analysis/report.json",
                "optimizer_run_dir": "runs/opt/demo",
                "objective_contract_hash": "objective_hash_456",
            }
        }
    )

    assert meta["analysis_context_hash"] == "analysis_hash_123"
    assert meta["analysis_report_path"] == "analysis/report.json"
    assert meta["optimizer_run_dir"] == "runs/opt/demo"
    assert meta["objective_contract_hash"] == "objective_hash_456"
