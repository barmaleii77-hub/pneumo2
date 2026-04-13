from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DesktopResultsArtifact:
    key: str
    title: str
    category: str
    path: Path
    detail: str = ""


@dataclass(frozen=True)
class DesktopResultsOverviewRow:
    key: str
    title: str
    status: str
    detail: str
    next_action: str = ""
    evidence_path: Path | None = None
    action_key: str = ""
    artifact_key: str = ""


@dataclass(frozen=True)
class DesktopResultsSessionHandoff:
    summary: str = ""
    detail: str = ""
    step_lines: tuple[str, ...] = ()
    zip_path: Path | None = None
    autotest_run_dir: Path | None = None
    diagnostics_run_dir: Path | None = None


@dataclass(frozen=True)
class DesktopResultsSnapshot:
    latest_zip_path: Path | None
    latest_validation_json_path: Path | None
    latest_validation_md_path: Path | None
    latest_triage_json_path: Path | None
    latest_triage_md_path: Path | None
    latest_dashboard_html_path: Path | None
    latest_anim_diag_json_path: Path | None
    latest_npz_path: Path | None
    latest_pointer_json_path: Path | None
    latest_mnemo_event_log_path: Path | None
    latest_autotest_run_dir: Path | None
    latest_diagnostics_run_dir: Path | None
    validation_ok: bool | None
    validation_error_count: int
    validation_warning_count: int
    triage_critical_count: int
    triage_warn_count: int
    triage_info_count: int
    validation_errors: tuple[str, ...]
    validation_warnings: tuple[str, ...]
    triage_red_flags: tuple[str, ...]
    optimizer_scope_gate: str
    optimizer_scope_gate_reason: str
    optimizer_scope_release_risk: bool | None
    anim_summary_lines: tuple[str, ...]
    operator_recommendations: tuple[str, ...]
    mnemo_current_mode: str
    mnemo_recent_titles: tuple[str, ...]
    suggested_next_step: str
    suggested_next_detail: str
    validation_overview_rows: tuple[DesktopResultsOverviewRow, ...]
    recent_artifacts: tuple[DesktopResultsArtifact, ...]
    suggested_next_action_key: str = ""
    suggested_next_artifact_key: str = ""


def format_validation_summary(snapshot: DesktopResultsSnapshot) -> str:
    if snapshot.validation_ok is None:
        return "Validation: latest send bundle validation not found yet."
    status = "PASS" if snapshot.validation_ok else "FAIL"
    return (
        f"Validation: {status} | "
        f"errors={int(snapshot.validation_error_count)} | "
        f"warnings={int(snapshot.validation_warning_count)}"
    )


def format_optimizer_gate_summary(snapshot: DesktopResultsSnapshot) -> str:
    gate = str(snapshot.optimizer_scope_gate or "").strip() or "n/a"
    risk = snapshot.optimizer_scope_release_risk
    if risk is None:
        return f"Optimizer gate: {gate}"
    return f"Optimizer gate: {gate} | release_risk={bool(risk)}"


def format_triage_summary(snapshot: DesktopResultsSnapshot) -> str:
    return (
        "Triage: "
        f"critical={int(snapshot.triage_critical_count)} | "
        f"warn={int(snapshot.triage_warn_count)} | "
        f"info={int(snapshot.triage_info_count)} | "
        f"red_flags={len(snapshot.triage_red_flags)}"
    )


def format_npz_summary(snapshot: DesktopResultsSnapshot) -> str:
    if snapshot.latest_npz_path is None:
        return "Latest NPZ: not available yet."
    return f"Latest NPZ: {snapshot.latest_npz_path.name}"


def format_recent_runs_summary(snapshot: DesktopResultsSnapshot) -> str:
    autotest = snapshot.latest_autotest_run_dir.name if snapshot.latest_autotest_run_dir else "—"
    diagnostics = snapshot.latest_diagnostics_run_dir.name if snapshot.latest_diagnostics_run_dir else "—"
    return f"Recent runs: autotest={autotest} | diagnostics={diagnostics}"


__all__ = [
    "DesktopResultsArtifact",
    "DesktopResultsOverviewRow",
    "DesktopResultsSessionHandoff",
    "DesktopResultsSnapshot",
    "format_npz_summary",
    "format_optimizer_gate_summary",
    "format_recent_runs_summary",
    "format_triage_summary",
    "format_validation_summary",
]
