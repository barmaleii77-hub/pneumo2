from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.anim_export_meta import extract_anim_sidecar_meta
from pneumo_solver_ui.desktop_animator.analysis_context import (
    ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
    build_analysis_context_meta_refs,
    format_analysis_context_banner,
    load_analysis_context,
)
from pneumo_solver_ui.desktop_animator.cylinder_truth_gate import (
    ALLOWED_GRAPHICS_TRUTH_STATES,
    evaluate_all_cylinder_truth_gates,
)
from pneumo_solver_ui.desktop_animator.cylinder_render_policy import (
    evaluate_cylinder_render_policy,
)
from pneumo_solver_ui.desktop_animator.operator_text import format_startup_degraded_status
from pneumo_solver_ui.desktop_animator.truth_contract import (
    CAPTURE_EXPORT_HANDOFF_ID,
    build_animator_truth_summary,
    build_capture_export_manifest,
    build_frame_budget_evidence,
    file_sha256,
    stable_contract_hash,
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


def _complete_gate_without_render_geometry_meta() -> dict:
    return {
        "packaging": {
            "status": "complete",
            "cylinders": {
                "cyl1": {
                    "contract_complete": True,
                    "length_status_by_corner": {
                        "ЛП": "already_finite",
                        "ПП": "already_finite",
                        "ЛЗ": "already_finite",
                        "ПЗ": "already_finite",
                    },
                    "resolved_geometry": {
                        "bore_diameter_m": 0.032,
                        "rod_diameter_m": 0.016,
                        "outer_diameter_m": 0.038,
                        "body_length_front_m": 0.293,
                    },
                    "advanced_fields_missing": [],
                    "mount_families": {"top": "cyl1_top", "bottom": "cyl1_bot"},
                }
            },
        }
    }


def _complete_render_geometry_meta() -> dict:
    meta = _complete_gate_without_render_geometry_meta()
    meta["packaging"]["cylinders"]["cyl1"]["resolved_geometry_by_axle"] = {
        "front": {
            "bore_diameter_m": 0.032,
            "rod_diameter_m": 0.016,
            "outer_diameter_m": 0.038,
            "stroke_m": 0.25,
            "dead_cap_length_m": 0.018,
            "dead_rod_length_m": 0.024,
            "dead_height_m": 0.018,
            "body_length_m": 0.293,
        }
    }
    return meta


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_analysis_context_payload(
    context_path: Path,
    artifact_path: Path,
    *,
    artifact_sha: str = "",
) -> dict:
    pointer = {
        "path": str(artifact_path),
        "exists": True,
        "kind": artifact_path.suffix.lower().lstrip(".") or artifact_path.name,
        "sha256": artifact_sha or file_sha256(artifact_path),
        "size_bytes": int(artifact_path.stat().st_size),
    }
    link = {
        "schema": "analysis_to_animator_link_contract.v1",
        "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
        "producer_workspace": "WS-ANALYSIS",
        "consumer_workspace": "WS-ANIMATOR",
        "created_at_utc": "2026-04-17T00:00:00Z",
        "analysis_context_path": str(context_path),
        "run_id": "run-animation-001",
        "run_contract_hash": "selected-run-contract-hash-001",
        "selected_test_id": "T01",
        "selected_segment_id": "segment-1",
        "selected_time_window": {"mode": "time_s", "start_s": 0.0, "end_s": 1.0},
        "selected_best_candidate_ref": "candidate-001",
        "selected_result_artifact_pointer": pointer,
        "objective_contract_hash": "objective-hash-001",
        "suite_snapshot_hash": "suite-hash-001",
        "problem_hash": "problem-hash-001",
        "hard_gate_key": "max_pressure_pa",
        "hard_gate_tolerance": 250000.0,
        "active_baseline_hash": "baseline-hash-001",
        "ready_state": "ready",
        "blocking_states": (),
        "warnings": (),
        "rules": ("WS-ANIMATOR receives only explicit artifact pointers, not live runtime-state.",),
    }
    link["animator_link_contract_hash"] = stable_contract_hash(
        {key: value for key, value in link.items() if key != "animator_link_contract_hash"}
    )
    context = {
        "schema": "analysis_context.v1",
        "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
        "producer_workspace": "WS-ANALYSIS",
        "consumer_workspace": "WS-ANIMATOR",
        "created_at_utc": "2026-04-17T00:00:00Z",
        "analysis_context_path": str(context_path),
        "selected_run_contract_path": str(context_path.parent.parent / "WS-OPTIMIZATION" / "selected_run_contract.json"),
        "selected_run_contract_hash": "selected-run-contract-hash-001",
        "selected_run_context": {
            "run_id": "run-animation-001",
            "mode": "distributed_coordinator",
            "status": "done",
            "run_dir": str(context_path.parent),
            "objective_contract_hash": "objective-hash-001",
            "hard_gate_key": "max_pressure_pa",
            "hard_gate_tolerance": 250000.0,
            "active_baseline_hash": "baseline-hash-001",
            "suite_snapshot_hash": "suite-hash-001",
            "problem_hash": "problem-hash-001",
            "run_contract_hash": "selected-run-contract-hash-001",
        },
        "selected_result_artifact_pointer": pointer,
        "animator_link_contract_path": str(context_path.with_name("animator_link_contract.json")),
        "animator_link_contract_hash": link["animator_link_contract_hash"],
        "animator_link_contract": link,
        "diagnostics_bundle_finalized": False,
    }
    context["analysis_context_hash"] = stable_contract_hash(
        {key: value for key, value in context.items() if key != "analysis_context_hash"}
    )
    return context


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


def test_cylinder_render_policy_keeps_partial_packaging_axis_only_with_solver_pair() -> None:
    meta = _partial_truth_meta()
    gate = evaluate_all_cylinder_truth_gates(meta)["cyl1"]

    policy = evaluate_cylinder_render_policy(
        meta=meta,
        cyl_name="cyl1",
        axle="front",
        top_xyz=(0.0, 0.0, 0.0),
        bottom_xyz=(0.0, 0.3, 0.0),
        truth_gate=gate,
    )

    assert policy["axis_visible"] is True
    assert policy["body_enabled"] is False
    assert policy["body_mode"] == "axis_only"
    assert "body" in policy["hidden_elements"]
    assert "rod" in policy["hidden_elements"]
    assert "piston" in policy["hidden_elements"]


def test_cylinder_render_policy_requires_explicit_render_geometry_even_when_truth_gate_complete() -> None:
    meta = _complete_gate_without_render_geometry_meta()
    gate = evaluate_all_cylinder_truth_gates(meta)["cyl1"]

    policy = evaluate_cylinder_render_policy(
        meta=meta,
        cyl_name="cyl1",
        axle="front",
        top_xyz=(0.0, 0.0, 0.0),
        bottom_xyz=(0.0, 0.3, 0.0),
        truth_gate=gate,
    )

    assert gate["enabled"] is True
    assert policy["axis_visible"] is True
    assert policy["body_enabled"] is False
    assert policy["reason"] == "missing_explicit_render_geometry"
    assert set(policy["missing_render_geometry_fields"]) >= {
        "stroke_m",
        "dead_cap_length_m",
        "dead_rod_length_m",
        "dead_height_m",
        "body_length_m",
    }


def test_cylinder_render_policy_enables_exact_explicit_packaging_geometry() -> None:
    meta = _complete_render_geometry_meta()
    gate = evaluate_all_cylinder_truth_gates(meta)["cyl1"]

    policy = evaluate_cylinder_render_policy(
        meta=meta,
        cyl_name="cyl1",
        axle="front",
        top_xyz=(0.0, 0.0, 0.0),
        bottom_xyz=(0.0, 0.3, 0.0),
        truth_gate=gate,
    )

    assert policy["axis_visible"] is True
    assert policy["body_enabled"] is True
    assert policy["body_mode"] == "body_rod_piston"
    assert policy["hidden_elements"] == []
    assert policy["render_geometry"] == meta["packaging"]["cylinders"]["cyl1"]["resolved_geometry_by_axle"]["front"]


def test_cylinder_render_policy_hides_axis_and_body_for_degenerate_solver_pair() -> None:
    meta = _complete_render_geometry_meta()
    gate = evaluate_all_cylinder_truth_gates(meta)["cyl1"]

    policy = evaluate_cylinder_render_policy(
        meta=meta,
        cyl_name="cyl1",
        axle="front",
        top_xyz=(1.0, 2.0, 3.0),
        bottom_xyz=(1.0, 2.0, 3.0),
        truth_gate=gate,
    )

    assert policy["axis_visible"] is False
    assert policy["axis_reason"] == "degenerate_explicit_solver_point_pair"
    assert policy["body_enabled"] is False
    assert policy["body_mode"] == "unavailable"


def test_desktop_animator_source_has_no_viewer_derived_cylinder_body_length_path() -> None:
    app_src = (Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(
        encoding="utf-8"
    )

    assert "_derive_body_len" not in app_src
    assert "cyl1_dead_height = float(cyl1_dead_cap)" not in app_src
    assert "cyl2_dead_height = float(cyl2_dead_cap)" not in app_src
    assert "_evaluate_cylinder_render_policy" in app_src
    assert 'lines.append(f"TRUTH BADGE:' not in app_src
    assert 'lines.append(f"VALIDATION LIMIT:' not in app_src
    assert '"DEGRADED: truth absent/partial' not in app_src
    assert '"No fake geometry:' not in app_src
    assert 'status_msg = f"Loaded:' not in app_src
    assert 'self._status(f"Loading:' not in app_src


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
    assert manifest["artifact_refs"]["capture_export_manifest"] == "capture_export_manifest.json"
    assert manifest["analysis_artifact_refs"]["analysis_report_path"] == "analysis/report.json"
    assert manifest["optimizer_artifact_refs"]["optimizer_run_dir"] == "runs/opt/demo"
    assert "truth_warning_required" in manifest["blocking_states"]


def test_capture_export_manifest_uses_explicit_ho008_analysis_context_refs(tmp_path: Path) -> None:
    npz_path = tmp_path / "anim_latest.npz"
    pointer_path = tmp_path / "anim_latest.json"
    npz_path.write_bytes(b"npz-demo")
    pointer_path.write_text('{"npz_path":"anim_latest.npz"}', encoding="utf-8")
    context_path = tmp_path / "workspace" / "handoffs" / "WS-ANALYSIS" / "analysis_context.json"
    _write_json(context_path, _build_analysis_context_payload(context_path.resolve(), npz_path.resolve()))
    snapshot = load_analysis_context(context_path)
    meta_refs = build_analysis_context_meta_refs(snapshot)

    meta = _partial_truth_meta()
    meta["analysis_context_hash"] = "stale-meta-hash"
    truth = build_animator_truth_summary(meta, updated_utc="2026-04-17T00:00:00+00:00")
    manifest = build_capture_export_manifest(
        meta=meta,
        updated_utc="2026-04-17T00:00:00+00:00",
        npz_path=npz_path,
        pointer_path=pointer_path,
        artifact_refs=meta["anim_export_contract_artifacts"],
        analysis_context_refs=meta_refs,
        truth_summary=truth,
    )

    assert manifest["analysis_context_hash"] == snapshot.analysis_context_hash
    assert manifest["analysis_context_status"] == "READY"
    assert manifest["animator_link_contract_hash"] == snapshot.animator_link_contract_hash
    assert manifest["selected_run_contract_hash"] == snapshot.selected_run_contract_hash
    assert manifest["analysis_context_refs"]["selected_npz_path"] == str(npz_path.resolve())
    assert manifest["analysis_context_refs"]["animator_link_contract_path"].endswith("animator_link_contract.json")
    assert manifest["analysis_artifact_refs"]["analysis_context_path"] == str(context_path.resolve())
    assert manifest["analysis_artifact_refs"]["selected_test_id"] == "T01"
    assert manifest["optimizer_artifact_refs"]["run_id"] == "run-animation-001"
    assert manifest["optimizer_artifact_refs"]["objective_contract_hash"] == "objective-hash-001"
    assert "analysis_context_blocked" not in manifest["blocking_states"]


def test_capture_export_manifest_marks_missing_ho008_without_empty_synthetic_hash(tmp_path: Path) -> None:
    npz_path = tmp_path / "anim_latest.npz"
    pointer_path = tmp_path / "anim_latest.json"
    npz_path.write_bytes(b"npz-demo")
    pointer_path.write_text('{"npz_path":"anim_latest.npz"}', encoding="utf-8")

    meta = _partial_truth_meta()
    meta.pop("analysis_context_hash", None)
    meta.pop("analysis_report_path", None)
    truth = build_animator_truth_summary(meta, updated_utc="2026-04-17T00:00:00+00:00")
    manifest = build_capture_export_manifest(
        meta=meta,
        updated_utc="2026-04-17T00:00:00+00:00",
        npz_path=npz_path,
        pointer_path=pointer_path,
        artifact_refs=meta["anim_export_contract_artifacts"],
        truth_summary=truth,
    )

    assert manifest["analysis_context_hash"] == ""
    assert manifest["analysis_context_hash"] != stable_contract_hash({})
    assert manifest["analysis_context_status"] == "MISSING"
    assert manifest["analysis_context_refs"] == {}
    assert manifest["analysis_artifact_refs"] == {}
    assert "analysis_context_missing" in manifest["blocking_states"]


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


def test_frame_budget_evidence_missing_cadence_is_warn_not_release_closure() -> None:
    evidence = build_frame_budget_evidence(
        panels={"dock_hud": {"count": 2, "hz": 18.0, "visible": True}},
        visible_aux=1,
        total_aux_docks=3,
        playing=True,
        many_visible_budget=True,
        frame_budget_active=True,
        window_s=1.0,
        updated_utc="2026-04-17T00:00:00+00:00",
    )

    assert evidence["frame_cadence"]["cadence_measured"] is False
    assert evidence["frame_cadence"]["cadence_budget_ok"] is None
    assert evidence["release_gate"]["level"] == "WARN"
    assert evidence["release_gate"]["status"] == "missing_frame_cadence"
    assert evidence["release_gate"]["hard_fail"] is False


def test_frame_budget_evidence_missing_panel_samples_is_unavailable_warn_not_release_closure() -> None:
    evidence = build_frame_budget_evidence(
        panels={},
        visible_aux=0,
        total_aux_docks=3,
        playing=True,
        many_visible_budget=True,
        frame_budget_active=True,
        window_s=1.0,
        frame_cadence={"target_interval_ms": 16, "measured_present_hz": 59.5},
        updated_utc="2026-04-17T00:00:00+00:00",
    )

    assert evidence["evidence_state"] == "unavailable"
    assert evidence["release_gate"]["level"] == "WARN"
    assert evidence["release_gate"]["status"] == "missing_panel_samples"
    assert evidence["release_gate"]["hard_fail"] is False


def test_anim_sidecar_meta_preserves_analysis_and_optimizer_artifact_refs() -> None:
    meta = extract_anim_sidecar_meta(
        {
            "test": {
                "type": "ring",
                "analysis_context_hash": "analysis_hash_123",
                "analysis_context_status": "READY",
                "animator_link_contract_hash": "animator_link_hash_123",
                "selected_run_contract_hash": "selected_run_hash_123",
                "analysis_report_path": "analysis/report.json",
                "optimizer_run_dir": "runs/opt/demo",
                "run_id": "run-meta-001",
                "objective_contract_hash": "objective_hash_456",
                "suite_snapshot_hash": "suite_hash_789",
                "selected_test_id": "T01",
            }
        }
    )

    assert meta["analysis_context_hash"] == "analysis_hash_123"
    assert meta["analysis_context_status"] == "READY"
    assert meta["animator_link_contract_hash"] == "animator_link_hash_123"
    assert meta["selected_run_contract_hash"] == "selected_run_hash_123"
    assert meta["analysis_report_path"] == "analysis/report.json"
    assert meta["optimizer_run_dir"] == "runs/opt/demo"
    assert meta["run_id"] == "run-meta-001"
    assert meta["objective_contract_hash"] == "objective_hash_456"
    assert meta["suite_snapshot_hash"] == "suite_hash_789"
    assert meta["selected_test_id"] == "T01"


def test_animator_loads_ho008_analysis_context_as_frozen_source(tmp_path: Path) -> None:
    npz_path = tmp_path / "anim_latest.npz"
    npz_path.write_bytes(b"npz-demo")
    context_path = tmp_path / "workspace" / "handoffs" / "WS-ANALYSIS" / "analysis_context.json"
    _write_json(context_path, _build_analysis_context_payload(context_path.resolve(), npz_path.resolve()))

    snapshot = load_analysis_context(context_path)

    assert snapshot.status == "READY"
    assert snapshot.ready_for_animator is True
    assert snapshot.selected_npz_path == npz_path.resolve()
    assert snapshot.lineage["run_id"] == "run-animation-001"
    assert snapshot.lineage["objective_contract_hash"] == "objective-hash-001"
    assert snapshot.lineage["suite_snapshot_hash"] == "suite-hash-001"
    assert snapshot.lineage["problem_hash"] == "problem-hash-001"
    assert snapshot.animator_link_contract_hash
    assert snapshot.analysis_context_hash == snapshot.computed_analysis_context_hash
    assert snapshot.blocking_states == ()

    meta_refs = build_analysis_context_meta_refs(snapshot)
    assert meta_refs["analysis_context_path"] == str(context_path.resolve())
    assert meta_refs["analysis_context_hash"] == snapshot.analysis_context_hash
    assert meta_refs["animator_link_contract_path"].endswith("animator_link_contract.json")
    assert meta_refs["selected_npz_path"] == str(npz_path.resolve())
    assert meta_refs["selected_test_id"] == "T01"
    banner = format_analysis_context_banner(snapshot)
    assert banner.startswith("Связь с анализом: готова")
    assert "прогон run-animation-001" in banner
    assert "цель objective-" in banner
    assert "набор suite-has" in banner
    assert "задача problem-ha" in banner
    assert "run=" not in banner
    assert "context=" not in banner
    assert "HO-008" not in banner
    assert "Контекст анализа" not in banner


def test_animator_analysis_context_resolves_json_pointer_to_npz(tmp_path: Path) -> None:
    npz_path = tmp_path / "anim_latest.npz"
    npz_path.write_bytes(b"npz-demo")
    pointer_path = tmp_path / "anim_latest.json"
    _write_json(pointer_path, {"npz_path": "anim_latest.npz"})
    context_path = tmp_path / "workspace" / "handoffs" / "WS-ANALYSIS" / "analysis_context.json"
    _write_json(context_path, _build_analysis_context_payload(context_path.resolve(), pointer_path.resolve()))

    snapshot = load_analysis_context(context_path)

    assert snapshot.status == "READY"
    assert snapshot.selected_result_artifact_path == pointer_path.resolve()
    assert snapshot.selected_npz_path == npz_path.resolve()


def test_animator_analysis_context_blocks_pointer_hash_mismatch(tmp_path: Path) -> None:
    npz_path = tmp_path / "anim_latest.npz"
    npz_path.write_bytes(b"npz-demo")
    context_path = tmp_path / "workspace" / "handoffs" / "WS-ANALYSIS" / "analysis_context.json"
    _write_json(
        context_path,
        _build_analysis_context_payload(
            context_path.resolve(),
            npz_path.resolve(),
            artifact_sha="0" * 64,
        ),
    )

    snapshot = load_analysis_context(context_path)

    assert snapshot.status == "BLOCKED"
    assert snapshot.ready_for_animator is False
    assert "selected result artifact pointer sha256 mismatch" in snapshot.blocking_states
    assert snapshot.selected_npz_path == npz_path.resolve()
    banner = format_analysis_context_banner(snapshot)
    assert "Связь с анализом: заблокирована" in banner
    assert "метка результатов расчёта не совпадает" in banner
    assert "HO-008" not in banner
    assert "Контекст анализа" not in banner


def test_animator_missing_ho008_context_has_russian_degraded_operator_status(tmp_path: Path) -> None:
    context_path = tmp_path / "workspace" / "handoffs" / "WS-ANALYSIS" / "analysis_context.json"

    snapshot = load_analysis_context(context_path)
    banner = format_analysis_context_banner(snapshot)
    status = format_startup_degraded_status(f"HO-008 {snapshot.status}", detail="; ".join(snapshot.blocking_states))

    assert snapshot.status == "MISSING"
    assert snapshot.ready_for_animator is False
    assert "Связь с анализом: отсутствует" in banner
    assert "Недоступно:" in status
    assert "связь с анализом отсутствует" in status
    assert "HO-008" not in banner
    assert "HO-008" not in status
    assert "контекст анализа" not in status
    assert "DEGRADED" not in status
