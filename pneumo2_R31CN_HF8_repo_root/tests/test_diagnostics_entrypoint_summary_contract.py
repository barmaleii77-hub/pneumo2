from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.diagnostics_entrypoint import (
    build_full_diagnostics_bundle,
    read_last_meta_from_out_dir,
    summarize_last_bundle_meta,
)
from pneumo_solver_ui.diagnostics_unified import build_unified_diagnostics


def _write_send_bundle_sidecars(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "latest_anim_pointer_diagnostics.json").write_text(
        json.dumps(
            {
                "anim_latest_available": True,
                "anim_latest_pointer_json": "/abs/workspace/exports/anim_latest.json",
                "anim_latest_npz_path": "/abs/workspace/exports/anim_latest.npz",
                "anim_latest_visual_cache_token": "tok-diag",
                "anim_latest_visual_reload_inputs": ["npz", "road_csv"],
                "anim_latest_meta": {
                    "scenario_kind": "ring",
                    "ring_closure_policy": "strict_exact",
                    "ring_closure_applied": False,
                    "ring_seam_open": True,
                    "ring_seam_max_jump_m": 0.012,
                    "ring_raw_seam_max_jump_m": 0.015,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "latest_send_bundle_validation.json").write_text(
        json.dumps(
            {
                "anim_latest": {
                    "available": True,
                    "visual_cache_token": "tok-diag",
                    "browser_perf_evidence_status": "trace_bundle_ready",
                    "browser_perf_evidence_level": "PASS",
                    "browser_perf_bundle_ready": True,
                    "browser_perf_comparison_status": "regression_checked",
                    "browser_perf_comparison_level": "PASS",
                    "browser_perf_comparison_ready": True,
                    "browser_perf_evidence_report_in_bundle": True,
                    "browser_perf_comparison_report_in_bundle": True,
                    "browser_perf_trace_in_bundle": True,
                    "scenario_kind": "ring",
                    "ring_closure_policy": "strict_exact",
                    "ring_closure_applied": False,
                    "ring_seam_open": True,
                    "ring_seam_max_jump_m": 0.012,
                    "ring_raw_seam_max_jump_m": 0.015,
                },
                "optimizer_scope": {
                    "problem_hash": "ph_diag_full_1234567890",
                    "problem_hash_short": "ph_diag_12",
                    "problem_hash_mode": "stable",
                    "canonical_source": "triage",
                    "scope_sync_ok": False,
                    "mismatch_fields": ["problem_hash", "problem_hash_mode"],
                },
                "optimizer_scope_gate": {
                    "release_gate": "FAIL",
                    "release_gate_reason": "problem_hash mismatch between sources",
                    "release_risk": True,
                    "canonical_source": "triage",
                    "scope_sync_ok": False,
                    "mismatch_fields": ["problem_hash", "problem_hash_mode"],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_full_diagnostics_bundle_returns_shared_summary_lines(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    out_dir = repo_root / "send_bundles"
    zip_path = out_dir / "latest_send_bundle.zip"

    def _fake_make_send_bundle(*, repo_root: Path, out_dir: Path, **_kwargs):
        _write_send_bundle_sidecars(out_dir)
        zip_path.write_bytes(b"zip")
        return zip_path

    monkeypatch.setattr("pneumo_solver_ui.send_bundle.make_send_bundle", _fake_make_send_bundle)

    res = build_full_diagnostics_bundle(trigger="manual", repo_root=repo_root, open_folder=False)

    assert res.ok is True
    assert res.zip_path == zip_path.resolve()
    assert res.meta["anim_latest_summary"]["visual_cache_token"] == "tok-diag"
    assert res.meta["anim_latest_summary"]["ring_closure_policy"] == "strict_exact"
    assert res.meta["anim_latest_summary"]["ring_seam_open"] is True
    assert res.meta["anim_latest_summary"]["optimizer_scope_release_gate"] == "FAIL"
    assert any("Browser perf evidence: trace_bundle_ready / PASS / bundle_ready=True" == line for line in res.meta["summary_lines"])
    assert any("Optimizer scope gate: FAIL / release_risk=True / reason=problem_hash mismatch between sources" == line for line in res.meta["summary_lines"])
    assert any("Optimizer scope: scope=ph_diag_12 / mode=stable / source=triage / sync=False / mismatches=problem_hash, problem_hash_mode" == line for line in res.meta["summary_lines"])
    assert any("Ring seam: closure=strict_exact / open=True / seam_max_m=0.012 / raw_seam_max_m=0.015" == line for line in res.meta["summary_lines"])
    assert str(out_dir / "latest_anim_pointer_diagnostics.json") == res.meta["anim_pointer_diagnostics_path"]

    last_meta = summarize_last_bundle_meta(read_last_meta_from_out_dir(out_dir))
    assert last_meta["zip_name"] == "latest_send_bundle.zip"
    assert last_meta["anim_latest_summary"]["ring_closure_policy"] == "strict_exact"
    assert last_meta["ring_seam_open"] is True
    assert last_meta["anim_latest_summary"]["optimizer_scope_release_gate"] == "FAIL"
    assert any("Browser perf evidence: trace_bundle_ready / PASS / bundle_ready=True" == line for line in last_meta["summary_lines"])
    assert any("Optimizer scope gate: FAIL / release_risk=True / reason=problem_hash mismatch between sources" == line for line in last_meta["summary_lines"])
    assert any("Ring seam: closure=strict_exact / open=True / seam_max_m=0.012 / raw_seam_max_m=0.015" == line for line in last_meta["summary_lines"])
    assert last_meta["anim_pointer_diagnostics_path"].endswith("latest_anim_pointer_diagnostics.json")


def test_build_unified_diagnostics_returns_shared_summary_lines(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    out_dir = repo_root / "send_bundles"
    zip_path = out_dir / "latest_send_bundle.zip"

    def _fake_make_send_bundle(*, repo_root: Path, out_dir: Path, **_kwargs):
        _write_send_bundle_sidecars(out_dir)
        zip_path.write_bytes(b"zip")
        return zip_path

    monkeypatch.setattr("pneumo_solver_ui.tools.make_send_bundle.make_send_bundle", _fake_make_send_bundle)

    res = build_unified_diagnostics(repo_root=repo_root, open_folder=False)

    assert res.ok is True
    assert res.zip_path == zip_path
    assert res.details["anim_latest_summary"]["visual_cache_token"] == "tok-diag"
    assert res.details["anim_latest_summary"]["ring_closure_policy"] == "strict_exact"
    assert res.details["anim_latest_summary"]["ring_seam_open"] is True
    assert res.details["anim_latest_summary"]["optimizer_scope_release_gate"] == "FAIL"
    assert any("Browser perf comparison: regression_checked / PASS / ready=True" == line for line in res.details["summary_lines"])
    assert any("Optimizer scope gate: FAIL / release_risk=True / reason=problem_hash mismatch between sources" == line for line in res.details["summary_lines"])
    assert any("Ring seam: closure=strict_exact / open=True / seam_max_m=0.012 / raw_seam_max_m=0.015" == line for line in res.details["summary_lines"])
    assert str(out_dir / "latest_anim_pointer_diagnostics.json") == res.details["anim_pointer_diagnostics_path"]


def test_summarize_last_bundle_meta_rebuilds_summary_lines_from_anim_latest_summary() -> None:
    meta = summarize_last_bundle_meta(
        {
            "ok": True,
            "ts": "2026-04-10 12:00:00",
            "trigger": "manual",
            "zip": {"name": "latest_send_bundle.zip", "path": "/tmp/latest_send_bundle.zip", "size_bytes": 1024},
            "anim_latest_summary": {
                "available": True,
                "scenario_kind": "ring",
                "ring_closure_policy": "strict_exact",
                "ring_closure_applied": False,
                "ring_seam_open": True,
                "ring_seam_max_jump_m": 0.012,
                "ring_raw_seam_max_jump_m": 0.015,
                "browser_perf_evidence_status": "trace_bundle_ready",
                "browser_perf_evidence_level": "PASS",
                "browser_perf_bundle_ready": True,
                "optimizer_scope_release_gate": "FAIL",
                "optimizer_scope_release_risk": True,
                "optimizer_scope_release_gate_reason": "problem_hash mismatch between sources",
                "optimizer_scope_problem_hash_short": "ph_diag_12",
                "optimizer_scope_problem_hash_mode": "stable",
                "optimizer_scope_canonical_source": "triage",
                "optimizer_scope_sync_ok": False,
                "optimizer_scope_mismatch_fields": ["problem_hash", "problem_hash_mode"],
            },
            "anim_pointer_diagnostics_path": "/tmp/latest_anim_pointer_diagnostics.json",
        }
    )

    assert meta["anim_latest_summary"]["ring_closure_policy"] == "strict_exact"
    assert meta["ring_seam_open"] is True
    assert any("Browser perf evidence: trace_bundle_ready / PASS / bundle_ready=True" == line for line in meta["summary_lines"])
    assert any("Optimizer scope gate: FAIL / release_risk=True / reason=problem_hash mismatch between sources" == line for line in meta["summary_lines"])
    assert any("Ring seam: closure=strict_exact / open=True / seam_max_m=0.012 / raw_seam_max_m=0.015" == line for line in meta["summary_lines"])
