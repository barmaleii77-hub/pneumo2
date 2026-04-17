from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from pneumo_solver_ui import run_artifacts
from pneumo_solver_ui.desktop_optimizer_model import (
    DESKTOP_OPTIMIZER_PROFILE_OPTIONS,
    FINISHED_JOB_SORT_OPTIONS,
    PACKAGING_SORT_OPTIONS,
    STAGE_NAMES,
    apply_launch_profile,
    build_contract_snapshot,
    build_optimizer_session_defaults,
    build_stage_policy_blueprint_rows,
    launch_profile_description,
    launch_profile_label,
)
from pneumo_solver_ui.optimization_active_runtime_summary import (
    active_handoff_provenance_caption,
    active_runtime_penalty_gate_caption,
    active_runtime_progress_caption,
    active_runtime_recent_errors_caption,
    active_runtime_trial_health_caption,
    build_active_runtime_summary,
    build_run_runtime_summary,
)
from pneumo_solver_ui.optimization_baseline_source import read_baseline_source_artifact
from pneumo_solver_ui.optimization_contract_summary_ui import (
    compare_objective_contract_to_current,
)
from pneumo_solver_ui.optimization_job_session_runtime import (
    DistOptJob,
    clear_job_from_session,
    load_job_from_session,
    parse_done_from_log,
    soft_stop_requested,
    tail_file_text,
    terminate_optimization_process,
    write_soft_stop_file,
)
from pneumo_solver_ui.optimization_job_start_runtime import (
    start_coordinator_handoff_job,
    start_optimization_job,
)
from pneumo_solver_ui.optimization_launch_plan_runtime import (
    build_optimization_launch_plan,
    problem_hash_mode_for_launch,
    workspace_dir_for_ui_root,
)
from pneumo_solver_ui.optimization_problem_scope_ui import (
    problem_scope_surface_payload,
)
from pneumo_solver_ui.optimization_run_history import (
    OptimizationRunPackagingSnapshot,
    OptimizationRunSummary,
    discover_workspace_optimization_runs,
    summarize_optimization_run,
    summarize_run_packaging_snapshot,
)
from pneumo_solver_ui.optimization_run_pointer_actions_ui import (
    build_run_pointer_meta_from_summary,
)
from pneumo_solver_ui.optimization_objective_contract import (
    normalize_penalty_tol,
    objective_contract_hash,
)
from pneumo_solver_ui.optimization_stage_policy_live import summarize_stage_policy_runtime
from pneumo_solver_ui.optimization_workspace_history_ui import (
    HANDOFF_SORT_OPTIONS,
    build_handoff_overview_rows,
    enrich_handoff_overview_rows,
    filter_handoff_overview_rows,
    sort_handoff_overview_rows,
)


_ACTIVE_LAUNCH_CONTEXT_KEY = "__opt_active_launch_context"
_HISTORY_SELECTED_RUN_DIR_KEY = "__opt_history_selected_run_dir"
SELECTED_RUN_CONTRACT_FILENAME = "selected_run_contract.json"
WS_OPTIMIZATION_HANDOFF_ID = "HO-007"
WS_OPTIMIZATION_SOURCE_WORKSPACE = "WS-OPTIMIZATION"
WS_OPTIMIZATION_ANALYSIS_TARGET_WORKSPACE = "WS-ANALYSIS"


@dataclass(frozen=True)
class DesktopOptimizerRunDetails:
    summary: OptimizationRunSummary
    packaging_snapshot: OptimizationRunPackagingSnapshot
    stage_policy_rows: tuple[dict[str, Any], ...]
    log_tail: str


def _resolved_path_text(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).resolve())
    except Exception:
        return text


def _run_id_text(run_dir: Path | str | None) -> str:
    if run_dir is None:
        return ""
    try:
        return (Path(run_dir) / "run_id.txt").read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def _int_value(raw: Any) -> int:
    try:
        return int(raw or 0)
    except Exception:
        try:
            return int(float(raw or 0.0))
        except Exception:
            return 0


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _file_sha256(path: Path | str | None) -> str:
    if path is None:
        return ""
    try:
        candidate = Path(path)
        if not candidate.exists() or not candidate.is_file():
            return ""
        digest = hashlib.sha256()
        with candidate.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except Exception:
        return ""


def _utc_now_label() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_from_timestamp(value: float | int | None) -> str:
    try:
        ts = float(value or 0.0)
    except Exception:
        return ""
    if ts <= 0.0:
        return ""
    return datetime.fromtimestamp(ts, UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _optimization_active_mode(summary: OptimizationRunSummary) -> str:
    return "stage_runner" if str(summary.pipeline_mode or "") == "staged" else "distributed_coordinator"


def _compatibility_text(selected: str, current: str) -> str:
    selected_text = str(selected or "").strip()
    current_text = str(current or "").strip()
    if not current_text and not selected_text:
        return ""
    if not current_text or not selected_text:
        return "unknown"
    return "match" if selected_text == current_text else "different"


class DesktopOptimizerRuntime:
    def __init__(
        self,
        *,
        ui_root: Path | None = None,
        python_executable: str | None = None,
        cpu_count: int | None = None,
        platform_name: str | None = None,
        session_state: dict[str, Any] | None = None,
    ) -> None:
        self.ui_root = Path(ui_root or Path(__file__).resolve().parent).resolve()
        self.python_executable = str(python_executable or sys.executable)
        self.ui_jobs_default = max(1, int(cpu_count or 4))
        self.session_state = dict(
            session_state
            or build_optimizer_session_defaults(
                cpu_count=cpu_count,
                platform_name=platform_name,
            )
        )
        self.workspace_dir = workspace_dir_for_ui_root(self.ui_root)

    def update_state(self, updates: Mapping[str, Any]) -> None:
        self.session_state.update(dict(updates or {}))

    def _with_workspace_dir_env(self, callback: Any, /, *args: Any, **kwargs: Any) -> Any:
        previous = os.environ.get("PNEUMO_WORKSPACE_DIR")
        os.environ["PNEUMO_WORKSPACE_DIR"] = str(self.workspace_dir)
        try:
            return callback(*args, **kwargs)
        finally:
            if previous is None:
                os.environ.pop("PNEUMO_WORKSPACE_DIR", None)
            else:
                os.environ["PNEUMO_WORKSPACE_DIR"] = previous

    def current_job(self) -> DistOptJob | None:
        return load_job_from_session(self.session_state)

    def active_launch_context(self) -> dict[str, Any]:
        raw = self.session_state.get(_ACTIVE_LAUNCH_CONTEXT_KEY)
        return dict(raw) if isinstance(raw, dict) else {}

    def bind_selected_run_dir(self, run_dir: Path | str | None) -> None:
        resolved = _resolved_path_text(run_dir)
        if not resolved:
            self.session_state.pop(_HISTORY_SELECTED_RUN_DIR_KEY, None)
            self.session_state["opt_dist_run_id"] = ""
            return
        self.session_state[_HISTORY_SELECTED_RUN_DIR_KEY] = resolved
        pipeline = Path(resolved).parent.name.lower()
        if pipeline == "coord":
            self.session_state["opt_dist_run_id"] = _run_id_text(resolved)
        else:
            self.session_state["opt_dist_run_id"] = ""

    def resume_target_summary(self) -> dict[str, Any]:
        selected_run_dir = _resolved_path_text(
            self.session_state.get(_HISTORY_SELECTED_RUN_DIR_KEY, "")
        )
        selected_pipeline = ""
        selected_run_name = ""
        selected_run_id = ""
        if selected_run_dir:
            path = Path(selected_run_dir)
            selected_pipeline = "staged" if path.parent.name.lower() == "staged" else "coordinator"
            selected_run_name = path.name
            selected_run_id = _run_id_text(path) if selected_pipeline == "coordinator" else ""
        use_staged = bool(self.session_state.get("opt_use_staged", True))
        return {
            "selected_run_dir": selected_run_dir,
            "selected_run_name": selected_run_name,
            "selected_pipeline": selected_pipeline,
            "selected_run_id": selected_run_id,
            "stage_resume_enabled": bool(self.session_state.get("opt_stage_resume", False)),
            "coord_resume_enabled": bool(self.session_state.get("opt_resume", False)),
            "coord_run_id": str(self.session_state.get("opt_dist_run_id", "") or "").strip(),
            "launch_pipeline": "staged" if use_staged else "coordinator",
        }

    def apply_run_contract(self, summary: OptimizationRunSummary) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        objective_keys = tuple(summary.objective_keys or ())
        if objective_keys:
            updates["opt_objectives"] = "\n".join(str(item) for item in objective_keys)
        penalty_key = str(summary.penalty_key or "").strip()
        if penalty_key:
            updates["opt_penalty_key"] = penalty_key
        if summary.penalty_tol is not None:
            updates["opt_penalty_tol"] = float(summary.penalty_tol)
        hash_mode = str(summary.problem_hash_mode or "").strip().lower()
        if hash_mode in {"stable", "legacy"}:
            updates["settings_opt_problem_hash_mode"] = hash_mode
        self.session_state.update(updates)
        return updates

    def selected_run_contract_path(self) -> Path:
        return (
            self.workspace_dir
            / "handoffs"
            / WS_OPTIMIZATION_SOURCE_WORKSPACE
            / SELECTED_RUN_CONTRACT_FILENAME
        ).resolve()

    def build_selected_run_contract(
        self,
        summary: OptimizationRunSummary,
        *,
        selected_from: str = "desktop_optimizer_center",
        now_text: str | None = None,
    ) -> dict[str, Any]:
        drift = self.contract_drift_summary(summary)
        scope_payload = dict(drift.get("scope_payload") or {})
        diff_bits = tuple(str(bit) for bit in (drift.get("diff_bits") or ()) if str(bit).strip())
        baseline_compatibility = str(drift.get("baseline_compatibility") or "")
        status = str(summary.status or "").strip().lower()

        blocking_states: list[str] = []
        warnings: list[str] = []
        if status in {"error", "unknown"}:
            blocking_states.append(f"run {status or 'unknown'}")
        elif status not in {"done", "partial", "stopped"}:
            blocking_states.append("run incomplete")
        elif status in {"partial", "stopped"}:
            warnings.append(f"run status is {status}")

        if summary.result_path is None:
            blocking_states.append("missing results artifact")
        if str(scope_payload.get("compatibility") or "") == "different" or str(
            scope_payload.get("mode_compatibility") or ""
        ) == "different":
            blocking_states.append("problem scope mismatch")
        if baseline_compatibility == "different":
            blocking_states.append("active baseline mismatch")
        if diff_bits:
            warnings.append("objective contract drift: " + ", ".join(diff_bits))

        baseline_source_payload = read_baseline_source_artifact(summary.run_dir)
        active_baseline_hash = str(getattr(summary, "active_baseline_hash", "") or "").strip()
        if not active_baseline_hash:
            active_baseline_hash = str(
                baseline_source_payload.get("active_baseline_hash") or ""
            ).strip()
        if not active_baseline_hash:
            active_baseline_hash = _file_sha256(summary.baseline_source_path)
        if not active_baseline_hash:
            warnings.append("active baseline hash missing")

        suite_snapshot_hash = str(getattr(summary, "suite_snapshot_hash", "") or "").strip()
        if not suite_snapshot_hash:
            suite_snapshot_hash = str(
                baseline_source_payload.get("suite_snapshot_hash") or ""
            ).strip()
        if not suite_snapshot_hash:
            warnings.append("suite snapshot hash missing")

        hard_gate_tolerance = normalize_penalty_tol(
            getattr(summary, "hard_gate_tolerance", None)
            if getattr(summary, "hard_gate_tolerance", None) is not None
            else summary.penalty_tol
        )
        hard_gate_key = str(getattr(summary, "hard_gate_key", "") or summary.penalty_key or "")
        objective_contract_hash_value = str(
            getattr(summary, "objective_contract_hash", "") or ""
        ).strip()
        if not objective_contract_hash_value:
            objective_contract_hash_value = objective_contract_hash(
                objective_keys=summary.objective_keys,
                penalty_key=hard_gate_key,
                penalty_tol=hard_gate_tolerance,
            )
        active_mode = _optimization_active_mode(summary)
        artifact_dir = (
            Path(summary.result_path).parent
            if summary.result_path is not None
            else Path(summary.run_dir)
        )
        objective_contract_path = (
            str(Path(summary.objective_contract_path).resolve())
            if summary.objective_contract_path is not None
            else ""
        )
        results_csv_path = (
            str(Path(summary.result_path).resolve())
            if summary.result_path is not None
            else ""
        )
        log_path = (
            str(Path(summary.log_path).resolve())
            if summary.log_path is not None
            else ""
        )
        handoff_plan_path = (
            str(Path(summary.handoff_plan_path).resolve())
            if summary.handoff_plan_path is not None
            else ""
        )
        ready_state = "blocked" if blocking_states else ("warning" if warnings else "ready")
        run_id = str(getattr(summary, "run_id", "") or _run_id_text(summary.run_dir) or summary.run_dir.name)

        payload: dict[str, Any] = {
            "schema_version": "selected_run_contract_v1",
            "handoff_id": WS_OPTIMIZATION_HANDOFF_ID,
            "source_workspace": WS_OPTIMIZATION_SOURCE_WORKSPACE,
            "target_workspace": WS_OPTIMIZATION_ANALYSIS_TARGET_WORKSPACE,
            "selected_from": str(selected_from or "desktop_optimizer_center"),
            "created_at_utc": str(now_text or _utc_now_label()),
            "run_id": run_id,
            "run_name": str(summary.run_dir.name),
            "run_dir": str(Path(summary.run_dir).resolve()),
            "mode": active_mode,
            "active_mode": active_mode,
            "pipeline_mode": str(summary.pipeline_mode or ""),
            "backend": str(summary.backend or ""),
            "status": str(summary.status or ""),
            "status_label": str(summary.status_label or ""),
            "started_at_utc": str(summary.started_at or ""),
            "finished_at_utc": _utc_from_timestamp(summary.updated_ts)
            if status in {"done", "partial", "stopped", "error"}
            else "",
            "objective_contract_hash": objective_contract_hash_value,
            "objective_contract_path": objective_contract_path,
            "objective_stack": list(summary.objective_keys or ()),
            "hard_gate_key": hard_gate_key,
            "hard_gate_tolerance": hard_gate_tolerance,
            "hard_gate_unit": "",
            "problem_hash": str(summary.problem_hash or ""),
            "problem_hash_mode": str(summary.problem_hash_mode or ""),
            "active_baseline_hash": active_baseline_hash,
            "active_baseline_ref": str(summary.baseline_source_path or ""),
            "active_baseline_label": str(
                summary.baseline_source_label or summary.baseline_source_kind or ""
            ),
            "suite_snapshot_hash": suite_snapshot_hash,
            "results_csv_path": results_csv_path,
            "best_candidate_ref": "",
            "selected_best_candidate_ref": "",
            "artifact_dir": str(Path(artifact_dir).resolve()),
            "results_artifact_index": {
                "results_csv_path": results_csv_path,
                "log_path": log_path,
                "objective_contract_path": objective_contract_path,
                "handoff_plan_path": handoff_plan_path,
                "run_dir": str(Path(summary.run_dir).resolve()),
            },
            "analysis_handoff_ready_state": ready_state,
            "animator_handoff_ready_state": "warning",
            "diagnostics_handoff_ready_state": "not_finalized_by_optimizer",
            "blocking_states": tuple(blocking_states),
            "warnings": tuple(warnings),
            "current_context_drift": dict(drift),
        }
        payload["selected_run_contract_hash"] = _sha256_payload(payload)
        return payload

    def export_selected_run_contract(
        self,
        summary: OptimizationRunSummary,
        *,
        selected_from: str = "desktop_optimizer_center",
        now_text: str | None = None,
    ) -> dict[str, Any]:
        payload = self.build_selected_run_contract(
            summary,
            selected_from=selected_from,
            now_text=now_text,
        )
        path = self.selected_run_contract_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return {**payload, "selected_run_contract_path": str(path)}

    def save_run_pointer(
        self,
        summary: OptimizationRunSummary,
        *,
        selected_from: str = "desktop_optimizer_center",
    ) -> dict[str, Any]:
        meta = build_run_pointer_meta_from_summary(
            summary,
            selected_from=selected_from,
        )
        meta["backend"] = str(summary.backend or meta.get("backend") or "")
        meta["run_dir"] = str(summary.run_dir)
        selected_contract = self.export_selected_run_contract(
            summary,
            selected_from=selected_from,
        )
        meta["handoff_id"] = WS_OPTIMIZATION_HANDOFF_ID
        meta["selected_run_contract_path"] = str(
            selected_contract.get("selected_run_contract_path") or self.selected_run_contract_path()
        )
        meta["selected_run_contract_hash"] = str(
            selected_contract.get("selected_run_contract_hash") or ""
        )
        meta["analysis_handoff_ready_state"] = str(
            selected_contract.get("analysis_handoff_ready_state") or ""
        )
        self._with_workspace_dir_env(
            run_artifacts.save_last_opt_ptr,
            Path(summary.run_dir),
            meta,
        )
        self._with_workspace_dir_env(run_artifacts.autoload_to_session, self.session_state)
        return self.latest_pointer_summary()

    def latest_pointer_summary(self) -> dict[str, Any]:
        payload = self._with_workspace_dir_env(run_artifacts.load_last_opt_ptr) or {}
        pointer_path = self._with_workspace_dir_env(run_artifacts.latest_optimization_ptr_path)
        run_dir = _resolved_path_text(payload.get("run_dir"))
        meta = dict(payload.get("meta") or {}) if isinstance(payload.get("meta"), dict) else {}
        details = self.selected_run_details(run_dir) if run_dir else None
        summary = getattr(details, "summary", None) if details is not None else None
        selected_run_dir = _resolved_path_text(
            self.session_state.get(_HISTORY_SELECTED_RUN_DIR_KEY, "")
        )
        selected_matches_pointer = bool(
            selected_run_dir and run_dir and selected_run_dir == run_dir
        )
        result_path = getattr(summary, "result_path", None) if summary is not None else None
        return {
            "pointer_path": str(pointer_path),
            "exists": bool(payload),
            "kind": str(payload.get("kind") or ""),
            "updated_at": str(payload.get("updated_at") or ""),
            "run_dir": run_dir,
            "run_name": Path(run_dir).name if run_dir else "",
            "run_dir_exists": bool(run_dir and Path(run_dir).exists()),
            "pointer_in_history": summary is not None,
            "selected_matches_pointer": selected_matches_pointer,
            "selected_from": str(meta.get("selected_from") or ""),
            "backend": str(meta.get("backend") or getattr(summary, "backend", "") or ""),
            "pipeline_mode": str(
                meta.get("pipeline_mode") or getattr(summary, "pipeline_mode", "") or ""
            ),
            "status": str(meta.get("status") or getattr(summary, "status", "") or ""),
            "status_label": str(getattr(summary, "status_label", "") or meta.get("status") or ""),
            "rows": int(meta.get("rows") or getattr(summary, "row_count", 0) or 0),
            "done_count": int(meta.get("done_count") or getattr(summary, "done_count", 0) or 0),
            "error_count": int(meta.get("error_count") or getattr(summary, "error_count", 0) or 0),
            "objective_keys": tuple(
                meta.get("objective_keys") or getattr(summary, "objective_keys", ()) or ()
            ),
            "penalty_key": str(meta.get("penalty_key") or getattr(summary, "penalty_key", "") or ""),
            "penalty_tol": meta.get("penalty_tol", getattr(summary, "penalty_tol", None)),
            "handoff_preset": str(
                meta.get("handoff_preset") or getattr(summary, "handoff_preset_tag", "") or ""
            ),
            "handoff_budget": int(
                meta.get("handoff_budget") or getattr(summary, "handoff_budget", 0) or 0
            ),
            "handoff_seed_count": int(
                meta.get("handoff_seed_count")
                or getattr(summary, "handoff_seed_count", 0)
                or 0
            ),
            "result_path": str(result_path) if result_path is not None else "",
        }

    def selected_run_next_step_summary(
        self,
        run_dir: Path | str | None = None,
    ) -> dict[str, Any]:
        resolved_run_dir = _resolved_path_text(
            run_dir if run_dir is not None else self.session_state.get(_HISTORY_SELECTED_RUN_DIR_KEY, "")
        )
        if not resolved_run_dir:
            return {
                "headline": "Selected run is not chosen yet.",
                "next_action": "History",
                "next_action_kind": "show_history_tab",
                "rows": (
                    {
                        "title": "Selection",
                        "status": "info",
                        "summary": "Choose a run in History, Finished Jobs, Handoff or Packaging first.",
                        "action": "History",
                    },
                ),
            }
        details = self.selected_run_details(resolved_run_dir)
        if details is None:
            return {
                "headline": "Selected run is no longer available in workspace history.",
                "next_action": "History",
                "next_action_kind": "show_history_tab",
                "rows": (
                    {
                        "title": "Selection",
                        "status": "warn",
                        "summary": "The selected run directory is missing or no longer discoverable.",
                        "action": "History",
                    },
                ),
            }

        summary = details.summary
        packaging = details.packaging_snapshot
        drift = self.contract_drift_summary(summary)
        latest_pointer = self.latest_pointer_summary()
        active_surface = self.active_job_surface()
        active_job = active_surface.get("job")
        pointer_matches = _resolved_path_text(latest_pointer.get("run_dir")) == resolved_run_dir
        live_now = _resolved_path_text(getattr(active_job, "run_dir", None)) == resolved_run_dir
        has_results = summary.result_path is not None
        interference_rows = int(packaging.spring_host_interference_rows or 0) + int(
            packaging.spring_pair_interference_rows or 0
        )
        truth_ready_rows = int(packaging.packaging_truth_ready_rows or 0)
        verification_rows = int(packaging.packaging_verification_pass_rows or 0)
        fallback_rows = int(packaging.runtime_fallback_rows or 0)
        rows_with_packaging = int(packaging.rows_with_packaging or 0)
        diff_bits = tuple(str(bit) for bit in (drift.get("diff_bits") or ()) if str(bit).strip())
        scope_payload = dict(drift.get("scope_payload") or {})
        baseline_compatibility = str(drift.get("baseline_compatibility") or "")

        rows: list[dict[str, Any]] = []
        rows.append(
            {
                "title": "Run materialization",
                "status": (
                    "ok"
                    if has_results
                    else ("warn" if str(summary.status or "").strip().lower() in {"done", "partial"} else "info")
                ),
                "summary": (
                    f"Results artifact is available: {summary.result_path}."
                    if has_results
                    else "Selected run has no results artifact yet; downstream review surfaces will stay partial."
                ),
                "action": "History",
                "action_kind": "show_history_tab",
            }
        )
        if str(scope_payload.get("compatibility") or "") == "different" or str(
            scope_payload.get("mode_compatibility") or ""
        ) == "different":
            compat_status = "warn"
            compat_summary = "Current launch contract uses another problem scope/hash mode than this selected run."
        elif baseline_compatibility == "different":
            compat_status = "warn"
            compat_summary = "Selected run points to another baseline source than the current launch contract."
        elif diff_bits:
            compat_status = "info"
            compat_summary = "Objective contract drift exists: " + ", ".join(diff_bits) + "."
        else:
            compat_status = "ok"
            compat_summary = "Selected run is aligned with the current launch contract."
        rows.append(
            {
                "title": "Launch compatibility",
                "status": compat_status,
                "summary": compat_summary,
                "action": "Contract",
                "action_kind": "show_contract_tab",
            }
        )
        if rows_with_packaging <= 0:
            packaging_status = "info"
            packaging_summary = "Packaging verdicts are not materialized for this run yet."
        elif truth_ready_rows > 0 and interference_rows == 0 and fallback_rows == 0:
            packaging_status = "ok"
            packaging_summary = (
                f"Packaging is truth-ready with zero interference across {truth_ready_rows} rows."
            )
        elif interference_rows > 0 or fallback_rows > 0:
            packaging_status = "warn"
            packaging_summary = (
                f"Packaging review is needed: interference={interference_rows}, fallback={fallback_rows}, "
                f"verification={verification_rows}."
            )
        elif verification_rows > 0:
            packaging_status = "info"
            packaging_summary = (
                f"Verification rows exist ({verification_rows}), but packaging is not truth-ready yet."
            )
        else:
            packaging_status = "info"
            packaging_summary = (
                f"Packaging evidence is partial: rows_with_packaging={rows_with_packaging}, truth_ready={truth_ready_rows}."
            )
        rows.append(
            {
                "title": "Packaging route",
                "status": packaging_status,
                "summary": packaging_summary,
                "action": "Packaging",
                "action_kind": "show_packaging_tab",
            }
        )
        if str(summary.pipeline_mode or "") == "staged":
            if bool(summary.handoff_available or summary.handoff_preset_tag):
                handoff_status = "ok"
                handoff_summary = (
                    "Staged run has a continuation plan: "
                    f"preset={summary.handoff_preset_tag or '—'}, budget={int(summary.handoff_budget or 0)}, "
                    f"seeds={int(summary.handoff_seed_count or 0)}."
                )
            else:
                handoff_status = "info"
                handoff_summary = "This staged run has not produced a coordinator handoff plan yet."
        else:
            handoff_status = "info"
            handoff_summary = "Coordinator run is already beyond the staged handoff step."
        rows.append(
            {
                "title": "Continuation route",
                "status": handoff_status,
                "summary": handoff_summary,
                "action": "Handoff",
                "action_kind": "show_handoff_tab",
            }
        )
        if pointer_matches:
            pointer_status = "ok"
            pointer_summary = "This selected run is already published as latest_optimization."
        elif has_results:
            pointer_status = "info"
            pointer_summary = "Selected run can be promoted to latest_optimization for downstream review surfaces."
        else:
            pointer_status = "info"
            pointer_summary = "Pointer promotion is possible, but downstream result surfaces will remain limited without results artifacts."
        rows.append(
            {
                "title": "Latest pointer",
                "status": pointer_status,
                "summary": pointer_summary,
                "action": "Make latest pointer",
                "action_kind": "make_latest_pointer",
            }
        )
        if live_now:
            runtime_status = "info"
            runtime_summary = "Selected run is live now; follow runtime progress before making downstream decisions."
        else:
            runtime_status = "ok"
            runtime_summary = "Selected run is not running right now."
        rows.append(
            {
                "title": "Runtime state",
                "status": runtime_status,
                "summary": runtime_summary,
                "action": "Runtime",
                "action_kind": "show_runtime_tab",
            }
        )

        next_action = "Runtime"
        next_action_kind = "show_runtime_tab"
        headline = "Selected run looks stable for review."
        if live_now:
            headline = "Selected run is active now."
            next_action = "Runtime"
            next_action_kind = "show_runtime_tab"
        elif compat_status == "warn":
            headline = "Selected run needs contract review before reuse."
            next_action = "Contract"
            next_action_kind = "show_contract_tab"
        elif packaging_status == "warn":
            headline = "Selected run needs packaging review before promotion."
            next_action = "Packaging"
            next_action_kind = "show_packaging_tab"
        elif str(summary.pipeline_mode or "") == "staged" and bool(summary.handoff_available or summary.handoff_preset_tag):
            headline = "Selected staged run is ready for coordinator continuation."
            next_action = "Handoff"
            next_action_kind = "show_handoff_tab"
        elif not pointer_matches and has_results:
            headline = "Selected run can be published as latest_optimization."
            next_action = "Make latest pointer"
            next_action_kind = "make_latest_pointer"
        elif not has_results:
            headline = "Selected run is still missing results artifacts."
            next_action = "History"
            next_action_kind = "show_history_tab"
        elif pointer_matches:
            headline = "Selected run is already published and aligned with downstream review."
            next_action = "Packaging"
            next_action_kind = "show_packaging_tab"
        return {
            "headline": headline,
            "next_action": next_action,
            "next_action_kind": next_action_kind,
            "rows": tuple(rows),
            "run_dir": resolved_run_dir,
        }

    def launch_profile_options(self) -> tuple[tuple[str, str, str], ...]:
        return tuple(DESKTOP_OPTIMIZER_PROFILE_OPTIONS)

    def apply_launch_profile(self, profile_key: str) -> dict[str, Any]:
        updated_state, changed_keys = apply_launch_profile(
            self.session_state,
            profile_key,
            cpu_count=self.ui_jobs_default,
        )
        updates = {
            key: updated_state[key]
            for key in changed_keys
            if key in updated_state
        }
        self.session_state.update(updates)
        return updates

    def launch_profile_summary(self) -> dict[str, Any]:
        profile_key = str(
            self.session_state.get("opt_launch_profile", "stage_triage") or "stage_triage"
        ).strip() or "stage_triage"
        _updated_state, drift_keys = apply_launch_profile(
            self.session_state,
            profile_key,
            cpu_count=self.ui_jobs_default,
        )
        launch_pipeline = "staged" if bool(self.session_state.get("opt_use_staged", True)) else "coordinator"
        backend = "StageRunner" if launch_pipeline == "staged" else str(
            self.session_state.get("opt_backend", "") or "Dask"
        )
        return {
            "profile_key": profile_key,
            "profile_label": launch_profile_label(profile_key),
            "description": launch_profile_description(profile_key),
            "launch_pipeline": launch_pipeline,
            "backend": backend,
            "stage_minutes": float(self.session_state.get("ui_opt_minutes", 0.0) or 0.0),
            "stage_jobs": int(self.session_state.get("ui_jobs", self.ui_jobs_default) or self.ui_jobs_default),
            "seed_candidates": int(self.session_state.get("ui_seed_candidates", 0) or 0),
            "seed_conditions": int(self.session_state.get("ui_seed_conditions", 0) or 0),
            "warmstart_mode": str(self.session_state.get("warmstart_mode", "") or ""),
            "adaptive_influence_eps": bool(self.session_state.get("adaptive_influence_eps", False)),
            "budget": int(self.session_state.get("opt_budget", 0) or 0),
            "max_inflight": int(self.session_state.get("opt_max_inflight", 0) or 0),
            "q": int(self.session_state.get("opt_q", 0) or 0),
            "export_every": int(self.session_state.get("opt_export_every", 0) or 0),
            "dask_mode": str(self.session_state.get("dask_mode", "") or ""),
            "dask_workers": int(self.session_state.get("dask_workers", 0) or 0),
            "dask_threads_per_worker": int(
                self.session_state.get("dask_threads_per_worker", 0) or 0
            ),
            "ray_mode": str(self.session_state.get("ray_mode", "") or ""),
            "ray_num_evaluators": int(self.session_state.get("ray_num_evaluators", 0) or 0),
            "ray_num_proposers": int(self.session_state.get("ray_num_proposers", 0) or 0),
            "resume_stage": bool(self.session_state.get("opt_stage_resume", False)),
            "resume_coord": bool(self.session_state.get("opt_resume", False)),
            "drift_keys": tuple(
                key for key in drift_keys if key != "opt_launch_profile"
            ),
        }

    def _packaging_snapshot_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for summary in self.history_summaries():
            if str(summary.status or "").strip().lower() == "running":
                continue
            packaging = summarize_run_packaging_snapshot(summary.result_path)
            row = {
                "run_dir": str(summary.run_dir),
                "name": str(summary.run_dir.name),
                "status": str(summary.status),
                "status_label": str(summary.status_label),
                "pipeline": str(summary.pipeline_mode),
                "backend": str(summary.backend),
                "updated_ts": float(summary.updated_ts or 0.0),
                "result_path": str(summary.result_path) if summary.result_path is not None else "",
                "has_results": bool(summary.result_path is not None),
                "row_count": int(summary.row_count or 0),
                "done_count": int(summary.done_count or 0),
                "running_count": int(summary.running_count or 0),
                "error_count": int(summary.error_count or 0),
                "note": str(summary.note or ""),
                "truth_ready_rows": int(packaging.packaging_truth_ready_rows or 0),
                "verification_pass_rows": int(packaging.packaging_verification_pass_rows or 0),
                "packaging_complete_rows": int(packaging.packaging_complete_rows or 0),
                "rows_with_packaging": int(packaging.rows_with_packaging or 0),
                "rows_considered": int(packaging.rows_considered or 0),
                "runtime_fallback_rows": int(packaging.runtime_fallback_rows or 0),
                "host_interference_rows": int(packaging.spring_host_interference_rows or 0),
                "pair_interference_rows": int(packaging.spring_pair_interference_rows or 0),
                "interference_rows": int(
                    int(packaging.spring_host_interference_rows or 0)
                    + int(packaging.spring_pair_interference_rows or 0)
                ),
                "status_counts_text": ", ".join(
                    f"{name}={count}" for name, count in tuple(packaging.status_counts or ())
                ),
            }
            if row["truth_ready_rows"] > 0 and row["verification_pass_rows"] > 0 and row["interference_rows"] == 0:
                row["ready_state"] = "truth-ready"
            elif row["verification_pass_rows"] > 0:
                row["ready_state"] = "verification-pass"
            elif row["rows_with_packaging"] > 0:
                row["ready_state"] = "packaging-partial"
            elif row["has_results"]:
                row["ready_state"] = "results-only"
            else:
                row["ready_state"] = "artifacts-missing"
            rows.append(row)
        return rows

    def finished_job_rows(self) -> list[dict[str, Any]]:
        rows = self._packaging_snapshot_rows()
        if bool(self.session_state.get("opt_finished_done_only", False)):
            rows = [row for row in rows if str(row.get("status") or "") == "done"]
        if bool(self.session_state.get("opt_finished_truth_ready_only", False)):
            rows = [row for row in rows if _int_value(row.get("truth_ready_rows")) > 0]
        if bool(self.session_state.get("opt_finished_verification_only", False)):
            rows = [row for row in rows if _int_value(row.get("verification_pass_rows")) > 0]

        sort_mode = str(
            self.session_state.get("opt_finished_sort_mode", FINISHED_JOB_SORT_OPTIONS[0])
            or FINISHED_JOB_SORT_OPTIONS[0]
        )
        if sort_mode == "Verification first":
            rows.sort(
                key=lambda row: (
                    -_int_value(row.get("verification_pass_rows")),
                    -_int_value(row.get("truth_ready_rows")),
                    _int_value(row.get("interference_rows")),
                    -float(row.get("updated_ts", 0.0) or 0.0),
                )
            )
        elif sort_mode == "Recent first":
            rows.sort(
                key=lambda row: (
                    -float(row.get("updated_ts", 0.0) or 0.0),
                    -_int_value(row.get("truth_ready_rows")),
                    -_int_value(row.get("verification_pass_rows")),
                )
            )
        elif sort_mode == "Least interference":
            rows.sort(
                key=lambda row: (
                    _int_value(row.get("interference_rows")),
                    -_int_value(row.get("truth_ready_rows")),
                    -_int_value(row.get("verification_pass_rows")),
                    -float(row.get("updated_ts", 0.0) or 0.0),
                )
            )
        elif sort_mode == "Most packaging rows":
            rows.sort(
                key=lambda row: (
                    -_int_value(row.get("rows_with_packaging")),
                    -_int_value(row.get("truth_ready_rows")),
                    -_int_value(row.get("verification_pass_rows")),
                    -float(row.get("updated_ts", 0.0) or 0.0),
                )
            )
        else:
            rows.sort(
                key=lambda row: (
                    -_int_value(row.get("truth_ready_rows")),
                    -_int_value(row.get("verification_pass_rows")),
                    _int_value(row.get("interference_rows")),
                    -float(row.get("updated_ts", 0.0) or 0.0),
                )
            )
        return rows

    def packaging_rows(self) -> list[dict[str, Any]]:
        rows = self._packaging_snapshot_rows()
        if bool(self.session_state.get("opt_packaging_done_only", False)):
            rows = [row for row in rows if str(row.get("status") or "") == "done"]
        if bool(self.session_state.get("opt_packaging_truth_ready_only", False)):
            rows = [row for row in rows if _int_value(row.get("truth_ready_rows")) > 0]
        if bool(self.session_state.get("opt_packaging_verification_only", False)):
            rows = [row for row in rows if _int_value(row.get("verification_pass_rows")) > 0]
        if bool(self.session_state.get("opt_packaging_zero_interference_only", False)):
            rows = [row for row in rows if _int_value(row.get("interference_rows")) == 0]

        sort_mode = str(
            self.session_state.get("opt_packaging_sort_mode", PACKAGING_SORT_OPTIONS[0])
            or PACKAGING_SORT_OPTIONS[0]
        )
        if sort_mode == "Zero interference first":
            rows.sort(
                key=lambda row: (
                    _int_value(row.get("interference_rows")),
                    -_int_value(row.get("truth_ready_rows")),
                    -_int_value(row.get("verification_pass_rows")),
                    -_int_value(row.get("rows_with_packaging")),
                    -float(row.get("updated_ts", 0.0) or 0.0),
                )
            )
        elif sort_mode == "Verification first":
            rows.sort(
                key=lambda row: (
                    -_int_value(row.get("verification_pass_rows")),
                    -_int_value(row.get("truth_ready_rows")),
                    _int_value(row.get("interference_rows")),
                    -_int_value(row.get("rows_with_packaging")),
                    -float(row.get("updated_ts", 0.0) or 0.0),
                )
            )
        elif sort_mode == "Most packaging rows":
            rows.sort(
                key=lambda row: (
                    -_int_value(row.get("rows_with_packaging")),
                    -_int_value(row.get("truth_ready_rows")),
                    -_int_value(row.get("verification_pass_rows")),
                    _int_value(row.get("interference_rows")),
                    -float(row.get("updated_ts", 0.0) or 0.0),
                )
            )
        elif sort_mode == "Recent first":
            rows.sort(
                key=lambda row: (
                    -float(row.get("updated_ts", 0.0) or 0.0),
                    -_int_value(row.get("truth_ready_rows")),
                    -_int_value(row.get("verification_pass_rows")),
                    _int_value(row.get("interference_rows")),
                )
            )
        else:
            rows.sort(
                key=lambda row: (
                    -_int_value(row.get("truth_ready_rows")),
                    -_int_value(row.get("verification_pass_rows")),
                    _int_value(row.get("interference_rows")),
                    -_int_value(row.get("rows_with_packaging")),
                    -float(row.get("updated_ts", 0.0) or 0.0),
                )
            )
        return rows

    def packaging_overview(self) -> dict[str, Any]:
        rows = self.packaging_rows()
        return {
            "total_runs": len(rows),
            "truth_ready_runs": sum(1 for row in rows if _int_value(row.get("truth_ready_rows")) > 0),
            "verification_runs": sum(
                1 for row in rows if _int_value(row.get("verification_pass_rows")) > 0
            ),
            "zero_interference_runs": sum(
                1 for row in rows if _int_value(row.get("interference_rows")) == 0
            ),
            "fallback_runs": sum(
                1 for row in rows if _int_value(row.get("runtime_fallback_rows")) > 0
            ),
            "packaging_rows_total": sum(_int_value(row.get("rows_with_packaging")) for row in rows),
            "truth_ready_rows_total": sum(_int_value(row.get("truth_ready_rows")) for row in rows),
            "verification_rows_total": sum(
                _int_value(row.get("verification_pass_rows")) for row in rows
            ),
            "best_run": str(rows[0].get("name") or "") if rows else "",
            "best_ready_state": str(rows[0].get("ready_state") or "") if rows else "",
            "sort_mode": str(
                self.session_state.get("opt_packaging_sort_mode", PACKAGING_SORT_OPTIONS[0])
                or PACKAGING_SORT_OPTIONS[0]
            ),
            "filters": {
                "done_only": bool(self.session_state.get("opt_packaging_done_only", False)),
                "truth_ready_only": bool(
                    self.session_state.get("opt_packaging_truth_ready_only", False)
                ),
                "verification_only": bool(
                    self.session_state.get("opt_packaging_verification_only", False)
                ),
                "zero_interference_only": bool(
                    self.session_state.get("opt_packaging_zero_interference_only", False)
                ),
            },
        }

    def selected_packaging_row(
        self,
        run_dir: Path | str | None,
    ) -> dict[str, Any] | None:
        resolved = _resolved_path_text(run_dir)
        if not resolved:
            return None
        for row in self.packaging_rows():
            if _resolved_path_text(row.get("run_dir")) == resolved:
                return row
        return None

    def dashboard_snapshot(self) -> dict[str, Any]:
        finished_rows = self.finished_job_rows()
        handoff_rows = self.handoff_overview_rows()
        packaging_rows = self.packaging_rows()
        return {
            "launch_profile": self.launch_profile_summary(),
            "launch_readiness": self.launch_readiness_summary(),
            "latest_pointer": self.latest_pointer_summary(),
            "selected_run_next_step": self.selected_run_next_step_summary(),
            "resume_target": self.resume_target_summary(),
            "active_surface": self.active_job_surface(),
            "finished_overview": self.finished_job_overview(),
            "best_finished_row": dict(finished_rows[0]) if finished_rows else None,
            "handoff_overview": self.handoff_overview_summary(),
            "best_handoff_row": dict(handoff_rows[0]) if handoff_rows else None,
            "packaging_overview": self.packaging_overview(),
            "best_packaging_row": dict(packaging_rows[0]) if packaging_rows else None,
        }

    def finished_job_overview(self) -> dict[str, Any]:
        rows = self.finished_job_rows()
        status_counts: dict[str, int] = {}
        pipeline_counts: dict[str, int] = {}
        for row in rows:
            status_key = str(row.get("status_label") or row.get("status") or "UNKNOWN")
            pipeline_key = str(row.get("pipeline") or "unknown")
            status_counts[status_key] = int(status_counts.get(status_key, 0)) + 1
            pipeline_counts[pipeline_key] = int(pipeline_counts.get(pipeline_key, 0)) + 1
        return {
            "total_jobs": len(rows),
            "jobs_with_results": sum(1 for row in rows if bool(row.get("has_results"))),
            "truth_ready_jobs": sum(1 for row in rows if _int_value(row.get("truth_ready_rows")) > 0),
            "verification_pass_jobs": sum(
                1 for row in rows if _int_value(row.get("verification_pass_rows")) > 0
            ),
            "interference_jobs": sum(1 for row in rows if _int_value(row.get("interference_rows")) > 0),
            "runtime_fallback_jobs": sum(
                1 for row in rows if _int_value(row.get("runtime_fallback_rows")) > 0
            ),
            "rows_with_packaging_total": sum(_int_value(row.get("rows_with_packaging")) for row in rows),
            "truth_ready_rows_total": sum(_int_value(row.get("truth_ready_rows")) for row in rows),
            "verification_rows_total": sum(
                _int_value(row.get("verification_pass_rows")) for row in rows
            ),
            "status_counts": tuple(sorted(status_counts.items())),
            "pipeline_counts": tuple(sorted(pipeline_counts.items())),
            "sort_mode": str(
                self.session_state.get("opt_finished_sort_mode", FINISHED_JOB_SORT_OPTIONS[0])
                or FINISHED_JOB_SORT_OPTIONS[0]
            ),
            "filters": {
                "done_only": bool(self.session_state.get("opt_finished_done_only", False)),
                "truth_ready_only": bool(
                    self.session_state.get("opt_finished_truth_ready_only", False)
                ),
                "verification_only": bool(
                    self.session_state.get("opt_finished_verification_only", False)
                ),
            },
        }

    def contract_snapshot(self):
        return build_contract_snapshot(self.session_state, ui_root=self.ui_root)

    def contract_drift_summary(self, summary: OptimizationRunSummary | None) -> dict[str, Any]:
        snapshot = self.contract_snapshot()
        if summary is None:
            return {
                "selected_run_dir": "",
                "diff_bits": tuple(),
                "scope_payload": {},
                "baseline_compatibility": "",
            }
        diff_bits = tuple(
            compare_objective_contract_to_current(
                objective_keys=summary.objective_keys,
                penalty_key=summary.penalty_key,
                penalty_tol=summary.penalty_tol,
                current_objective_keys=snapshot.objective_keys,
                current_penalty_key=snapshot.penalty_key,
                current_penalty_tol=snapshot.penalty_tol,
            )
        )
        scope_payload = problem_scope_surface_payload(
            summary=summary,
            current_problem_hash=snapshot.problem_hash,
            current_problem_hash_mode=snapshot.problem_hash_mode,
        )
        selected_baseline_ref = str(summary.baseline_source_path or "").strip() or str(
            summary.baseline_source_label or summary.baseline_source_kind or ""
        ).strip()
        current_baseline_ref = str(snapshot.baseline_path or "").strip() or str(
            snapshot.baseline_source_label or snapshot.baseline_source_kind or ""
        ).strip()
        baseline_compatibility = _compatibility_text(selected_baseline_ref, current_baseline_ref)
        return {
            "selected_run_dir": str(summary.run_dir),
            "selected_pipeline": str(summary.pipeline_mode or ""),
            "selected_status": str(summary.status_label or summary.status or ""),
            "selected_objective_keys": tuple(summary.objective_keys or ()),
            "selected_penalty_key": str(summary.penalty_key or ""),
            "selected_penalty_tol": summary.penalty_tol,
            "selected_problem_hash": str(summary.problem_hash or ""),
            "selected_problem_hash_mode": str(summary.problem_hash_mode or ""),
            "selected_baseline_label": str(
                summary.baseline_source_label or summary.baseline_source_kind or ""
            ),
            "selected_baseline_path": str(summary.baseline_source_path or ""),
            "current_objective_keys": tuple(snapshot.objective_keys or ()),
            "current_penalty_key": str(snapshot.penalty_key or ""),
            "current_penalty_tol": snapshot.penalty_tol,
            "current_problem_hash": str(snapshot.problem_hash or ""),
            "current_problem_hash_mode": str(snapshot.problem_hash_mode or ""),
            "current_baseline_label": str(
                snapshot.baseline_source_label or snapshot.baseline_source_kind or ""
            ),
            "current_baseline_path": str(snapshot.baseline_path or ""),
            "diff_bits": diff_bits,
            "scope_payload": dict(scope_payload or {}),
            "baseline_compatibility": baseline_compatibility,
        }

    def launch_readiness_summary(self) -> dict[str, Any]:
        snapshot = self.contract_snapshot()
        launch_profile = self.launch_profile_summary()
        packaging_overview = self.packaging_overview()
        handoff_overview = self.handoff_overview_summary()
        selected_run_dir = self.session_state.get(_HISTORY_SELECTED_RUN_DIR_KEY)
        selected_details = self.selected_run_details(selected_run_dir) if selected_run_dir else None
        selected_summary = getattr(selected_details, "summary", None) if selected_details is not None else None
        drift = self.contract_drift_summary(selected_summary)
        active_surface = self.active_job_surface()

        rows: list[dict[str, Any]] = []

        contract_issues: list[str] = []
        if not tuple(snapshot.objective_keys or ()):
            contract_issues.append("objective keys missing")
        if not str(snapshot.penalty_key or "").strip():
            contract_issues.append("penalty key missing")
        if not str(snapshot.problem_hash or "").strip():
            contract_issues.append("problem hash missing")
        rows.append(
            {
                "title": "Contract & scope",
                "status": "warn" if contract_issues else "ok",
                "summary": (
                    "Blockers: " + ", ".join(contract_issues) + "."
                    if contract_issues
                    else "Objective contract, penalty gate and problem scope are materialized."
                ),
                "action": "Contract",
            }
        )

        search_space_issues: list[str] = []
        if int(snapshot.search_param_count or 0) <= 0:
            search_space_issues.append("no design params in ranges.json")
        if int(snapshot.enabled_suite_total or 0) <= 0:
            search_space_issues.append("no enabled suite rows")
        rows.append(
            {
                "title": "Search space & suite",
                "status": "warn" if search_space_issues else "ok",
                "summary": (
                    "Blockers: " + ", ".join(search_space_issues) + "."
                    if search_space_issues
                    else (
                        f"Design params={int(snapshot.search_param_count or 0)}, "
                        f"enabled suite rows={int(snapshot.enabled_suite_total or 0)}."
                    )
                ),
                "action": "Contract",
            }
        )

        selected_scope = dict(drift.get("scope_payload") or {})
        diff_bits = tuple(str(bit) for bit in (drift.get("diff_bits") or ()) if str(bit).strip())
        baseline_compatibility = str(drift.get("baseline_compatibility") or "")
        if selected_summary is None:
            align_status = "info"
            align_summary = "Historical run is not selected; launch will use the current desktop contract only."
        elif str(selected_scope.get("compatibility") or "") == "different" or str(
            selected_scope.get("mode_compatibility") or ""
        ) == "different":
            align_status = "warn"
            align_summary = (
                "Selected run belongs to a different problem scope/hash mode than the current launch contract."
            )
        elif baseline_compatibility == "different":
            align_status = "warn"
            align_summary = "Selected run uses another baseline source than the current launch contract."
        elif diff_bits:
            align_status = "info"
            align_summary = (
                "Selected run differs by objective contract: " + ", ".join(diff_bits) + "."
            )
        else:
            align_status = "ok"
            align_summary = "Selected run is aligned with the current launch contract and problem scope."
        rows.append(
            {
                "title": "Selected run alignment",
                "status": align_status,
                "summary": align_summary,
                "action": "Contract drift",
            }
        )

        if int(packaging_overview.get("total_runs", 0) or 0) <= 0:
            packaging_status = "info"
            packaging_summary = "No finished packaging evidence yet; launch can proceed, but comparison history is still empty."
        elif int(packaging_overview.get("truth_ready_runs", 0) or 0) <= 0:
            packaging_status = "warn"
            packaging_summary = "Finished runs exist, but none is truth-ready for packaging yet."
        elif int(packaging_overview.get("zero_interference_runs", 0) or 0) <= 0:
            packaging_status = "warn"
            packaging_summary = "Packaging evidence exists, but all visible runs still show interference rows."
        else:
            packaging_status = "ok"
            packaging_summary = (
                f"Packaging evidence is available: truth-ready runs={int(packaging_overview.get('truth_ready_runs', 0) or 0)}, "
                f"zero-interference runs={int(packaging_overview.get('zero_interference_runs', 0) or 0)}."
            )
        rows.append(
            {
                "title": "Packaging evidence",
                "status": packaging_status,
                "summary": packaging_summary,
                "action": "Packaging",
            }
        )

        if str(launch_profile.get("launch_pipeline") or "") == "coordinator":
            if int(handoff_overview.get("total_candidates", 0) or 0) <= 0:
                handoff_status = "info"
                handoff_summary = "Coordinator launch is available directly, but no staged handoff candidate is selected in history."
            else:
                handoff_status = "ok"
                handoff_summary = (
                    f"Handoff candidates are available: best={handoff_overview.get('best_run') or '—'} "
                    f"preset={handoff_overview.get('best_preset') or '—'}."
                )
        else:
            if int(handoff_overview.get("total_candidates", 0) or 0) <= 0:
                handoff_status = "info"
                handoff_summary = "No handoff candidates yet; they will appear after staged runs produce continuation plans."
            else:
                handoff_status = "ok"
                handoff_summary = (
                    f"Staged continuation inventory already exists: candidates={int(handoff_overview.get('total_candidates', 0) or 0)}."
                )
        rows.append(
            {
                "title": "Handoff inventory",
                "status": handoff_status,
                "summary": handoff_summary,
                "action": "Handoff",
            }
        )

        if active_surface:
            active_job = active_surface.get("job")
            runtime_status = "info"
            runtime_summary = (
                f"Active job is running: {getattr(active_job, 'pipeline_mode', '') or '—'} / "
                f"{getattr(active_job, 'backend', '') or '—'}."
            )
        else:
            runtime_status = "ok"
            runtime_summary = (
                f"Launch surface is idle and ready: profile={launch_profile.get('profile_label') or '—'}, "
                f"pipeline={launch_profile.get('launch_pipeline') or '—'}."
            )
        rows.append(
            {
                "title": "Runtime state",
                "status": runtime_status,
                "summary": runtime_summary,
                "action": "Runtime",
            }
        )

        warn_count = sum(1 for row in rows if str(row.get("status") or "") == "warn")
        info_count = sum(1 for row in rows if str(row.get("status") or "") == "info")
        ok_count = sum(1 for row in rows if str(row.get("status") or "") == "ok")
        if warn_count > 0:
            headline = "Review blockers before launch."
            next_action = str(next((row.get("action") for row in rows if row.get("status") == "warn"), "Contract"))
        elif info_count > 0:
            headline = "Launch is usable, but there are contextual notes for the operator."
            next_action = str(next((row.get("action") for row in rows if row.get("status") == "info"), "Runtime"))
        else:
            headline = "Launch surface looks aligned and ready."
            next_action = "Runtime"
        return {
            "rows": tuple(rows),
            "warn_count": int(warn_count),
            "info_count": int(info_count),
            "ok_count": int(ok_count),
            "headline": headline,
            "next_action": next_action,
        }

    def stage_policy_blueprint_rows(self) -> list[dict[str, Any]]:
        return build_stage_policy_blueprint_rows(self.session_state)

    def command_preview_text(self) -> str:
        plan = build_optimization_launch_plan(
            self.session_state,
            run_dir=Path("DUMMY_RUN_DIR"),
            ui_root=self.ui_root,
            python_executable=self.python_executable,
            ui_jobs_default=int(
                self.session_state.get("ui_jobs", self.ui_jobs_default) or self.ui_jobs_default
            ),
        )
        return " ".join(str(part) for part in plan.cmd)

    def _remember_started_job(
        self,
        job: DistOptJob,
        *,
        launch_kind: str,
        source_run_dir: Path | None = None,
    ) -> None:
        run_dir_text = _resolved_path_text(getattr(job, "run_dir", None))
        pipeline_mode = str(getattr(job, "pipeline_mode", "") or "").strip()
        backend = str(getattr(job, "backend", "") or "").strip()
        is_staged = pipeline_mode == "staged"
        self.session_state[_HISTORY_SELECTED_RUN_DIR_KEY] = run_dir_text
        self.session_state[_ACTIVE_LAUNCH_CONTEXT_KEY] = {
            "kind": str(launch_kind or "manual"),
            "run_dir": run_dir_text,
            "pipeline_mode": pipeline_mode,
            "backend": backend,
            "source_run_dir": _resolved_path_text(source_run_dir),
        }
        self.session_state["opt_use_staged"] = bool(is_staged)
        self.session_state["use_staged_opt"] = bool(is_staged)

    def start_job(self) -> DistOptJob:
        job = start_optimization_job(
            self.session_state,
            ui_root=self.ui_root,
            ui_jobs_default=int(
                self.session_state.get("ui_jobs", self.ui_jobs_default) or self.ui_jobs_default
            ),
            problem_hash_mode=problem_hash_mode_for_launch(self.session_state),
            python_executable=self.python_executable,
        )
        self._remember_started_job(job, launch_kind="manual")
        return job

    def start_handoff(self, source_run_dir: Path | str) -> DistOptJob:
        job = start_coordinator_handoff_job(
            self.session_state,
            source_run_dir=Path(source_run_dir),
            ui_root=self.ui_root,
            problem_hash_mode=problem_hash_mode_for_launch(self.session_state),
            python_executable=self.python_executable,
        )
        self._remember_started_job(
            job,
            launch_kind="handoff",
            source_run_dir=Path(source_run_dir),
        )
        return job

    def clear_finished_job(self) -> None:
        clear_job_from_session(self.session_state)
        self.session_state.pop(_ACTIVE_LAUNCH_CONTEXT_KEY, None)

    def request_soft_stop(self) -> bool:
        job = self.current_job()
        if job is None:
            return False
        return write_soft_stop_file(getattr(job, "stop_file", None))

    def request_hard_stop(self) -> bool:
        job = self.current_job()
        if job is None:
            return False
        stop_written = write_soft_stop_file(getattr(job, "stop_file", None))
        terminate_optimization_process(job.proc)
        return stop_written

    def active_job_surface(self) -> dict[str, Any]:
        job = self.current_job()
        if job is None:
            return {}
        proc = getattr(job, "proc", None)
        rc = None
        poll = getattr(proc, "poll", None)
        if callable(poll):
            try:
                rc = poll()
            except Exception:
                rc = None
        log_text = tail_file_text(getattr(job, "log_path"))
        if rc is None:
            runtime_summary = build_active_runtime_summary(
                job,
                tail_file_text_fn=tail_file_text,
                parse_done_from_log_fn=parse_done_from_log,
                active_launch_context=self.active_launch_context(),
            )
        else:
            runtime_summary = build_run_runtime_summary(
                getattr(job, "run_dir", None),
                pipeline_mode=getattr(job, "pipeline_mode", ""),
                backend=getattr(job, "backend", ""),
                budget=getattr(job, "budget", 0),
                done=parse_done_from_log(log_text),
                tail_state=log_text,
                active_launch_context=self.active_launch_context(),
            )
        captions = [
            text
            for text in (
                active_runtime_progress_caption(runtime_summary),
                active_runtime_trial_health_caption(runtime_summary),
                active_runtime_penalty_gate_caption(runtime_summary),
                active_runtime_recent_errors_caption(runtime_summary),
                active_handoff_provenance_caption(runtime_summary),
            )
            if str(text or "").strip()
        ]
        stage_policy_rows: list[dict[str, Any]] = []
        if str(getattr(job, "pipeline_mode", "") or "") == "staged":
            for stage_idx, stage_name in enumerate(STAGE_NAMES):
                stage_policy_rows.append(
                    summarize_stage_policy_runtime(
                        getattr(job, "run_dir", None),
                        stage_idx=stage_idx,
                        stage_name=stage_name,
                    )
                )
        return {
            "job": job,
            "returncode": rc,
            "log_text": log_text,
            "soft_stop_requested": soft_stop_requested(job),
            "runtime_summary": runtime_summary,
            "captions": captions,
            "stage_policy_rows": tuple(stage_policy_rows),
        }

    def history_summaries(self) -> list[OptimizationRunSummary]:
        active_job = self.current_job()
        active_run_dir = getattr(active_job, "run_dir", None) if active_job is not None else None
        return discover_workspace_optimization_runs(
            self.workspace_dir,
            active_run_dir=active_run_dir,
        )

    def handoff_overview_rows(self) -> list[dict[str, Any]]:
        summaries = self.history_summaries()
        active_job = self.current_job()
        rows = enrich_handoff_overview_rows(
            build_handoff_overview_rows(
                summaries,
                active_job=active_job,
                active_launch_context=self.active_launch_context(),
            )
        )
        rows = filter_handoff_overview_rows(
            rows,
            full_ring_only=bool(self.session_state.get("opt_handoff_full_ring_only", False)),
            done_only=bool(self.session_state.get("opt_handoff_done_only", False)),
            min_seeds=int(self.session_state.get("opt_handoff_min_seeds", 0) or 0),
        )
        return sort_handoff_overview_rows(
            rows,
            sort_mode=str(
                self.session_state.get("opt_handoff_sort_mode", HANDOFF_SORT_OPTIONS[0])
                or HANDOFF_SORT_OPTIONS[0]
            ),
        )

    def handoff_overview_summary(self) -> dict[str, Any]:
        rows = self.handoff_overview_rows()
        if not rows:
            return {
                "total_candidates": 0,
                "live_candidates": 0,
                "done_candidates": 0,
                "full_ring_candidates": 0,
                "seed_total": 0,
                "best_run": "",
                "best_preset": "",
                "best_score": 0.0,
                "sort_mode": str(
                    self.session_state.get("opt_handoff_sort_mode", HANDOFF_SORT_OPTIONS[0])
                    or HANDOFF_SORT_OPTIONS[0]
                ),
                "filters": {
                    "full_ring_only": bool(self.session_state.get("opt_handoff_full_ring_only", False)),
                    "done_only": bool(self.session_state.get("opt_handoff_done_only", False)),
                    "min_seeds": int(self.session_state.get("opt_handoff_min_seeds", 0) or 0),
                },
            }
        best = rows[0]
        return {
            "total_candidates": len(rows),
            "live_candidates": sum(1 for row in rows if str(row.get("live_now") or "") == "LIVE"),
            "done_candidates": sum(
                1 for row in rows if str(row.get("status") or "").strip().upper() == "DONE"
            ),
            "full_ring_candidates": sum(
                1 for row in rows if str(row.get("full_ring") or "").strip().lower() == "yes"
            ),
            "seed_total": sum(int(row.get("seeds", 0) or 0) for row in rows),
            "best_run": str(best.get("run") or ""),
            "best_preset": str(best.get("preset") or ""),
            "best_score": float(best.get("quality_score", 0.0) or 0.0),
            "sort_mode": str(
                self.session_state.get("opt_handoff_sort_mode", HANDOFF_SORT_OPTIONS[0])
                or HANDOFF_SORT_OPTIONS[0]
            ),
            "filters": {
                "full_ring_only": bool(self.session_state.get("opt_handoff_full_ring_only", False)),
                "done_only": bool(self.session_state.get("opt_handoff_done_only", False)),
                "min_seeds": int(self.session_state.get("opt_handoff_min_seeds", 0) or 0),
            },
        }

    def selected_handoff_row(
        self,
        run_dir: Path | str | None,
    ) -> dict[str, Any] | None:
        resolved = _resolved_path_text(run_dir)
        if not resolved:
            return None
        for row in self.handoff_overview_rows():
            if _resolved_path_text(row.get("__run_dir")) == resolved:
                return row
        return None

    def selected_run_details(
        self,
        run_dir: Path | str | None,
    ) -> DesktopOptimizerRunDetails | None:
        if run_dir is None:
            return None
        summary = summarize_optimization_run(
            Path(run_dir),
            active_run_dir=getattr(self.current_job(), "run_dir", None),
        )
        if summary is None:
            return None
        packaging = summarize_run_packaging_snapshot(summary.result_path)
        stage_policy_rows: list[dict[str, Any]] = []
        if str(summary.pipeline_mode or "") == "staged":
            for stage_idx, stage_name in enumerate(STAGE_NAMES):
                stage_policy_rows.append(
                    summarize_stage_policy_runtime(
                        summary.run_dir,
                        stage_idx=stage_idx,
                        stage_name=stage_name,
                    )
                )
        log_path = summary.log_path if summary.log_path is not None else Path(summary.run_dir) / "coordinator.log"
        return DesktopOptimizerRunDetails(
            summary=summary,
            packaging_snapshot=packaging,
            stage_policy_rows=tuple(stage_policy_rows),
            log_tail=tail_file_text(log_path),
        )


__all__ = [
    "DesktopOptimizerRunDetails",
    "DesktopOptimizerRuntime",
]
