from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def test_engineering_analysis_center_uses_ttk_panedwindow_actions_status_and_log() -> None:
    src = _read("pneumo_solver_ui/tools/desktop_engineering_analysis_center.py")

    assert "class DesktopEngineeringAnalysisCenter" in src
    assert "DesktopEngineeringAnalysisRuntime" in src
    assert 'workspace = ttk.Panedwindow(self, orient="horizontal")' in src
    for label in (
        "Обновить",
        "Открыть артефакт",
        "Экспорт HO-007",
        "Экспорт evidence",
        "Открыть evidence",
        "System Influence",
        "Full Report",
        "Influence Staging",
        "Собрать диагностику",
    ):
        assert label in src
    assert "threading.Thread" in src
    assert "ttk.Progressbar" in src
    assert "status_var" in src
    assert "log_text" in src
    assert "def _run_system_influence" in src
    assert "def _run_full_report" in src
    assert "def _run_param_staging" in src
    assert "def _export_selected_run_contract_bridge" in src
    assert "discover_selected_run_candidates" in src
    assert "_candidate_by_iid" in src
    assert "Optimization runs for HO-007" in src
    assert "candidate_ready_only_var" in src
    assert "ttk.Checkbutton" in src
    assert "READY only" in src
    assert "def _refresh_candidate_filter" in src
    assert "shown=" in src
    assert "def _selected_candidate_run_dir" in src
    assert "bridge_status" in src
    assert 'label == "Export HO-007" and result.ok' in src
    assert "def _auto_export_evidence_after_ho007" in src
    assert "write_diagnostics_evidence_manifest" in src
    assert "evidence auto-exported after HO-007" in src
    assert "def _open_evidence_manifest" in src
    assert "Evidence manifest opened" in src
    assert "run Экспорт evidence first" in src
    assert "compare_influence_surface_count" in src
    assert "def _compare_surface_details" in src
    assert "def _compare_surface_preview_for_artifact" in src
    assert "compare_influence_surface_preview" in src
    assert "compare_influence_surface_for_artifact" in src
    assert "validated_artifacts_summary" in src
    assert '"validated_artifacts"' in src
    assert "Validated artifacts" in src
    assert "missing_required_artifacts" in src
    assert "missing_required_artifact" in src
    assert "Required artifacts ready" in src
    assert "filedialog.askdirectory" in src


def test_engineering_analysis_shell_discovery_is_wired_to_module_and_aliases() -> None:
    spec_registry = _read("pneumo_solver_ui/desktop_spec_shell/registry.py")
    legacy_registry = _read("pneumo_solver_ui/desktop_shell/registry.py")
    legacy_contracts = _read("pneumo_solver_ui/desktop_shell/contracts.py")
    adapter = _read("pneumo_solver_ui/desktop_shell/adapters/desktop_engineering_analysis_center_adapter.py")

    assert "analysis.engineering.open" in spec_registry
    assert "pneumo_solver_ui.tools.desktop_engineering_analysis_center" in spec_registry
    assert "analysis.influence_and_exploration" in spec_registry
    for alias in (
        "engineering analysis",
        "calibration",
        "influence",
        "sensitivity",
        "system influence",
        "калибровка",
        "влияние",
        "чувствительность",
    ):
        assert alias in spec_registry
        assert alias in legacy_contracts

    assert "build_desktop_engineering_analysis_center_spec" in legacy_registry
    assert "desktop_engineering_analysis_center" in adapter
    assert "DesktopEngineeringAnalysisRuntime" in adapter


def test_engineering_analysis_send_bundle_sources_reference_expected_artifacts() -> None:
    make_bundle = _read("pneumo_solver_ui/tools/make_send_bundle.py")
    evidence = _read("pneumo_solver_ui/tools/send_bundle_evidence.py")
    validate = _read("pneumo_solver_ui/tools/validate_send_bundle.py")
    inspect = _read("pneumo_solver_ui/tools/inspect_send_bundle.py")

    assert "ENGINEERING_ANALYSIS_EVIDENCE_ARCNAME" in make_bundle
    assert "ENGINEERING_ANALYSIS_EVIDENCE_SIDECAR_NAME" in make_bundle
    assert "BND-021" in evidence
    assert "if engineering analysis used" in evidence
    assert "release_blocking_if_missing\": False" in evidence
    assert "engineering_analysis_evidence" in validate
    assert "has_engineering_analysis_evidence" in inspect
