from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from pneumo_solver_ui.desktop_engineering_analysis_model import (
    ANALYSIS_CONTEXT_FILENAME,
    ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
    ANALYSIS_WORKSPACE_ID,
    ANIMATOR_LINK_CONTRACT_FILENAME,
    ANIMATOR_WORKSPACE_ID,
    ENGINEERING_ANALYSIS_CONSUMED_BY,
    ENGINEERING_ANALYSIS_EVIDENCE_SCHEMA,
    ENGINEERING_ANALYSIS_EVIDENCE_SCHEMA_VERSION,
    ENGINEERING_ANALYSIS_HANDOFF_ID,
    ENGINEERING_ANALYSIS_PRODUCED_BY,
    SELECTED_RUN_CONSUMED_BY,
    SELECTED_RUN_CONTRACT_FILENAME,
    SELECTED_RUN_HANDOFF_ID,
    SELECTED_RUN_PRODUCED_BY,
    SYSTEM_INFLUENCE_UNIT_CATALOG,
    EngineeringAnalysisArtifact,
    EngineeringAnalysisJobResult,
    EngineeringAnalysisPipelineRow,
    EngineeringAnalysisSnapshot,
    SelectedRunContractSnapshot,
    build_analysis_compare_contract,
    build_analysis_to_animator_link_contract,
    build_compare_influence_surface,
    build_sensitivity_summary,
    selected_run_context_from_payload,
)


LATEST_ENGINEERING_ANALYSIS_EVIDENCE_MANIFEST = "latest_engineering_analysis_evidence_manifest.json"
SELECTED_RUN_CONTRACT_ENV = "PNEUMO_SELECTED_RUN_CONTRACT_PATH"
REQUIRED_SELECTED_RUN_CONTRACT_FIELDS: tuple[str, ...] = (
    "run_id",
    "mode",
    "status",
    "started_at_utc",
    "active_baseline_hash",
    "objective_contract_hash",
    "hard_gate_key",
    "hard_gate_tolerance",
    "suite_snapshot_hash",
    "results_artifact_index",
)
_ENGINEERING_ANALYSIS_ARTIFACT_SPECS: tuple[tuple[str, str, str, str, bool], ...] = (
    ("system_influence.json", "system_influence_json", "Данные влияния системы", "influence", True),
    ("SYSTEM_INFLUENCE.md", "system_influence_md", "Отчёт влияния системы", "report", True),
    ("system_influence_params.csv", "system_influence_params_csv", "Таблица параметров влияния", "influence", True),
    ("system_influence_edges.csv", "system_influence_edges_csv", "Таблица связей влияния", "influence", False),
    ("system_influence_paths.csv", "system_influence_paths_csv", "Таблица путей влияния", "influence", False),
    ("AUTOPILOT_V20_WRAPPER.json", "autopilot_v20_wrapper_json", "Данные калибровочного запуска v20", "calibration", False),
    ("AUTOPILOT_V19_WRAPPER.json", "autopilot_v19_wrapper_json", "Данные калибровочного запуска v19", "calibration", False),
    ("PARAM_STAGING_INFLUENCE.md", "param_staging_influence_md", "Отчёт подбора шагов по влиянию", "calibration", False),
    ("stages_influence.json", "stages_influence_json", "Шаги подбора по влиянию", "calibration", False),
    ("REPORT_FULL.md", "report_full_md", "Полный отчёт калибровки", "report", False),
    ("fit_report_final.json", "fit_report_final_json", "Итоговый отчёт подгонки", "calibration", False),
    ("fit_details_final.json", "fit_details_final_json", "Итоговые детали подгонки", "calibration", False),
    ("report.md", "calibration_report_md", "Подробный отчёт калибровки", "report", False),
    ("fit_report.json", "fit_report_json", "Отчёт подгонки", "calibration", False),
    ("fit_details.json", "fit_details_json", "Детали подгонки", "calibration", False),
    ("uq_sensitivity_summary.csv", "uq_sensitivity_summary_csv", "Сводка неопределённости", "uncertainty", False),
    ("measurement_priority.csv", "measurement_priority_csv", "Приоритеты измерений", "uncertainty", False),
    ("uq_runs.csv", "uq_runs_csv", "Прогоны неопределённости", "uncertainty", False),
    ("uq_report.md", "uq_report_md", "Отчёт неопределённости", "uncertainty", False),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_dumps_canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _selected_contract_hash(payload: Mapping[str, Any]) -> str:
    clean = dict(payload or {})
    clean.pop("selected_run_contract_hash", None)
    return _sha256_text(_json_dumps_canonical(clean))


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(path))


def _payload_hash(payload: Mapping[str, Any], *, hash_key: str) -> str:
    clean = dict(payload or {})
    clean.pop(hash_key, None)
    return _sha256_text(_json_dumps_canonical(clean))


def _safe_read_json_dict(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists() or not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def _first_payload_value(payload: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            return payload.get(key)
    return None


def _axis_names(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        return [str(key) for key in value.keys()]
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            raw = (
                item.get("key")
                or item.get("name")
                or item.get("label")
                or item.get("param")
                or item.get("metric")
            )
            names.append(str(raw or ""))
        else:
            names.append(str(item or ""))
    return [name for name in names if name.strip()]


def _unit_map(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(unit) for key, unit in value.items() if str(key).strip() and str(unit).strip()}


def _resolve_existing_file(path: Path | str | None) -> Path | None:
    if path in (None, ""):
        return None
    try:
        candidate = Path(path).expanduser().resolve()
    except Exception:
        candidate = Path(path).expanduser()
    return candidate if candidate.exists() and candidate.is_file() else None


def _resolve_existing_dir(path: Path | str | None) -> Path | None:
    if path in (None, ""):
        return None
    try:
        candidate = Path(path).expanduser().resolve()
    except Exception:
        candidate = Path(path).expanduser()
    return candidate if candidate.exists() and candidate.is_dir() else None


def _effective_workspace_dir(repo_root: Path) -> Path:
    raw = os.environ.get("PNEUMO_WORKSPACE_DIR", "").strip()
    if raw:
        try:
            return Path(raw).expanduser().resolve()
        except Exception:
            return Path(raw).expanduser()
    return (repo_root / "pneumo_solver_ui" / "workspace").resolve()


def _default_selected_run_contract_path() -> Path:
    raw_path = os.environ.get(SELECTED_RUN_CONTRACT_ENV, "").strip()
    if raw_path:
        try:
            return Path(raw_path).expanduser().resolve()
        except Exception:
            return Path(raw_path).expanduser()
    raw_workspace = os.environ.get("PNEUMO_WORKSPACE_DIR", "").strip()
    if raw_workspace:
        try:
            workspace = Path(raw_workspace).expanduser().resolve()
        except Exception:
            workspace = Path(raw_workspace).expanduser()
    else:
        workspace = (Path.cwd() / "pneumo_solver_ui" / "workspace").resolve()
    return (
        workspace
        / "handoffs"
        / SELECTED_RUN_PRODUCED_BY
        / SELECTED_RUN_CONTRACT_FILENAME
    )


def _latest_child_dir(root: Path) -> Path | None:
    if not root.exists() or not root.is_dir():
        return None
    dirs = [item for item in root.iterdir() if item.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda item: item.stat().st_mtime)


def _value_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, Mapping):
        return not bool(value)
    return False


def _selected_contract_mismatch_summary(
    *,
    status: str,
    path: Path | None,
    missing_fields: Sequence[str],
    blocking_states: Sequence[str],
    warnings: Sequence[str],
) -> dict[str, Any]:
    return {
        "scope": "selected_run_contract",
        "handoff_id": SELECTED_RUN_HANDOFF_ID,
        "status": str(status or "MISSING"),
        "contract_path": str(path or ""),
        "missing_fields": [str(item) for item in missing_fields],
        "blocking_states": [str(item) for item in blocking_states],
        "warnings": [str(item) for item in warnings],
    }


def load_selected_run_contract(path: Path | str | None = None) -> SelectedRunContractSnapshot:
    """Load the frozen HO-007 selected run contract for WS-ANALYSIS."""

    contract_path = Path(path).expanduser() if path is not None else _default_selected_run_contract_path()
    try:
        contract_path = contract_path.resolve()
    except Exception:
        pass

    if not contract_path.exists() or not contract_path.is_file():
        blocking = ("missing selected run contract",)
        status = "MISSING"
        return SelectedRunContractSnapshot(
            path=contract_path,
            exists=False,
            status=status,
            blocking_states=blocking,
            mismatch_summary=_selected_contract_mismatch_summary(
                status=status,
                path=contract_path,
                missing_fields=(),
                blocking_states=blocking,
                warnings=(),
            ),
        )

    try:
        payload_obj = json.loads(contract_path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        blocking = (f"invalid selected run contract: {exc}",)
        status = "INVALID"
        return SelectedRunContractSnapshot(
            path=contract_path,
            exists=True,
            status=status,
            blocking_states=blocking,
            mismatch_summary=_selected_contract_mismatch_summary(
                status=status,
                path=contract_path,
                missing_fields=(),
                blocking_states=blocking,
                warnings=(),
            ),
        )
    if not isinstance(payload_obj, Mapping):
        blocking = ("selected run contract root is not an object",)
        status = "INVALID"
        return SelectedRunContractSnapshot(
            path=contract_path,
            exists=True,
            status=status,
            blocking_states=blocking,
            mismatch_summary=_selected_contract_mismatch_summary(
                status=status,
                path=contract_path,
                missing_fields=(),
                blocking_states=blocking,
                warnings=(),
            ),
        )

    payload = dict(payload_obj)
    missing_fields = tuple(
        field
        for field in REQUIRED_SELECTED_RUN_CONTRACT_FIELDS
        if _value_missing(payload.get(field))
    )
    warnings: list[str] = []
    blocking_states: list[str] = []
    if str(payload.get("handoff_id") or "").strip() != SELECTED_RUN_HANDOFF_ID:
        blocking_states.append("handoff_id mismatch")
    if str(payload.get("source_workspace") or "").strip() not in {"", SELECTED_RUN_PRODUCED_BY}:
        blocking_states.append("source workspace mismatch")
    if str(payload.get("target_workspace") or "").strip() not in {"", SELECTED_RUN_CONSUMED_BY}:
        blocking_states.append("target workspace mismatch")

    stored_hash = str(payload.get("selected_run_contract_hash") or "").strip()
    computed_hash = _selected_contract_hash(payload)
    if stored_hash and stored_hash != computed_hash:
        warnings.append("selected run contract hash mismatch")

    if missing_fields:
        warnings.append("missing selected run fields: " + ", ".join(missing_fields))
    if str(payload.get("analysis_handoff_ready_state") or "").strip().lower() == "blocked":
        blocking_states.extend(str(item) for item in (payload.get("blocking_states") or ()) if str(item).strip())

    status = "READY"
    if blocking_states:
        status = "BLOCKED"
    elif missing_fields or warnings:
        status = "DEGRADED"

    effective_hash = stored_hash or computed_hash
    context = selected_run_context_from_payload(
        payload,
        contract_path=contract_path,
        contract_hash=effective_hash,
    )
    if not context.run_dir:
        blocking_states.append("selected run contract missing run_dir")
        status = "BLOCKED"

    mismatch_summary = _selected_contract_mismatch_summary(
        status=status,
        path=contract_path,
        missing_fields=missing_fields,
        blocking_states=blocking_states,
        warnings=warnings,
    )
    return SelectedRunContractSnapshot(
        path=contract_path,
        exists=True,
        status=status,
        payload=payload,
        selected_run_context=context,
        selected_run_contract_hash=effective_hash,
        computed_contract_hash=computed_hash,
        missing_fields=missing_fields,
        blocking_states=tuple(blocking_states),
        warnings=tuple(warnings),
        mismatch_summary=mismatch_summary,
    )


class DesktopEngineeringAnalysisRuntime:
    def __init__(self, *, repo_root: Path, python_executable: str = "") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.python_executable = str(python_executable or "")
        self.send_bundles_dir = self.repo_root / "send_bundles"

    def selected_run_contract_path(self) -> Path:
        return (
            _effective_workspace_dir(self.repo_root)
            / "handoffs"
            / SELECTED_RUN_PRODUCED_BY
            / SELECTED_RUN_CONTRACT_FILENAME
        ).resolve()

    def analysis_handoff_dir(self) -> Path:
        return (_effective_workspace_dir(self.repo_root) / "handoffs" / ANALYSIS_WORKSPACE_ID).resolve()

    def analysis_context_path(self) -> Path:
        return (self.analysis_handoff_dir() / ANALYSIS_CONTEXT_FILENAME).resolve()

    def animator_link_contract_path(self) -> Path:
        return (self.analysis_handoff_dir() / ANIMATOR_LINK_CONTRACT_FILENAME).resolve()

    def load_selected_run_contract(
        self,
        path: Path | str | None = None,
    ) -> SelectedRunContractSnapshot:
        return load_selected_run_contract(path or self.selected_run_contract_path())

    def resolve_run_dir(self, run_dir: Path | str | None = None) -> Path | None:
        if run_dir:
            try:
                candidate = Path(run_dir).expanduser().resolve()
            except Exception:
                candidate = Path(run_dir).expanduser()
            return candidate if candidate.exists() and candidate.is_dir() else None

        env_run = os.environ.get("PNEUMO_ENGINEERING_ANALYSIS_RUN_DIR", "").strip()
        if env_run:
            resolved = self.resolve_run_dir(env_run)
            if resolved is not None:
                return resolved

        roots = (
            self.repo_root / "calibration_runs",
            self.repo_root / "pneumo_solver_ui" / "calibration_runs",
            self.repo_root / "runs",
        )
        latest: list[Path] = []
        for root in roots:
            child = _latest_child_dir(root)
            if child is not None:
                latest.append(child)
        if not latest:
            return None
        return max(latest, key=lambda item: item.stat().st_mtime).resolve()

    def _python(self) -> str:
        return str(self.python_executable or sys.executable or "python")

    def _run_command(self, command: Sequence[str], *, cwd: Path) -> tuple[int, str, str]:
        completed = subprocess.run(
            [str(item) for item in command],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        return int(completed.returncode), str(completed.stdout or ""), str(completed.stderr or "")

    def _missing_inputs_result(
        self,
        *,
        run_dir: Path | None,
        command: Sequence[str] = (),
        error: str,
    ) -> EngineeringAnalysisJobResult:
        artifacts = self.collect_artifacts(run_dir) if run_dir is not None and run_dir.exists() else ()
        return EngineeringAnalysisJobResult(
            ok=False,
            status="MISSING_INPUTS",
            command=tuple(str(item) for item in command),
            returncode=None,
            run_dir=run_dir,
            artifacts=artifacts,
            log_text="",
            error=str(error or "missing inputs"),
        )

    def _execute_job(
        self,
        *,
        run_dir: Path,
        command: Sequence[str],
    ) -> EngineeringAnalysisJobResult:
        command_tuple = tuple(str(item) for item in command)
        try:
            returncode, stdout, stderr = self._run_command(command_tuple, cwd=self.repo_root)
        except Exception as exc:
            artifacts = self.collect_artifacts(run_dir) if run_dir.exists() else ()
            return EngineeringAnalysisJobResult(
                ok=False,
                status="FAILED",
                command=command_tuple,
                returncode=None,
                run_dir=run_dir,
                artifacts=artifacts,
                log_text="",
                error=f"{type(exc).__name__}: {exc!s}",
            )

        log_text = "\n".join(part for part in (stdout, stderr) if str(part or "").strip())
        ok = int(returncode) == 0
        artifacts = self.collect_artifacts(run_dir) if run_dir.exists() else ()
        return EngineeringAnalysisJobResult(
            ok=ok,
            status="FINISHED" if ok else "FAILED",
            command=command_tuple,
            returncode=int(returncode),
            run_dir=run_dir,
            artifacts=artifacts,
            log_text=log_text,
            error="" if ok else (stderr.strip() or stdout.strip() or f"returncode={returncode}"),
        )

    def _resolve_fit_ranges_json(
        self,
        run_dir: Path,
        fit_ranges_json: Path | str | None = None,
    ) -> Path | None:
        explicit = _resolve_existing_file(fit_ranges_json)
        if explicit is not None:
            return explicit
        candidates = (
            run_dir / "param_prune" / "fit_ranges_pruned.json",
            run_dir / "fit_ranges_final.json",
            run_dir / "fit_ranges.json",
            self.repo_root / "pneumo_solver_ui" / "default_ranges.json",
        )
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        return None

    def build_system_influence_command(
        self,
        run_dir: Path | str,
        *,
        model_path: Path | str | None = None,
        base_json: Path | str | None = None,
        fit_ranges_json: Path | str | None = None,
        adaptive_eps: bool = True,
        stage_name: str = "",
        max_params: int | None = None,
    ) -> tuple[str, ...]:
        run_path = Path(run_dir).expanduser()
        command: list[str] = [
            self._python(),
            "-m",
            "pneumo_solver_ui.calibration.system_influence_report_v1",
            "--run_dir",
            str(run_path),
        ]
        for flag, value in (
            ("--model", model_path),
            ("--base_json", base_json),
            ("--fit_ranges_json", fit_ranges_json),
        ):
            if value not in (None, ""):
                command.extend([flag, str(Path(value).expanduser())])
        if adaptive_eps:
            command.append("--adaptive_eps")
        if str(stage_name or "").strip():
            command.extend(["--stage_name", str(stage_name).strip()])
        if max_params is not None:
            command.extend(["--max_params", str(int(max_params))])
        return tuple(command)

    def build_full_report_command(
        self,
        run_dir: Path | str,
        *,
        max_plots: int = 12,
    ) -> tuple[str, ...]:
        return (
            self._python(),
            "-m",
            "pneumo_solver_ui.calibration.report_full_from_run_v1",
            "--run_dir",
            str(Path(run_dir).expanduser()),
            "--max_plots",
            str(int(max_plots)),
        )

    def build_param_staging_command(
        self,
        run_dir: Path | str,
        *,
        fit_ranges_json: Path | str,
        system_influence_json: Path | str,
        oed_report_json: Path | str | None = None,
        out_dir: Path | str | None = None,
    ) -> tuple[str, ...]:
        command: list[str] = [
            self._python(),
            "-m",
            "pneumo_solver_ui.calibration.param_staging_v3_influence",
            "--fit_ranges_json",
            str(Path(fit_ranges_json).expanduser()),
            "--system_influence_json",
            str(Path(system_influence_json).expanduser()),
            "--out_dir",
            str(Path(out_dir or run_dir).expanduser()),
        ]
        if oed_report_json not in (None, ""):
            command.extend(["--oed_report_json", str(Path(oed_report_json).expanduser())])
        return tuple(command)

    def run_system_influence(
        self,
        run_dir: Path | str | None = None,
        *,
        model_path: Path | str | None = None,
        base_json: Path | str | None = None,
        fit_ranges_json: Path | str | None = None,
        adaptive_eps: bool = True,
        stage_name: str = "",
        max_params: int | None = None,
    ) -> EngineeringAnalysisJobResult:
        resolved = self.resolve_run_dir(run_dir)
        if resolved is None:
            return self._missing_inputs_result(run_dir=None, error="run_dir not found")
        command = self.build_system_influence_command(
            resolved,
            model_path=model_path,
            base_json=base_json,
            fit_ranges_json=fit_ranges_json,
            adaptive_eps=adaptive_eps,
            stage_name=stage_name,
            max_params=max_params,
        )
        return self._execute_job(run_dir=resolved, command=command)

    def run_full_report(
        self,
        run_dir: Path | str | None = None,
        *,
        max_plots: int = 12,
    ) -> EngineeringAnalysisJobResult:
        resolved = self.resolve_run_dir(run_dir)
        if resolved is None:
            return self._missing_inputs_result(run_dir=None, error="run_dir not found")
        return self._execute_job(
            run_dir=resolved,
            command=self.build_full_report_command(resolved, max_plots=max_plots),
        )

    def run_param_staging(
        self,
        run_dir: Path | str | None = None,
        *,
        fit_ranges_json: Path | str | None = None,
        oed_report_json: Path | str | None = None,
        system_influence_json: Path | str | None = None,
        out_dir: Path | str | None = None,
    ) -> EngineeringAnalysisJobResult:
        resolved = self.resolve_run_dir(run_dir)
        if resolved is None:
            return self._missing_inputs_result(run_dir=None, error="run_dir not found")

        fit_ranges_path = self._resolve_fit_ranges_json(resolved, fit_ranges_json)
        influence_path = _resolve_existing_file(system_influence_json) or _resolve_existing_file(
            resolved / "system_influence.json"
        )
        if fit_ranges_path is None or influence_path is None:
            missing = []
            if fit_ranges_path is None:
                missing.append("fit_ranges_json")
            if influence_path is None:
                missing.append("system_influence_json")
            return self._missing_inputs_result(
                run_dir=resolved,
                error="missing inputs: " + ", ".join(missing),
            )

        oed_path = (
            _resolve_existing_file(oed_report_json)
            if oed_report_json not in (None, "")
            else _resolve_existing_file(resolved / "oed_report.json")
        )
        output_dir = _resolve_existing_dir(out_dir) if out_dir not in (None, "") else resolved
        if output_dir is None:
            output_dir = resolved
        command = self.build_param_staging_command(
            resolved,
            fit_ranges_json=fit_ranges_path,
            oed_report_json=oed_path,
            system_influence_json=influence_path,
            out_dir=output_dir,
        )
        return self._execute_job(run_dir=resolved, command=command)

    def _selected_run_contract_missing_inputs(
        self,
        payload: Mapping[str, Any],
    ) -> tuple[str, ...]:
        missing: list[str] = []
        for field in REQUIRED_SELECTED_RUN_CONTRACT_FIELDS:
            if _value_missing(payload.get(field)):
                missing.append(field)

        results_index = dict(payload.get("results_artifact_index") or {})
        for field in ("run_dir", "results_csv_path", "objective_contract_path"):
            raw = payload.get(field) or results_index.get(field)
            if field == "run_dir":
                if _resolve_existing_dir(raw) is None:
                    missing.append(field)
            elif _resolve_existing_file(raw) is None:
                missing.append(field)

        if str(payload.get("analysis_handoff_ready_state") or "").strip().lower() == "blocked":
            for item in payload.get("blocking_states") or ():
                text = str(item or "").strip()
                if text:
                    missing.append(f"blocking_state:{text}")
            if not payload.get("blocking_states"):
                missing.append("analysis_handoff_ready_state")
        return tuple(dict.fromkeys(missing))

    def build_selected_run_contract_from_run_dir(
        self,
        run_dir: Path | str,
        *,
        selected_from: str = "desktop_engineering_analysis_center",
        now_text: str | None = None,
    ) -> dict[str, Any]:
        """Build the HO-007 payload with the optimizer's canonical producer helper."""

        resolved = self.resolve_run_dir(run_dir)
        if resolved is None:
            raise FileNotFoundError(f"run_dir not found: {run_dir}")

        from pneumo_solver_ui.desktop_optimizer_runtime import DesktopOptimizerRuntime

        ui_root = self.repo_root / "pneumo_solver_ui"
        if not ui_root.exists():
            ui_root = self.repo_root
        optimizer_runtime = DesktopOptimizerRuntime(
            ui_root=ui_root,
            python_executable=self._python(),
        )
        optimizer_runtime.workspace_dir = _effective_workspace_dir(self.repo_root)
        details = optimizer_runtime.selected_run_details(resolved)
        if details is None:
            raise ValueError(f"not an optimization run directory: {resolved}")
        payload = optimizer_runtime.build_selected_run_contract(
            details.summary,
            selected_from=selected_from,
            now_text=now_text,
        )
        return dict(payload)

    def discover_selected_run_candidates(
        self,
        *,
        limit: int = 25,
    ) -> tuple[dict[str, Any], ...]:
        from pneumo_solver_ui.desktop_optimizer_runtime import DesktopOptimizerRuntime
        from pneumo_solver_ui.optimization_run_history import discover_workspace_optimization_runs

        workspace = _effective_workspace_dir(self.repo_root)
        ui_root = self.repo_root / "pneumo_solver_ui"
        if not ui_root.exists():
            ui_root = self.repo_root
        optimizer_runtime = DesktopOptimizerRuntime(
            ui_root=ui_root,
            python_executable=self._python(),
        )
        optimizer_runtime.workspace_dir = workspace

        rows: list[dict[str, Any]] = []
        summaries = discover_workspace_optimization_runs(workspace)
        for summary in summaries[: max(0, int(limit or 0))]:
            payload: dict[str, Any] = {}
            missing_inputs: tuple[str, ...] = ()
            bridge_status = "UNKNOWN"
            error = ""
            try:
                payload = optimizer_runtime.build_selected_run_contract(
                    summary,
                    selected_from="desktop_engineering_analysis_center_preview",
                )
                missing_inputs = self._selected_run_contract_missing_inputs(payload)
                bridge_status = "READY" if not missing_inputs else "MISSING_INPUTS"
            except Exception as exc:
                bridge_status = "FAILED"
                error = f"{type(exc).__name__}: {exc!s}"

            rows.append(
                {
                    "run_id": str(payload.get("run_id") or summary.run_id or summary.run_dir.name),
                    "run_name": str(payload.get("run_name") or summary.run_dir.name),
                    "run_dir": str(Path(summary.run_dir).resolve()),
                    "pipeline_mode": str(summary.pipeline_mode or ""),
                    "mode": str(payload.get("mode") or ""),
                    "backend": str(summary.backend or payload.get("backend") or ""),
                    "status": str(summary.status or payload.get("status") or ""),
                    "status_label": str(summary.status_label or "").strip(),
                    "updated_ts": float(summary.updated_ts or 0.0),
                    "row_count": int(summary.row_count or 0),
                    "done_count": int(summary.done_count or 0),
                    "result_path": str(Path(summary.result_path).resolve())
                    if summary.result_path is not None
                    else "",
                    "objective_contract_hash": str(payload.get("objective_contract_hash") or ""),
                    "hard_gate_key": str(payload.get("hard_gate_key") or ""),
                    "hard_gate_tolerance": payload.get("hard_gate_tolerance"),
                    "active_baseline_hash": str(payload.get("active_baseline_hash") or ""),
                    "suite_snapshot_hash": str(payload.get("suite_snapshot_hash") or ""),
                    "analysis_handoff_ready_state": str(
                        payload.get("analysis_handoff_ready_state") or ""
                    ),
                    "bridge_status": bridge_status,
                    "missing_inputs": list(missing_inputs),
                    "blocking_states": list(payload.get("blocking_states") or ()),
                    "warnings": list(payload.get("warnings") or ()),
                    "selected_run_contract_hash": str(
                        payload.get("selected_run_contract_hash") or ""
                    ),
                    "error": error,
                }
            )
        return tuple(rows)

    def selected_run_candidate_readiness(self, *, limit: int = 25) -> dict[str, Any]:
        candidates = list(self.discover_selected_run_candidates(limit=limit))
        status_counts: dict[str, int] = {}
        missing_inputs: list[str] = []
        blocking_states: list[str] = []
        ready_run_dirs: list[str] = []
        for row in candidates:
            status = str(row.get("bridge_status") or "UNKNOWN")
            status_counts[status] = int(status_counts.get(status, 0)) + 1
            if status == "READY":
                run_dir = str(row.get("run_dir") or "").strip()
                if run_dir:
                    ready_run_dirs.append(run_dir)
            for item in row.get("missing_inputs") or ():
                text = str(item or "").strip()
                if text:
                    missing_inputs.append(text)
            for item in row.get("blocking_states") or ():
                text = str(item or "").strip()
                if text:
                    blocking_states.append(text)
        return {
            "schema": "selected_run_candidate_readiness.v1",
            "source": "workspace/opt_runs",
            "selected_run_contract_path": str(self.selected_run_contract_path()),
            "candidate_count": len(candidates),
            "ready_candidate_count": int(status_counts.get("READY", 0)),
            "missing_inputs_candidate_count": int(status_counts.get("MISSING_INPUTS", 0)),
            "failed_candidate_count": int(status_counts.get("FAILED", 0)),
            "status_counts": dict(sorted(status_counts.items())),
            "unique_missing_inputs": sorted(dict.fromkeys(missing_inputs)),
            "unique_blocking_states": sorted(dict.fromkeys(blocking_states)),
            "ready_run_dirs": ready_run_dirs[:10],
            "candidates": candidates,
        }

    def export_selected_run_contract_from_run_dir(
        self,
        run_dir: Path | str | None = None,
        *,
        target_path: Path | str | None = None,
        selected_from: str = "desktop_engineering_analysis_center",
        now_text: str | None = None,
    ) -> EngineeringAnalysisJobResult:
        resolved = self.resolve_run_dir(run_dir)
        command = (
            "export_selected_run_contract_from_run_dir",
            str(run_dir or ""),
            str(target_path or self.selected_run_contract_path()),
        )
        if resolved is None:
            return self._missing_inputs_result(
                run_dir=None,
                command=command,
                error="run_dir not found",
            )

        try:
            payload = self.build_selected_run_contract_from_run_dir(
                resolved,
                selected_from=selected_from,
                now_text=now_text,
            )
        except Exception as exc:
            return self._missing_inputs_result(
                run_dir=resolved,
                command=command,
                error=f"{type(exc).__name__}: {exc!s}",
            )

        missing = self._selected_run_contract_missing_inputs(payload)
        if missing:
            return self._missing_inputs_result(
                run_dir=resolved,
                command=command,
                error="missing inputs: " + ", ".join(missing),
            )

        target = Path(target_path).expanduser() if target_path is not None else self.selected_run_contract_path()
        try:
            target = target.resolve()
        except Exception:
            pass
        try:
            _atomic_write_json(target, payload)
        except Exception as exc:
            artifacts = self.collect_artifacts(resolved)
            return EngineeringAnalysisJobResult(
                ok=False,
                status="FAILED",
                command=command,
                returncode=None,
                run_dir=resolved,
                artifacts=artifacts,
                log_text="",
                error=f"{type(exc).__name__}: {exc!s}",
            )

        artifact = EngineeringAnalysisArtifact(
            key="selected_run_contract_json",
            title="Выбранный прогон",
            category="handoff",
            path=target,
            required=True,
            detail="Выбранный прогон подготовлен из явно указанной папки оптимизации.",
        )
        contract_hash = str(payload.get("selected_run_contract_hash") or "")
        return EngineeringAnalysisJobResult(
            ok=True,
            status="FINISHED",
            command=command,
            returncode=0,
            run_dir=resolved,
            artifacts=(artifact, *self.collect_artifacts(resolved)),
            log_text=f"selected_run_contract_path={target}\nselected_run_contract_hash={contract_hash}",
            error="",
        )

    def _artifact(
        self,
        run_dir: Path,
        rel: str,
        *,
        key: str,
        title: str,
        category: str,
        required: bool = False,
        detail: str = "",
    ) -> EngineeringAnalysisArtifact | None:
        path = (run_dir / rel).resolve()
        if not path.exists():
            return None
        return EngineeringAnalysisArtifact(
            key=key,
            title=title,
            category=category,
            path=path,
            required=bool(required),
            detail=detail,
        )

    def collect_artifacts(self, run_dir: Path) -> tuple[EngineeringAnalysisArtifact, ...]:
        items: list[EngineeringAnalysisArtifact] = []
        for rel, key, title, category, required in _ENGINEERING_ANALYSIS_ARTIFACT_SPECS:
            artifact = self._artifact(
                run_dir,
                rel,
                key=key,
                title=title,
                category=category,
                required=required,
            )
            if artifact is not None:
                items.append(artifact)

        known_paths = {str(item.path) for item in items}
        known_keys = {item.key for item in items}
        optional_recursive = (
            ("uq_sensitivity_summary.csv", "uq_sensitivity_summary_csv", "UQ sensitivity summary", "uncertainty"),
            ("measurement_priority.csv", "measurement_priority_csv", "Measurement priority table", "uncertainty"),
            ("uq_runs.csv", "uq_runs_csv", "UQ run table", "uncertainty"),
            ("uq_report.md", "uq_report_md", "UQ report", "uncertainty"),
        )
        for filename, key, title, category in optional_recursive:
            if key in known_keys:
                continue
            try:
                matches = sorted(
                    (path for path in run_dir.rglob(filename) if path.is_file()),
                    key=lambda path: (len(path.relative_to(run_dir).parts), str(path).lower()),
                )
            except Exception:
                matches = []
            if not matches:
                continue
            path = matches[0].resolve()
            known_paths.add(str(path))
            known_keys.add(key)
            items.append(
                EngineeringAnalysisArtifact(
                    key=key,
                    title=title,
                    category=category,
                    path=path,
                    detail="Найден дополнительный файл расчёта неопределённости в папке анализа.",
                )
            )
        for path in sorted(run_dir.glob("*influence*.*"), key=lambda p: p.name.lower()):
            if str(path.resolve()) in known_paths or not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in {".json", ".csv", ".md", ".png", ".svg"}:
                continue
            items.append(
                EngineeringAnalysisArtifact(
                    key="influence_artifact_" + path.stem.lower().replace("-", "_"),
                    title=path.name,
                    category="compare_influence" if "compare" in path.name.lower() else "influence",
                    path=path.resolve(),
                    detail="Найден дополнительный файл влияния в папке анализа.",
                )
            )
        return tuple(items)

    def snapshot(
        self,
        run_dir: Path | str | None = None,
        *,
        selected_contract_path: Path | str | None = None,
    ) -> EngineeringAnalysisSnapshot:
        effective_run_dir = run_dir
        effective_contract_path = selected_contract_path
        if effective_contract_path is None and run_dir is not None:
            try:
                candidate = Path(run_dir).expanduser()
                if (
                    candidate.name == SELECTED_RUN_CONTRACT_FILENAME
                    or candidate.suffix.lower() == ".json"
                ):
                    effective_contract_path = candidate
                    effective_run_dir = None
            except Exception:
                pass

        contract_snapshot = self.load_selected_run_contract(effective_contract_path)
        selected_context = contract_snapshot.selected_run_context
        if selected_context is None and contract_snapshot.status in {"MISSING", "INVALID"}:
            return EngineeringAnalysisSnapshot(
                run_dir=None,
                status="BLOCKED",
                influence_status="BLOCKED",
                calibration_status="BLOCKED",
                compare_status="BLOCKED",
                artifacts=(),
                sensitivity_rows=(),
                unit_catalog=dict(SYSTEM_INFLUENCE_UNIT_CATALOG),
                selected_run_context=None,
                selected_run_contract_path=contract_snapshot.path,
                selected_run_contract_hash=contract_snapshot.selected_run_contract_hash,
                contract_status=contract_snapshot.status,
                mismatch_summary=dict(contract_snapshot.mismatch_summary or {}),
                blocking_states=contract_snapshot.blocking_states,
            )
        selected_run_dir = selected_context.run_dir if selected_context is not None else ""
        resolved_run_dir = self.resolve_run_dir(selected_run_dir or effective_run_dir)
        if resolved_run_dir is None:
            return EngineeringAnalysisSnapshot(
                run_dir=None,
                status="BLOCKED" if contract_snapshot.status in {"MISSING", "INVALID", "BLOCKED"} else "MISSING",
                influence_status="BLOCKED" if contract_snapshot.status in {"MISSING", "INVALID", "BLOCKED"} else "MISSING",
                calibration_status="BLOCKED" if contract_snapshot.status in {"MISSING", "INVALID", "BLOCKED"} else "MISSING",
                compare_status="BLOCKED" if contract_snapshot.status in {"MISSING", "INVALID", "BLOCKED"} else "MISSING",
                artifacts=(),
                sensitivity_rows=(),
                unit_catalog=dict(SYSTEM_INFLUENCE_UNIT_CATALOG),
                selected_run_context=selected_context,
                selected_run_contract_path=contract_snapshot.path,
                selected_run_contract_hash=contract_snapshot.selected_run_contract_hash,
                contract_status=contract_snapshot.status,
                mismatch_summary=dict(contract_snapshot.mismatch_summary or {}),
                blocking_states=contract_snapshot.blocking_states,
            )

        artifacts = self.collect_artifacts(resolved_run_dir)
        artifact_keys = {artifact.key for artifact in artifacts}
        system_payload = _safe_read_json_dict(resolved_run_dir / "system_influence.json")
        sensitivity_rows = build_sensitivity_summary(system_payload)

        has_influence_core = {
            "system_influence_json",
            "system_influence_md",
            "system_influence_params_csv",
        }.issubset(artifact_keys)
        influence_status = "PASS" if has_influence_core and sensitivity_rows else "PARTIAL"
        if "system_influence_json" not in artifact_keys:
            influence_status = "MISSING"

        has_full_report = {"report_full_md", "fit_report_final_json"}.issubset(artifact_keys)
        has_detail_report = {"calibration_report_md", "fit_report_json"}.issubset(artifact_keys)
        if has_full_report or has_detail_report:
            calibration_status = "PASS"
        elif any(key in artifact_keys for key in ("report_full_md", "calibration_report_md", "fit_report_final_json", "fit_report_json")):
            calibration_status = "PARTIAL"
        else:
            calibration_status = "MISSING"

        compare_status = "PASS" if any(a.category == "compare_influence" for a in artifacts) else "MISSING"
        if influence_status == "PASS" and calibration_status in {"PASS", "PARTIAL"}:
            status = "PASS" if calibration_status == "PASS" else "PARTIAL"
        elif influence_status == "MISSING" and calibration_status == "MISSING" and compare_status == "MISSING":
            status = "MISSING"
        else:
            status = "PARTIAL"
        if contract_snapshot.status in {"MISSING", "INVALID", "BLOCKED"}:
            status = "BLOCKED"
        elif contract_snapshot.status == "DEGRADED" and status == "PASS":
            status = "DEGRADED"

        manifest_path = self.send_bundles_dir / LATEST_ENGINEERING_ANALYSIS_EVIDENCE_MANIFEST
        manifest_payload = _safe_read_json_dict(manifest_path)
        manifest_hash = str(manifest_payload.get("evidence_manifest_hash") or "")
        manifest_status = "MISSING"
        if manifest_path.exists():
            if not manifest_payload or not manifest_hash:
                manifest_status = "INVALID"
            else:
                computed_manifest_hash = _payload_hash(
                    manifest_payload,
                    hash_key="evidence_manifest_hash",
                )
                upstream = (
                    manifest_payload.get("upstream_handoff")
                    if isinstance(manifest_payload.get("upstream_handoff"), Mapping)
                    else {}
                )
                manifest_run_dir = str(manifest_payload.get("run_dir") or "").strip()
                manifest_contract_hash = str(
                    dict(upstream).get("selected_run_contract_hash") or ""
                ).strip()
                run_matches = manifest_run_dir == str(resolved_run_dir)
                hash_matches = (
                    bool(contract_snapshot.selected_run_contract_hash)
                    and manifest_contract_hash == contract_snapshot.selected_run_contract_hash
                )
                if computed_manifest_hash != manifest_hash:
                    manifest_status = "INVALID"
                elif run_matches and hash_matches:
                    manifest_status = "READY"
                else:
                    manifest_status = "STALE"

        return EngineeringAnalysisSnapshot(
            run_dir=resolved_run_dir,
            status=status,
            influence_status=influence_status,
            calibration_status=calibration_status,
            compare_status=compare_status,
            artifacts=artifacts,
            sensitivity_rows=sensitivity_rows,
            unit_catalog=dict(SYSTEM_INFLUENCE_UNIT_CATALOG),
            diagnostics_evidence_manifest_path=manifest_path.resolve() if manifest_path.exists() else None,
            diagnostics_evidence_manifest_hash=manifest_hash,
            diagnostics_evidence_manifest_status=manifest_status,
            selected_run_context=selected_context,
            selected_run_contract_path=contract_snapshot.path,
            selected_run_contract_hash=contract_snapshot.selected_run_contract_hash,
            contract_status=contract_snapshot.status,
            mismatch_summary=dict(contract_snapshot.mismatch_summary or {}),
            blocking_states=contract_snapshot.blocking_states,
        )

    def _artifact_record(self, artifact: EngineeringAnalysisArtifact) -> dict[str, Any]:
        path = artifact.path
        record: dict[str, Any] = artifact.to_payload()
        record.update(
            {
                "exists": bool(path.exists()),
                "is_dir": bool(path.is_dir()) if path.exists() else None,
            }
        )
        try:
            if path.exists() and path.is_file():
                stat = path.stat()
                record["size_bytes"] = int(stat.st_size)
                record["mtime_epoch"] = float(stat.st_mtime)
                record["sha256"] = _sha256_file(path)
            elif path.exists() and path.is_dir():
                record["child_count"] = sum(1 for _item in path.iterdir())
        except Exception as exc:
            record["sha256_error"] = str(exc)
        return record

    def _artifact_validation_status(self, record: Mapping[str, Any]) -> str:
        if not bool(record.get("exists")):
            return "MISSING"
        if bool(record.get("is_dir")):
            return "READY"
        if str(record.get("sha256") or "").strip():
            return "READY"
        if str(record.get("sha256_error") or "").strip():
            return "HASH_FAILED"
        return "UNHASHED"

    def validated_artifacts_summary(
        self,
        snapshot: EngineeringAnalysisSnapshot,
        *,
        selected_artifacts: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        selected_records = (
            [dict(item) for item in selected_artifacts]
            if selected_artifacts is not None
            else [self._artifact_record(artifact) for artifact in snapshot.artifacts]
        )
        selected_by_key = {
            str(record.get("key") or ""): dict(record)
            for record in selected_records
            if str(record.get("key") or "").strip()
        }
        spec_keys = {key for _rel, key, _title, _category, _required in _ENGINEERING_ANALYSIS_ARTIFACT_SPECS}
        expected_records: list[dict[str, Any]] = []
        missing_required: list[dict[str, Any]] = []
        required_count = 0
        ready_required_count = 0

        for rel, key, title, category, required in _ENGINEERING_ANALYSIS_ARTIFACT_SPECS:
            expected_path = (snapshot.run_dir / rel).resolve() if snapshot.run_dir is not None else Path(rel)
            record = dict(selected_by_key.get(key) or {})
            if not record:
                record = {
                    "key": key,
                    "title": title,
                    "category": category,
                    "path": str(expected_path),
                    "status": "MISSING",
                    "required": bool(required),
                    "detail": "Expected engineering analysis artifact was not found.",
                    "exists": False,
                    "is_dir": False,
                }
            record["expected_relpath"] = rel
            record["validation_status"] = self._artifact_validation_status(record)
            expected_records.append(record)

            if required:
                required_count += 1
                if record["validation_status"] == "READY":
                    ready_required_count += 1
                else:
                    missing_required.append(
                        {
                            "key": key,
                            "title": title,
                            "category": category,
                            "path": str(expected_path),
                            "validation_status": record["validation_status"],
                        }
                    )

        discovered_records: list[dict[str, Any]] = []
        for record in selected_records:
            if str(record.get("key") or "") in spec_keys:
                continue
            item = dict(record)
            item["validation_status"] = self._artifact_validation_status(item)
            discovered_records.append(item)

        status = "BLOCKED" if snapshot.run_dir is None else ("READY" if not missing_required else "MISSING")
        return {
            "schema": "engineering_analysis_validated_artifacts.v1",
            "status": status,
            "run_dir": str(snapshot.run_dir or ""),
            "required_artifact_count": required_count,
            "ready_required_artifact_count": ready_required_count,
            "missing_required_artifact_count": len(missing_required),
            "missing_required_artifacts": missing_required,
            "selected_artifact_count": len(selected_records),
            "hash_ready_artifact_count": sum(1 for item in selected_records if str(item.get("sha256") or "")),
            "expected_artifacts": expected_records,
            "discovered_artifacts": discovered_records,
        }

    def selected_run_handoff_requirements(
        self,
        snapshot: EngineeringAnalysisSnapshot,
    ) -> dict[str, Any]:
        missing_fields: list[str] = []
        mismatch = dict(snapshot.mismatch_summary or {})
        for item in mismatch.get("missing_fields") or ():
            text = str(item or "").strip()
            if text:
                missing_fields.append(text)
        if snapshot.contract_status in {"MISSING", "INVALID"} and not missing_fields:
            missing_fields = list(REQUIRED_SELECTED_RUN_CONTRACT_FIELDS)

        contract_path = snapshot.selected_run_contract_path or self.selected_run_contract_path()
        return {
            "handoff_id": SELECTED_RUN_HANDOFF_ID,
            "schema_version": "selected_run_contract_v1",
            "producer_workspace": SELECTED_RUN_PRODUCED_BY,
            "consumer_workspace": SELECTED_RUN_CONSUMED_BY,
            "required_contract_path": str(contract_path),
            "required_contract_filename": SELECTED_RUN_CONTRACT_FILENAME,
            "required_fields": list(REQUIRED_SELECTED_RUN_CONTRACT_FIELDS),
            "missing_fields": missing_fields,
            "contract_status": snapshot.contract_status,
            "blocking_states": list(snapshot.blocking_states),
            "can_run_engineering_analysis": bool(
                snapshot.contract_status == "READY"
                and snapshot.run_dir is not None
                and not snapshot.blocking_states
            ),
            "next_actions": [
                "Export a completed optimization selected-run handoff from WS-OPTIMIZATION.",
                f"Write {SELECTED_RUN_CONTRACT_FILENAME} to the required_contract_path.",
                "Refresh Engineering Analysis Center and export engineering analysis evidence again.",
            ],
        }

    def _artifact_for_keys(
        self,
        snapshot: EngineeringAnalysisSnapshot,
        keys: Sequence[str],
    ) -> EngineeringAnalysisArtifact | None:
        wanted = {str(key) for key in keys}
        for artifact in snapshot.artifacts:
            if artifact.key in wanted:
                return artifact
        return None

    def _read_static_trim_summary(self, snapshot: EngineeringAnalysisSnapshot) -> dict[str, Any]:
        def _static_metrics_from_mapping(value: Any) -> dict[str, Any]:
            found: dict[str, Any] = {}

            def _walk(item: Any) -> None:
                if len(found) >= 80:
                    return
                if isinstance(item, Mapping):
                    for raw_key, raw_value in item.items():
                        key = str(raw_key or "")
                        if key.startswith("static_trim_"):
                            found[key] = raw_value
                        if isinstance(raw_value, Mapping) or (
                            isinstance(raw_value, Sequence)
                            and not isinstance(raw_value, (str, bytes, bytearray))
                        ):
                            _walk(raw_value)
                elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
                    for child in list(item)[:20]:
                        _walk(child)

            _walk(value)
            return found

        def _status_from_metrics(metrics: Mapping[str, Any]) -> str:
            if not metrics:
                return "MISSING"
            raw_success = (
                metrics.get("static_trim_success")
                if "static_trim_success" in metrics
                else metrics.get("static_trim_pressure_trim_success")
            )
            if raw_success in (None, ""):
                return "PARTIAL"
            text = str(raw_success).strip().lower()
            return "READY" if text in {"1", "true", "yes", "ok", "pass", "passed", "success"} else "PARTIAL"

        if snapshot.run_dir is None:
            return {
                "status": "BLOCKED",
                "detail": "Статическая настройка недоступна, пока не выбран прогон.",
                "path": "",
                "metrics": {},
                "units": {},
            }

        candidates: list[Path] = []
        context = snapshot.selected_run_context
        if context is not None:
            raw_candidates = [
                context.results_csv_path,
                context.results_artifact_index.get("results_csv_path")
                if isinstance(context.results_artifact_index, Mapping)
                else "",
                context.results_artifact_index.get("results_path")
                if isinstance(context.results_artifact_index, Mapping)
                else "",
            ]
            for raw_path in raw_candidates:
                if not str(raw_path or "").strip():
                    continue
                try:
                    candidates.append(Path(str(raw_path)).expanduser().resolve())
                except Exception:
                    candidates.append(Path(str(raw_path)).expanduser())

        for artifact in snapshot.artifacts:
            if artifact.key in {
                "fit_report_final_json",
                "fit_details_final_json",
                "fit_report_json",
                "fit_details_json",
            }:
                candidates.append(artifact.path)

        seen: set[str] = set()
        for path in candidates:
            key = str(path)
            if key in seen or not path.exists() or not path.is_file():
                continue
            seen.add(key)
            metrics: dict[str, Any] = {}
            if path.suffix.lower() == ".csv":
                try:
                    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
                        reader = csv.DictReader(fh)
                        for idx, row in enumerate(reader):
                            for raw_key, raw_value in dict(row or {}).items():
                                if str(raw_key or "").startswith("static_trim_"):
                                    metrics[str(raw_key)] = raw_value
                            if metrics or idx >= 4:
                                break
                except Exception:
                    metrics = {}
            elif path.suffix.lower() == ".json":
                metrics = _static_metrics_from_mapping(_safe_read_json_dict(path))
            if metrics:
                units = {
                    key: str(SYSTEM_INFLUENCE_UNIT_CATALOG.get(key) or "")
                    for key in metrics
                    if str(SYSTEM_INFLUENCE_UNIT_CATALOG.get(key) or "")
                }
                return {
                    "status": _status_from_metrics(metrics),
                    "detail": "Поля статической настройки найдены в данных выбранного прогона.",
                    "path": str(path),
                    "metrics": dict(metrics),
                    "units": units,
                }

        return {
            "status": "MISSING",
            "detail": "Поля статической настройки не найдены в результатах и деталях подгонки.",
            "path": "",
            "metrics": {},
            "units": {},
        }

    def analysis_animator_handoff_summary(self, snapshot: EngineeringAnalysisSnapshot) -> dict[str, Any]:
        context_path = self.analysis_context_path()
        link_path = self.animator_link_contract_path()
        context_exists = context_path.exists() and context_path.is_file()
        link_exists = link_path.exists() and link_path.is_file()
        context_payload = _safe_read_json_dict(context_path)
        link_payload = _safe_read_json_dict(link_path)
        pointer = dict(
            context_payload.get("selected_result_artifact_pointer")
            or link_payload.get("selected_result_artifact_pointer")
            or {}
        )
        pointer_exists = bool(pointer.get("exists"))
        raw_pointer_path = str(pointer.get("path") or "").strip()
        if raw_pointer_path and not pointer_exists:
            try:
                pointer_exists = Path(raw_pointer_path).expanduser().exists()
            except Exception:
                pointer_exists = False

        context_hash = ""
        link_hash = ""
        try:
            context_hash = _sha256_file(context_path) if context_exists else ""
        except Exception:
            context_hash = ""
        try:
            link_hash = _sha256_file(link_path) if link_exists else ""
        except Exception:
            link_hash = ""

        handoff_hash = str(
            context_payload.get("selected_run_contract_hash")
            or link_payload.get("run_contract_hash")
            or ""
        )
        selected_hash_match = bool(
            snapshot.selected_run_contract_hash
            and handoff_hash
            and handoff_hash == snapshot.selected_run_contract_hash
        )
        if context_exists and link_exists and selected_hash_match and pointer_exists:
            status = "READY"
        elif context_exists or link_exists:
            status = "PARTIAL"
        elif snapshot.contract_status in {"MISSING", "INVALID", "BLOCKED"}:
            status = "BLOCKED"
        else:
            status = "MISSING"

        return {
            "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
            "status": status,
            "analysis_context_path": str(context_path),
            "analysis_context_exists": context_exists,
            "analysis_context_hash": context_hash,
            "animator_link_contract_path": str(link_path),
            "animator_link_contract_exists": link_exists,
            "animator_link_contract_hash": link_hash,
            "selected_artifact_pointer_status": "READY" if pointer_exists else "MISSING",
            "selected_result_artifact_pointer": pointer,
            "selected_run_contract_hash": snapshot.selected_run_contract_hash,
            "handoff_selected_run_contract_hash": handoff_hash,
            "selected_run_hash_match": selected_hash_match,
        }

    def analysis_compare_handoff_summary(self, snapshot: EngineeringAnalysisSnapshot) -> dict[str, Any]:
        compare_contract = build_analysis_compare_contract(
            snapshot.selected_run_context,
            None,
            unit_profile=snapshot.unit_catalog,
        )
        ready_state = str(compare_contract.get("analysis_compare_ready_state") or "blocked")
        blocking_states = [str(item) for item in (compare_contract.get("blocking_states") or ()) if str(item)]
        warnings = [str(item) for item in (compare_contract.get("warnings") or ()) if str(item)]
        try:
            compare_surfaces = self.compare_influence_surfaces(snapshot, top_k=5)
            compare_surface_error = ""
        except Exception as exc:
            compare_surfaces = ()
            compare_surface_error = f"{type(exc).__name__}: {exc!s}"
        context = snapshot.selected_run_context
        if snapshot.contract_status in {"MISSING", "INVALID", "BLOCKED"} or context is None:
            status = "BLOCKED"
        elif ready_state == "blocked":
            status = "BLOCKED"
        elif ready_state == "warning":
            status = "PARTIAL"
        else:
            status = "READY"
        return {
            "schema": "engineering_analysis_compare_handoff_summary.v1",
            "status": status,
            "producer_workspace": ANALYSIS_WORKSPACE_ID,
            "consumer_workspace": "WS-COMPARE",
            "consumer_surface": "Compare Viewer",
            "analysis_compare_ready_state": ready_state,
            "blocking_states": blocking_states,
            "warnings": warnings,
            "mismatch_banner": dict(compare_contract.get("mismatch_banner") or {}),
            "selected_run_contract_hash": snapshot.selected_run_contract_hash,
            "run_id": context.run_id if context else "",
            "run_dir": str(snapshot.run_dir or ""),
            "results_source_kind": str(compare_contract.get("results_source_kind") or "selected_run_contract"),
            "selected_results_ref": context.results_csv_path if context else "",
            "selected_artifact_dir": context.artifact_dir if context else "",
            "objective_contract_hash": context.objective_contract_hash if context else "",
            "hard_gate_key": context.hard_gate_key if context else "",
            "active_baseline_hash": context.active_baseline_hash if context else "",
            "suite_snapshot_hash": context.suite_snapshot_hash if context else "",
            "compare_surface_count": len(compare_surfaces),
            "compare_surface_titles": [str(surface.get("title") or "") for surface in compare_surfaces],
            "compare_surface_error": compare_surface_error,
            "analysis_compare_contract": compare_contract,
            "boundary": (
                "Analysis exposes public compare contract readiness and compare-influence previews; "
                "Compare Viewer remains the executor for comparison workflows."
            ),
            "rules": [
                "Do not mutate Compare Viewer internals from WS-ANALYSIS.",
                "Do not treat analysis previews as Compare Viewer execution evidence.",
            ],
        }

    def analysis_results_boundary_summary(self, snapshot: EngineeringAnalysisSnapshot) -> dict[str, Any]:
        context = snapshot.selected_run_context
        results_path = ""
        artifact_dir = ""
        result_exists = False
        artifact_dir_exists = False
        if context is not None:
            results_path = str(context.results_csv_path or "")
            artifact_dir = str(context.artifact_dir or context.run_dir or "")
            if results_path:
                try:
                    result_exists = Path(results_path).expanduser().exists()
                except Exception:
                    result_exists = False
            if artifact_dir:
                try:
                    artifact_dir_exists = Path(artifact_dir).expanduser().exists()
                except Exception:
                    artifact_dir_exists = False
        if snapshot.contract_status in {"MISSING", "INVALID", "BLOCKED"} or context is None:
            status = "BLOCKED"
        elif results_path and not result_exists:
            status = "PARTIAL"
        elif not results_path and not artifact_dir_exists:
            status = "PARTIAL"
        else:
            status = "READY"
        return {
            "schema": "engineering_analysis_results_boundary_summary.v1",
            "status": status,
            "producer_surface": "Results Center",
            "consumer_workspace": ANALYSIS_WORKSPACE_ID,
            "run_id": context.run_id if context else "",
            "run_dir": str(snapshot.run_dir or ""),
            "selected_run_contract_hash": snapshot.selected_run_contract_hash,
            "objective_contract_hash": context.objective_contract_hash if context else "",
            "results_csv_path": results_path,
            "results_ref_exists": result_exists,
            "artifact_dir": artifact_dir,
            "artifact_dir_exists": artifact_dir_exists,
            "contract_status": snapshot.contract_status,
            "boundary": (
                "Analysis consumes selected-run and result artifact references; "
                "Results Center remains the owner of results production and full results workflows."
            ),
            "rules": [
                "Do not mutate optimizer/results producer internals from WS-ANALYSIS.",
                "Do not treat analysis previews as Results Center acceptance evidence.",
            ],
        }

    def _artifact_source_relpath(
        self,
        artifact: EngineeringAnalysisArtifact,
        snapshot: EngineeringAnalysisSnapshot,
    ) -> str:
        if snapshot.run_dir is None:
            return ""
        try:
            return str(artifact.path.resolve().relative_to(snapshot.run_dir))
        except Exception:
            return ""

    def _csv_artifact_preview(
        self,
        artifact: EngineeringAnalysisArtifact,
        snapshot: EngineeringAnalysisSnapshot,
        *,
        max_rows: int,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": artifact.key,
            "title": artifact.title,
            "category": artifact.category,
            "source_path": str(artifact.path),
            "source_relpath": self._artifact_source_relpath(artifact, snapshot),
            "status": "MISSING",
            "columns": [],
            "row_sample": [],
            "sample_row_count": 0,
        }
        if not artifact.path.exists() or not artifact.path.is_file():
            return payload
        try:
            with artifact.path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
                reader = csv.DictReader(handle)
                columns = [str(item or "") for item in (reader.fieldnames or [])]
                rows: list[dict[str, Any]] = []
                for idx, row in enumerate(reader):
                    if idx >= max_rows:
                        break
                    rows.append({str(key or ""): value for key, value in dict(row).items()})
            payload.update(
                {
                    "status": "READY" if columns else "EMPTY",
                    "columns": columns,
                    "row_sample": rows,
                    "sample_row_count": len(rows),
                }
            )
        except Exception as exc:
            payload.update(
                {
                    "status": "INVALID",
                    "error": f"{type(exc).__name__}: {exc!s}",
                }
            )
        return payload

    def analysis_workspace_chart_table_preview(
        self,
        snapshot: EngineeringAnalysisSnapshot,
        *,
        max_rows: int = 5,
    ) -> dict[str, Any]:
        max_rows = max(1, int(max_rows or 5))
        charts: list[dict[str, Any]] = []
        preview_warnings: list[str] = []
        try:
            compare_surfaces = self.compare_influence_surfaces(snapshot, top_k=max_rows)
        except Exception as exc:
            compare_surfaces = ()
            preview_warnings.append(f"compare influence preview failed: {type(exc).__name__}: {exc!s}")
        for surface in compare_surfaces:
            axes = dict(surface.get("axes") or {})
            charts.append(
                {
                    "kind": "compare_influence_surface",
                    "status": "READY",
                    "title": str(surface.get("title") or "compare_influence"),
                    "source_path": str(surface.get("source") or ""),
                    "feature_count": len(axes.get("features") or ()),
                    "target_count": len(axes.get("targets") or ()),
                    "axes": axes,
                    "diagnostics": dict(surface.get("diagnostics") or {}),
                    "top_cells": list(surface.get("top_cells") or [])[:max_rows],
                }
            )

        sensitivity_rows = [row.to_payload() for row in snapshot.sensitivity_rows[:max_rows]]
        sensitivity_table = {
            "kind": "sensitivity_table",
            "status": "READY" if snapshot.sensitivity_rows else "MISSING",
            "source": "system_influence.json",
            "row_count": len(snapshot.sensitivity_rows),
            "columns": [
                "param",
                "group",
                "score",
                "status",
                "strongest_metric",
                "strongest_elasticity",
                "eps_rel_used",
            ],
            "units": {
                "score": str(snapshot.unit_catalog.get("score") or ""),
                "strongest_elasticity": "dimensionless",
                "eps_rel_used": str(snapshot.unit_catalog.get("eps_rel_used") or ""),
            },
            "rows": sensitivity_rows,
        }

        tables = [
            self._csv_artifact_preview(artifact, snapshot, max_rows=max_rows)
            for artifact in snapshot.artifacts
            if artifact.path.suffix.lower() == ".csv"
        ]
        status = "READY" if charts or sensitivity_rows or tables else "MISSING"
        return {
            "schema": "engineering_analysis_chart_table_preview.v1",
            "status": status,
            "max_rows": max_rows,
            "chart_count": len(charts),
            "table_count": len(tables),
            "warnings": preview_warnings,
            "charts": charts,
            "sensitivity_table": sensitivity_table,
            "tables": tables,
            "boundary": (
                "These are traceable previews from WS-ANALYSIS artifacts; Compare Viewer and Results Center "
                "remain authoritative for full comparison and results workflows."
            ),
        }

    def analysis_workspace_pipeline_status(
        self,
        snapshot: EngineeringAnalysisSnapshot,
    ) -> tuple[EngineeringAnalysisPipelineRow, ...]:
        rows: list[EngineeringAnalysisPipelineRow] = []

        context = snapshot.selected_run_context
        selected_status = "READY"
        if snapshot.contract_status == "DEGRADED":
            selected_status = "PARTIAL"
        elif snapshot.contract_status in {"MISSING", "INVALID", "BLOCKED"} or snapshot.run_dir is None:
            selected_status = "BLOCKED"
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="selected_run_context",
                section="selected_run",
                title="Выбранный прогон для анализа",
                status=selected_status,
                detail="Выбранный прогон из оптимизатора принят как источник инженерного анализа.",
                path=snapshot.selected_run_contract_path,
                metrics={
                    "handoff_id": SELECTED_RUN_HANDOFF_ID,
                    "run_id": context.run_id if context else "",
                    "objective_contract_hash": context.objective_contract_hash if context else "",
                    "hard_gate_key": context.hard_gate_key if context else "",
                    "hard_gate_tolerance": context.hard_gate_tolerance if context else "",
                    "active_baseline_hash": context.active_baseline_hash if context else "",
                    "suite_snapshot_hash": context.suite_snapshot_hash if context else "",
                    "selected_run_contract_hash": snapshot.selected_run_contract_hash,
                    "contract_status": snapshot.contract_status,
                    "run_dir": str(snapshot.run_dir or ""),
                },
                source="файл выбранного прогона из оптимизатора",
            )
        )

        autopilot = self._artifact_for_keys(
            snapshot,
            ("autopilot_v20_wrapper_json", "autopilot_v19_wrapper_json"),
        )
        autopilot_script = self.repo_root / "pneumo_solver_ui" / "calibration" / "pipeline_npz_autopilot_v20.py"
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="calibration_autopilot_v20",
                section="calibration",
                title="Калибровочный запуск",
                status="READY" if autopilot is not None else "AVAILABLE_NOT_RUN",
                detail=(
                    "Найдены данные калибровочного запуска."
                    if autopilot is not None
                    else "Калибровочный модуль доступен; эта проверка не запускает тяжёлый расчёт."
                ),
                path=autopilot.path if autopilot is not None else autopilot_script,
                source="калибровочный модуль",
            )
        )

        fit_report = self._artifact_for_keys(
            snapshot,
            ("report_full_md", "fit_report_final_json", "calibration_report_md", "fit_report_json"),
        )
        fit_ready = {"report_full_md", "fit_report_final_json"}.issubset(
            {artifact.key for artifact in snapshot.artifacts}
        )
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="calibration_fit_reports",
                section="calibration",
                title="Отчёты калибровки",
                status="READY" if fit_ready else ("PARTIAL" if fit_report is not None else "MISSING"),
                detail="Полные и итоговые отчёты калибровки из выбранного прогона.",
                path=fit_report.path if fit_report is not None else None,
                source="отчёты выбранного прогона",
            )
        )

        static_trim = self._read_static_trim_summary(snapshot)
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="calibration_static_trim",
                section="calibration",
                title="Статическая настройка",
                status=str(static_trim.get("status") or "MISSING"),
                detail=str(static_trim.get("detail") or ""),
                path=Path(str(static_trim.get("path"))) if str(static_trim.get("path") or "") else None,
                units=dict(static_trim.get("units") or {}),
                metrics=dict(static_trim.get("metrics") or {}),
                source="результаты и детали подгонки выбранного прогона",
            )
        )

        system_influence = self._artifact_for_keys(snapshot, ("system_influence_json",))
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="influence_system",
                section="influence",
                title="Влияние системы",
                status=(
                    "READY"
                    if snapshot.influence_status == "PASS"
                    else ("PARTIAL" if system_influence is not None else "MISSING")
                ),
                detail="Данные влияния системы и строки чувствительности из выбранного прогона.",
                path=system_influence.path if system_influence is not None else None,
                metrics={"sensitivity_row_count": len(snapshot.sensitivity_rows)},
                source="отчёт влияния системы",
            )
        )

        staging_artifacts = [
            artifact
            for artifact in snapshot.artifacts
            if artifact.key in {"param_staging_influence_md", "stages_influence_json"}
        ]
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="influence_staging",
                section="influence",
                title="Подбор шагов по влиянию",
                status=(
                    "READY"
                    if len(staging_artifacts) >= 2
                    else ("PARTIAL" if staging_artifacts else ("AVAILABLE_NOT_RUN" if system_influence else "MISSING"))
                ),
                detail="Шаги подбора параметров строятся по данным влияния после запуска расчёта.",
                path=staging_artifacts[0].path if staging_artifacts else None,
                metrics={"artifact_count": len(staging_artifacts)},
                source="подбор параметров по влиянию",
            )
        )

        compare_artifacts = [
            artifact
            for artifact in snapshot.artifacts
            if artifact.path.suffix.lower() == ".json"
            and (artifact.category == "compare_influence" or "compare_influence" in artifact.key)
        ]
        try:
            compare_surfaces = self.compare_influence_surfaces(snapshot, top_k=5)
            compare_surface_error = ""
        except Exception as exc:
            compare_surfaces = ()
            compare_surface_error = f"{type(exc).__name__}: {exc!s}"
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="influence_compare_surfaces",
                section="influence",
                title="Поверхности сравнения влияния",
                status=(
                    "READY"
                    if compare_surfaces
                    else ("PARTIAL" if compare_artifacts else "MISSING")
                ),
                detail=compare_surface_error or "Поверхности влияния разобраны по осям, единицам измерения и признакам качества данных.",
                path=compare_artifacts[0].path if compare_artifacts else None,
                metrics={
                    "artifact_count": len(compare_artifacts),
                    "surface_count": len(compare_surfaces),
                    "titles": [str(surface.get("title") or "") for surface in compare_surfaces],
                },
                source="поверхности сравнения влияния",
            )
        )

        rows.append(
            EngineeringAnalysisPipelineRow(
                key="sensitivity_summary",
                section="sensitivity_uncertainty",
                title="Сводка чувствительности",
                status="READY" if snapshot.sensitivity_rows else "MISSING",
                detail="Упорядоченные строки чувствительности из данных влияния системы.",
                path=system_influence.path if system_influence is not None else None,
                units={
                    "score": str(snapshot.unit_catalog.get("score") or ""),
                    "eps_rel_used": str(snapshot.unit_catalog.get("eps_rel_used") or ""),
                },
                metrics={"row_count": len(snapshot.sensitivity_rows)},
                source="сводка чувствительности",
            )
        )

        uq_artifacts = [
            artifact
            for artifact in snapshot.artifacts
            if artifact.key in {
                "uq_sensitivity_summary_csv",
                "measurement_priority_csv",
                "uq_runs_csv",
                "uq_report_md",
            }
        ]
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="uncertainty_uq",
                section="sensitivity_uncertainty",
                title="Неопределённость и приоритет измерений",
                status=(
                    "READY"
                    if len(uq_artifacts) >= 2
                    else ("PARTIAL" if uq_artifacts else "AVAILABLE_NOT_RUN")
                ),
                detail="Дополнительные расчёты неопределённости только проверяются; этот проход их не запускает.",
                path=uq_artifacts[0].path if uq_artifacts else None,
                metrics={
                    "artifact_count": len(uq_artifacts),
                    "artifact_keys": [artifact.key for artifact in uq_artifacts],
                },
                source="расчёты неопределённости",
            )
        )

        compare_handoff_summary = self.analysis_compare_handoff_summary(snapshot)
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="handoff_compare_viewer_boundary",
                section="handoffs_evidence",
                title="Связь с окном сравнения",
                status=str(compare_handoff_summary.get("status") or "BLOCKED"),
                detail=(
                    "Анализ проверяет готовность данных для окна сравнения; "
                    "само сравнение выполняется в отдельном окне."
                ),
                path=snapshot.selected_run_contract_path,
                metrics=compare_handoff_summary,
                source="данные для окна сравнения",
            )
        )

        results_boundary_summary = self.analysis_results_boundary_summary(snapshot)
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="boundary_results_center",
                section="handoffs_evidence",
                title="Связь с центром результатов",
                status=str(results_boundary_summary.get("status") or "BLOCKED"),
                detail=(
                    "Анализ использует выбранный прогон и ссылки на результаты; "
                    "подготовка результатов остаётся в центре результатов."
                ),
                path=Path(str(results_boundary_summary.get("results_csv_path") or ""))
                if str(results_boundary_summary.get("results_csv_path") or "").strip()
                else snapshot.selected_run_contract_path,
                metrics=results_boundary_summary,
                source="ссылки на результаты выбранного прогона",
            )
        )

        animator_summary = self.analysis_animator_handoff_summary(snapshot)
        rows.append(
            EngineeringAnalysisPipelineRow(
                key="handoff_ho008_animator",
                section="handoffs_evidence",
                title="Данные для аниматора",
                status=str(animator_summary.get("status") or "MISSING"),
                detail="Проверка готовности данных анализа для открытия аниматора.",
                path=self.analysis_context_path(),
                metrics=animator_summary,
                source="данные анализа для аниматора",
            )
        )

        rows.append(
            EngineeringAnalysisPipelineRow(
                key="handoff_ho009_diagnostics",
                section="handoffs_evidence",
                title="Материалы проверки и отправки",
                status=snapshot.diagnostics_evidence_manifest_status,
                detail="Актуальность материалов инженерного анализа для проверки проекта и отправки.",
                path=snapshot.diagnostics_evidence_manifest_path or (
                    self.send_bundles_dir / LATEST_ENGINEERING_ANALYSIS_EVIDENCE_MANIFEST
                ),
                metrics={
                    "handoff_id": ENGINEERING_ANALYSIS_HANDOFF_ID,
                    "manifest_hash": snapshot.diagnostics_evidence_manifest_hash,
                    "run_dir": str(snapshot.run_dir or ""),
                    "selected_run_contract_hash": snapshot.selected_run_contract_hash,
                },
                source="последние материалы инженерного анализа",
            )
        )

        return tuple(rows)

    def analysis_workspace_runtime_gaps(
        self,
        snapshot: EngineeringAnalysisSnapshot,
    ) -> tuple[dict[str, Any], ...]:
        gap_statuses = {"MISSING", "BLOCKED", "PARTIAL", "AVAILABLE_NOT_RUN", "INVALID", "STALE"}
        gaps: list[dict[str, Any]] = []
        for row in self.analysis_workspace_pipeline_status(snapshot):
            if row.status in gap_statuses:
                gaps.append(
                    {
                        "key": row.key,
                        "section": row.section,
                        "title": row.title,
                        "status": row.status,
                        "detail": row.detail,
                        "path": str(row.path or ""),
                    }
                )
        return tuple(gaps)

    def _result_artifact_pointer(self, raw_path: Path | str | None) -> dict[str, Any]:
        text = str(raw_path or "").strip()
        pointer: dict[str, Any] = {
            "path": text,
            "exists": False,
            "kind": "",
            "sha256": "",
            "size_bytes": 0,
        }
        if not text:
            return pointer
        try:
            path = Path(text).expanduser().resolve()
        except Exception:
            path = Path(text).expanduser()
        pointer["path"] = str(path)
        pointer["kind"] = path.suffix.lower().lstrip(".") or path.name
        if not path.exists() or not path.is_file():
            return pointer
        pointer["exists"] = True
        try:
            pointer["sha256"] = _sha256_file(path)
            pointer["size_bytes"] = int(path.stat().st_size)
        except Exception as exc:
            pointer["sha256_error"] = str(exc)
        return pointer

    def _compare_influence_surface_from_artifact(
        self,
        artifact: EngineeringAnalysisArtifact,
        *,
        top_k: int = 20,
    ) -> dict[str, Any] | None:
        payload = _safe_read_json_dict(artifact.path)
        if not payload:
            return None
        if str(payload.get("surface_type") or "") == "compare_influence" and isinstance(
            payload.get("diagnostics"),
            Mapping,
        ):
            surface = dict(payload)
            surface.setdefault("source", str(artifact.path))
            return surface

        corr = _first_payload_value(
            payload,
            "corr",
            "correlation",
            "correlation_matrix",
            "corr_matrix",
            "matrix",
        )
        feature_names = _axis_names(
            _first_payload_value(payload, "feature_names", "features", "params", "parameters")
        )
        target_names = _axis_names(_first_payload_value(payload, "target_names", "targets", "metrics", "signals"))
        if corr is None or not feature_names or not target_names:
            return None

        feature_units = _unit_map(
            _first_payload_value(payload, "feature_units", "param_units", "parameter_units")
        )
        target_units = _unit_map(_first_payload_value(payload, "target_units", "metric_units", "signal_units"))
        unit_profile = _unit_map(_first_payload_value(payload, "unit_profile", "units"))
        for name in feature_names:
            if name in unit_profile and name not in feature_units:
                feature_units[name] = unit_profile[name]
        for name in target_names:
            if name in unit_profile and name not in target_units:
                target_units[name] = unit_profile[name]

        return build_compare_influence_surface(
            corr,
            feature_names,
            target_names,
            title=str(payload.get("title") or artifact.title or "Compare influence surface"),
            feature_units=feature_units,
            target_units=target_units,
            top_k=top_k,
            source=str(artifact.path),
        )

    def compare_influence_surfaces(
        self,
        snapshot: EngineeringAnalysisSnapshot,
        *,
        top_k: int = 20,
    ) -> tuple[dict[str, Any], ...]:
        surfaces: list[dict[str, Any]] = []
        seen: set[str] = set()
        for artifact in snapshot.artifacts:
            if artifact.category != "compare_influence" and "compare_influence" not in artifact.key:
                continue
            if artifact.path.suffix.lower() != ".json":
                continue
            key = str(artifact.path)
            if key in seen:
                continue
            seen.add(key)
            surface = self._compare_influence_surface_from_artifact(artifact, top_k=top_k)
            if surface is not None:
                surfaces.append(surface)
        return tuple(surfaces)

    def compare_influence_surface_for_artifact(
        self,
        artifact: EngineeringAnalysisArtifact,
        *,
        top_k: int = 20,
    ) -> dict[str, Any] | None:
        return self._compare_influence_surface_from_artifact(artifact, top_k=top_k)

    def build_analysis_to_animator_link_contract(
        self,
        snapshot: EngineeringAnalysisSnapshot,
        *,
        selected_result_artifact_pointer: Path | str | None,
        selected_test_id: str = "",
        selected_segment_id: str = "",
        selected_time_window: Mapping[str, Any] | None = None,
        selected_best_candidate_ref: str = "",
        compare_contract: Mapping[str, Any] | None = None,
        now_text: str | None = None,
    ) -> dict[str, Any]:
        blocking: list[str] = []
        if snapshot.contract_status in {"MISSING", "INVALID", "BLOCKED"}:
            blocking.append(f"selected run contract {snapshot.contract_status.lower()}")
        pointer = self._result_artifact_pointer(selected_result_artifact_pointer)
        return build_analysis_to_animator_link_contract(
            snapshot.selected_run_context,
            selected_result_artifact_pointer=pointer,
            selected_test_id=selected_test_id,
            selected_segment_id=selected_segment_id,
            selected_time_window=selected_time_window,
            selected_best_candidate_ref=selected_best_candidate_ref,
            compare_contract=compare_contract,
            analysis_context_path=self.analysis_context_path(),
            now_text=str(now_text or _utc_now()),
            extra_blocking_states=blocking,
        )

    def export_analysis_to_animator_link_contract(
        self,
        snapshot: EngineeringAnalysisSnapshot,
        *,
        selected_result_artifact_pointer: Path | str | None,
        selected_test_id: str = "",
        selected_segment_id: str = "",
        selected_time_window: Mapping[str, Any] | None = None,
        selected_best_candidate_ref: str = "",
        compare_contract: Mapping[str, Any] | None = None,
        now_text: str | None = None,
    ) -> dict[str, Any]:
        link_payload = self.build_analysis_to_animator_link_contract(
            snapshot,
            selected_result_artifact_pointer=selected_result_artifact_pointer,
            selected_test_id=selected_test_id,
            selected_segment_id=selected_segment_id,
            selected_time_window=selected_time_window,
            selected_best_candidate_ref=selected_best_candidate_ref,
            compare_contract=compare_contract,
            now_text=now_text,
        )
        if str(link_payload.get("ready_state") or "") == "blocked":
            raise RuntimeError(
                "Analysis-to-Animator handoff blocked: "
                + ", ".join(str(item) for item in (link_payload.get("blocking_states") or ()))
            )

        handoff_dir = self.analysis_handoff_dir()
        handoff_dir.mkdir(parents=True, exist_ok=True)
        context_path = self.analysis_context_path()
        link_path = self.animator_link_contract_path()
        _atomic_write_json(link_path, link_payload)

        context_payload: dict[str, Any] = {
            "schema": "analysis_context.v1",
            "handoff_id": ANALYSIS_TO_ANIMATOR_HANDOFF_ID,
            "producer_workspace": ANALYSIS_WORKSPACE_ID,
            "consumer_workspace": ANIMATOR_WORKSPACE_ID,
            "created_at_utc": str(link_payload.get("created_at_utc") or now_text or _utc_now()),
            "analysis_context_path": str(context_path),
            "selected_run_contract_path": str(snapshot.selected_run_contract_path or ""),
            "selected_run_contract_hash": snapshot.selected_run_contract_hash,
            "selected_run_context": (
                snapshot.selected_run_context.to_payload()
                if snapshot.selected_run_context is not None
                else {}
            ),
            "selected_result_artifact_pointer": dict(link_payload.get("selected_result_artifact_pointer") or {}),
            "animator_link_contract_path": str(link_path),
            "animator_link_contract_hash": str(link_payload.get("animator_link_contract_hash") or ""),
            "animator_link_contract": dict(link_payload),
            "diagnostics_bundle_finalized": False,
        }
        context_payload["analysis_context_hash"] = _payload_hash(
            context_payload,
            hash_key="analysis_context_hash",
        )
        _atomic_write_json(context_path, context_payload)
        return {
            **context_payload,
            "analysis_context_path": str(context_path),
            "animator_link_contract_path": str(link_path),
        }

    def build_diagnostics_evidence_manifest(
        self,
        snapshot: EngineeringAnalysisSnapshot,
        *,
        compare_surfaces: Sequence[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        selected_artifacts = [self._artifact_record(artifact) for artifact in snapshot.artifacts]
        for item in selected_artifacts:
            item["source_run_dir"] = str(snapshot.run_dir or "")
            item["source_selected_run_contract_hash"] = snapshot.selected_run_contract_hash
            item["source_objective_contract_hash"] = (
                snapshot.selected_run_context.objective_contract_hash
                if snapshot.selected_run_context is not None
                else ""
            )
            raw_path = str(item.get("path") or "")
            relpath = ""
            if raw_path and snapshot.run_dir is not None:
                try:
                    relpath = str(Path(raw_path).resolve().relative_to(snapshot.run_dir))
                except Exception:
                    relpath = ""
            item["source_relpath"] = relpath
        report_provenance = [
            item
            for item in selected_artifacts
            if str(item.get("category") or "") in {"report", "calibration", "influence", "compare_influence"}
        ]
        compare_artifacts = [
            artifact
            for artifact in snapshot.artifacts
            if (
                artifact.path.suffix.lower() == ".json"
                and (artifact.category == "compare_influence" or "compare_influence" in artifact.key)
            )
        ]
        surface_sources = (
            compare_surfaces
            if compare_surfaces is not None
            else self.compare_influence_surfaces(snapshot)
        )
        surfaces = [dict(surface) for surface in surface_sources]
        surface_source_paths = {
            str(surface.get("source") or "").strip()
            for surface in surfaces
            if str(surface.get("source") or "").strip()
        }
        validated_artifacts = self.validated_artifacts_summary(
            snapshot,
            selected_artifacts=selected_artifacts,
        )
        unparsed_compare_artifacts = [
            str(artifact.path)
            for artifact in compare_artifacts
            if str(artifact.path) not in surface_source_paths
        ] if compare_surfaces is None else []
        validation_warnings: list[str] = []
        missing_required_artifacts = [
            str(item.get("key") or item.get("path") or "").strip()
            for item in validated_artifacts.get("missing_required_artifacts") or ()
            if str(item.get("key") or item.get("path") or "").strip()
        ]
        if missing_required_artifacts:
            validation_warnings.append(
                "Required engineering analysis artifact(s) missing or unvalidated: "
                + ", ".join(missing_required_artifacts)
            )
        if compare_surfaces is None and compare_artifacts and not surfaces:
            validation_warnings.append(
                "compare_influence artifact(s) found but no parseable compare_influence surface was exported; "
                "expected a prebuilt surface payload or corr/matrix plus feature and target axes."
            )
        elif unparsed_compare_artifacts:
            validation_warnings.append(
                f"{len(unparsed_compare_artifacts)} compare_influence artifact(s) were not parseable as surfaces."
            )
        pipeline_rows = [row.to_payload() for row in self.analysis_workspace_pipeline_status(snapshot)]
        runtime_data_gaps = [dict(item) for item in self.analysis_workspace_runtime_gaps(snapshot)]
        chart_table_preview = self.analysis_workspace_chart_table_preview(snapshot)
        compare_handoff_summary = self.analysis_compare_handoff_summary(snapshot)
        results_boundary_summary = self.analysis_results_boundary_summary(snapshot)
        payload: dict[str, Any] = {
            "schema": ENGINEERING_ANALYSIS_EVIDENCE_SCHEMA,
            "schema_version": ENGINEERING_ANALYSIS_EVIDENCE_SCHEMA_VERSION,
            "handoff_id": ENGINEERING_ANALYSIS_HANDOFF_ID,
            "produced_by": ENGINEERING_ANALYSIS_PRODUCED_BY,
            "consumed_by": ENGINEERING_ANALYSIS_CONSUMED_BY,
            "created_at": _utc_now(),
            "project_id": self.repo_root.name,
            "project_path": str(self.repo_root),
            "run_dir": str(snapshot.run_dir or ""),
            "upstream_handoff": {
                "handoff_id": SELECTED_RUN_HANDOFF_ID,
                "producer_workspace": SELECTED_RUN_PRODUCED_BY,
                "consumer_workspace": SELECTED_RUN_CONSUMED_BY,
                "selected_run_contract_path": str(snapshot.selected_run_contract_path or ""),
                "selected_run_contract_hash": snapshot.selected_run_contract_hash,
                "run_id": snapshot.selected_run_context.run_id if snapshot.selected_run_context else "",
                "run_contract_hash": (
                    snapshot.selected_run_context.run_contract_hash
                    if snapshot.selected_run_context
                    else ""
                ),
                "objective_contract_hash": (
                    snapshot.selected_run_context.objective_contract_hash
                    if snapshot.selected_run_context
                    else ""
                ),
                "hard_gate_key": (
                    snapshot.selected_run_context.hard_gate_key
                    if snapshot.selected_run_context
                    else ""
                ),
                "hard_gate_tolerance": (
                    snapshot.selected_run_context.hard_gate_tolerance
                    if snapshot.selected_run_context
                    else ""
                ),
                "active_baseline_hash": (
                    snapshot.selected_run_context.active_baseline_hash
                    if snapshot.selected_run_context
                    else ""
                ),
                "suite_snapshot_hash": (
                    snapshot.selected_run_context.suite_snapshot_hash
                    if snapshot.selected_run_context
                    else ""
                ),
                "problem_hash": snapshot.selected_run_context.problem_hash if snapshot.selected_run_context else "",
                "contract_status": snapshot.contract_status,
                "mismatch_summary": dict(snapshot.mismatch_summary or {}),
            },
            "handoff_requirements": self.selected_run_handoff_requirements(snapshot),
            "selected_run_candidate_readiness": self.selected_run_candidate_readiness(limit=25),
            "diagnostics_bundle_finalized": False,
            "validation": {
                "status": snapshot.status,
                "influence_status": snapshot.influence_status,
                "calibration_status": snapshot.calibration_status,
                "compare_status": snapshot.compare_status,
                "selected_run_contract_status": snapshot.contract_status,
                "blocking_states": list(snapshot.blocking_states),
                "warnings": validation_warnings,
            },
            "selected_artifact_list": selected_artifacts,
            "selected_tables": [
                item["key"]
                for item in selected_artifacts
                if str(item.get("path") or "").lower().endswith(".csv")
            ],
            "selected_charts": [
                str(surface.get("title") or surface.get("surface_type") or "compare_influence")
                for surface in surfaces
            ],
            "selected_filters": {
                "source": "desktop_engineering_analysis_center",
                "artifact_scope": "calibration_influence_reports",
                "categories": sorted(
                    {
                        str(item.get("category") or "")
                        for item in selected_artifacts
                        if str(item.get("category") or "")
                    }
                ),
            },
            "unit_catalog": dict(snapshot.unit_catalog),
            "validated_artifacts": validated_artifacts,
            "analysis_workspace_pipeline": pipeline_rows,
            "runtime_data_gaps": runtime_data_gaps,
            "analysis_chart_table_preview": chart_table_preview,
            "compare_viewer_handoff_summary": compare_handoff_summary,
            "results_center_boundary_summary": results_boundary_summary,
            "sensitivity_summary": [
                row.to_payload()
                for row in snapshot.sensitivity_rows
            ],
            "compare_influence_diagnostics": {
                "artifact_count": len(compare_artifacts),
                "surface_count": len(surfaces),
                "unparsed_artifacts": unparsed_compare_artifacts,
                "source": "explicit" if compare_surfaces is not None else "artifact_auto_discovery",
                "surface_titles": [str(surface.get("title") or "") for surface in surfaces],
            },
            "compare_influence_surfaces": surfaces,
            "report_provenance": report_provenance,
        }
        payload["evidence_manifest_hash"] = _sha256_text(_json_dumps_canonical(payload))
        return payload

    def write_diagnostics_evidence_manifest(
        self,
        snapshot: EngineeringAnalysisSnapshot,
        *,
        compare_surfaces: Sequence[Mapping[str, Any]] | None = None,
    ) -> Path:
        payload = self.build_diagnostics_evidence_manifest(
            snapshot,
            compare_surfaces=compare_surfaces,
        )
        workspace_path = (
            _effective_workspace_dir(self.repo_root)
            / "exports"
            / "engineering_analysis_evidence_manifest.json"
        )
        sidecar_path = self.send_bundles_dir / LATEST_ENGINEERING_ANALYSIS_EVIDENCE_MANIFEST
        _atomic_write_json(workspace_path, payload)
        _atomic_write_json(sidecar_path, payload)
        return sidecar_path.resolve()


__all__ = [
    "LATEST_ENGINEERING_ANALYSIS_EVIDENCE_MANIFEST",
    "REQUIRED_SELECTED_RUN_CONTRACT_FIELDS",
    "SELECTED_RUN_CONTRACT_ENV",
    "DesktopEngineeringAnalysisRuntime",
    "EngineeringAnalysisJobResult",
    "load_selected_run_contract",
]
