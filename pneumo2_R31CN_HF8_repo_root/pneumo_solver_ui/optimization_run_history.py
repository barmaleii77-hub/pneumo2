from __future__ import annotations

"""Helpers for honest optimization run history on the dedicated Optimization page.

Goals
-----
- sequential optimization launches must remain visible side by side;
- the page must surface *workspace truth* (run directories on disk), not only the
  single in-memory job stored in ``st.session_state``;
- the UI must distinguish between finished, partial and errored runs without
  inventing completion states;
- objective / penalty contracts must remain visible on disk so historical runs
  can be compared honestly instead of being silently reinterpreted by today's UI.
"""

from dataclasses import dataclass
from pathlib import Path
import csv
import json
from typing import Any, Dict, Optional

from pneumo_solver_ui.optimization_objective_contract import (
    normalize_objective_keys,
    objective_contract_payload,
)
from pneumo_solver_ui.optimization_baseline_source import (
    baseline_source_short_label,
    read_baseline_source_artifact,
)
from pneumo_solver_ui.optimization_problem_hash_mode import (
    problem_hash_mode_artifact_path,
    read_problem_hash_mode_artifact,
)
from pneumo_solver_ui.optimization_problem_scope import (
    problem_hash_artifact_path,
    problem_hash_short_label,
    read_problem_hash_artifact,
)
from pneumo_solver_ui.packaging_surface_helpers import collect_packaging_surface_metrics


@dataclass(frozen=True)
class OptimizationRunSummary:
    run_dir: Path
    pipeline_mode: str
    backend: str
    status: str
    status_label: str
    started_at: str
    updated_ts: float
    log_path: Optional[Path] = None
    result_path: Optional[Path] = None
    row_count: int = 0
    done_count: int = 0
    running_count: int = 0
    error_count: int = 0
    note: str = ''
    last_error: str = ''
    objective_keys: tuple[str, ...] = ()
    penalty_key: str = ''
    penalty_tol: Optional[float] = None
    objective_source: str = ''
    objective_contract_path: Optional[Path] = None
    problem_hash: str = ''
    problem_hash_path: Optional[Path] = None
    problem_hash_mode: str = ''
    problem_hash_mode_path: Optional[Path] = None
    baseline_source_kind: str = ''
    baseline_source_label: str = ''
    baseline_source_path: Optional[Path] = None


@dataclass(frozen=True)
class OptimizationRunPackagingSnapshot:
    rows_considered: int = 0
    rows_with_packaging: int = 0
    packaging_complete_rows: int = 0
    packaging_truth_ready_rows: int = 0
    packaging_verification_pass_rows: int = 0
    runtime_fallback_rows: int = 0
    spring_host_interference_rows: int = 0
    spring_pair_interference_rows: int = 0
    status_counts: tuple[tuple[str, int], ...] = ()


def _safe_json(path: Path) -> Dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        return dict(obj) if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _csv_row_count(path: Optional[Path]) -> int:
    if path is None or not path.exists():
        return 0
    try:
        with path.open('r', encoding='utf-8', errors='ignore', newline='') as fh:
            return max(0, sum(1 for _ in fh) - 1)
    except Exception:
        return 0


def _status_label(status: str) -> str:
    mapping = {
        'done': 'DONE',
        'running': 'RUNNING',
        'partial': 'PARTIAL',
        'error': 'ERROR',
        'stopped': 'STOPPED',
        'unknown': 'UNKNOWN',
    }
    return mapping.get(str(status or 'unknown').strip().lower(), 'UNKNOWN')


def _float_or_none(value: Any) -> Optional[float]:
    try:
        out = float(value)
    except Exception:
        return None
    return out if out == out else None


def _bool_like(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    num = _float_or_none(value)
    if num is not None:
        return bool(num != 0.0)
    text = str(value or '').strip().lower()
    return text in {'true', 'yes', 'y', 'on'}


def _parse_json_text(raw: Any) -> Dict[str, Any]:
    text = str(raw or '').strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
        return dict(obj) if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _iter_result_rows(result_path: Path):
    with result_path.open('r', encoding='utf-8', errors='ignore', newline='') as fh:
        reader = csv.DictReader(fh)
        for raw_row in reader:
            row = dict(raw_row or {})
            metrics_blob = _parse_json_text(row.get('metrics_json'))
            for key, value in metrics_blob.items():
                if key not in row or str(row.get(key) or '').strip() == '':
                    row[str(key)] = value
            yield row


def summarize_run_packaging_snapshot(result_path: Optional[Path]) -> OptimizationRunPackagingSnapshot:
    if result_path is None or not result_path.exists():
        return OptimizationRunPackagingSnapshot()

    rows_considered = 0
    rows_with_packaging = 0
    packaging_complete_rows = 0
    packaging_truth_ready_rows = 0
    packaging_verification_pass_rows = 0
    runtime_fallback_rows = 0
    spring_host_interference_rows = 0
    spring_pair_interference_rows = 0
    status_counts: Dict[str, int] = {}

    try:
        for row in _iter_result_rows(result_path):
            row_status = str((row or {}).get('status') or '').strip().upper()
            if row_status and row_status != 'DONE':
                continue
            rows_considered += 1

            has_packaging = any(
                key in row and str(row.get(key) or '').strip() != ''
                for key in (
                    'anim_export_packaging_status',
                    'anim_export_packaging_truth_ready',
                    'верификация_флаги',
                    'число_runtime_fallback_пружины',
                    'число_пересечений_пружина_цилиндр',
                    'число_пересечений_пружина_пружина',
                )
            )
            if not has_packaging:
                continue

            rows_with_packaging += 1
            surface = collect_packaging_surface_metrics(row)
            packaging_status = str(surface.get('packaging_статус') or '').strip() or 'n/a'
            status_counts[packaging_status] = int(status_counts.get(packaging_status, 0)) + 1

            if packaging_status == 'complete':
                packaging_complete_rows += 1
            if _bool_like(row.get('anim_export_packaging_truth_ready')):
                packaging_truth_ready_rows += 1
            if int(surface.get('pass_packaging_верификация', 0) or 0) == 1:
                packaging_verification_pass_rows += 1

            runtime_fallback = _float_or_none(row.get('число_runtime_fallback_пружины')) or 0.0
            host_hits = _float_or_none(row.get('число_пересечений_пружина_цилиндр')) or 0.0
            pair_hits = _float_or_none(row.get('число_пересечений_пружина_пружина')) or 0.0
            if runtime_fallback > 0.0:
                runtime_fallback_rows += 1
            if host_hits > 0.0:
                spring_host_interference_rows += 1
            if pair_hits > 0.0:
                spring_pair_interference_rows += 1
    except Exception:
        return OptimizationRunPackagingSnapshot()

    return OptimizationRunPackagingSnapshot(
        rows_considered=int(rows_considered),
        rows_with_packaging=int(rows_with_packaging),
        packaging_complete_rows=int(packaging_complete_rows),
        packaging_truth_ready_rows=int(packaging_truth_ready_rows),
        packaging_verification_pass_rows=int(packaging_verification_pass_rows),
        runtime_fallback_rows=int(runtime_fallback_rows),
        spring_host_interference_rows=int(spring_host_interference_rows),
        spring_pair_interference_rows=int(spring_pair_interference_rows),
        status_counts=tuple(sorted((str(key), int(value)) for key, value in status_counts.items())),
    )


def _read_objective_contract(run_dir: Path) -> tuple[Dict[str, Any], Optional[Path]]:
    contract_path = run_dir / 'objective_contract.json'
    if contract_path.exists():
        payload = _safe_json(contract_path)
        if payload:
            return payload, contract_path

    spec_path = run_dir / 'problem_spec.json'
    spec_payload = _safe_json(spec_path)
    cfg = spec_payload.get('cfg') if isinstance(spec_payload.get('cfg'), dict) else {}
    if isinstance(cfg, dict) and cfg:
        payload = objective_contract_payload(
            objective_keys=cfg.get('objective_keys'),
            penalty_key=str(cfg.get('penalty_key') or ''),
            penalty_tol=cfg.get('penalty_tol') if 'penalty_tol' in cfg else None,
            source='problem_spec_cfg_fallback',
        )
        return payload, spec_path
    return {}, None


def _objective_contract_fields(run_dir: Path) -> dict[str, Any]:
    payload, payload_path = _read_objective_contract(run_dir)
    objective_keys = normalize_objective_keys(payload.get('objective_keys'))
    penalty_key = str(payload.get('penalty_key') or '').strip()
    penalty_tol = _float_or_none(payload.get('penalty_tol')) if 'penalty_tol' in payload else None
    return {
        'objective_keys': objective_keys,
        'penalty_key': penalty_key,
        'penalty_tol': penalty_tol,
        'objective_source': str(payload.get('source') or ''),
        'objective_contract_path': payload_path,
    }


def _baseline_source_fields(run_dir: Path) -> dict[str, Any]:
    payload = read_baseline_source_artifact(run_dir)
    source_kind = str(payload.get('source_kind') or '').strip().lower()
    source_label = str(payload.get('source_label') or '').strip()
    baseline_path_raw = str(payload.get('baseline_path') or '').strip()
    baseline_path: Optional[Path] = None
    if baseline_path_raw:
        try:
            baseline_path = Path(baseline_path_raw)
        except Exception:
            baseline_path = None
    return {
        'baseline_source_kind': source_kind,
        'baseline_source_label': source_label,
        'baseline_source_path': baseline_path,
    }


def _problem_scope_fields(run_dir: Path) -> dict[str, Any]:
    problem_hash = read_problem_hash_artifact(run_dir)
    problem_hash_mode = read_problem_hash_mode_artifact(run_dir)
    return {
        'problem_hash': problem_hash,
        'problem_hash_path': problem_hash_artifact_path(run_dir) if problem_hash else None,
        'problem_hash_mode': problem_hash_mode,
        'problem_hash_mode_path': problem_hash_mode_artifact_path(run_dir) if problem_hash_mode else None,
    }


def _summarize_staged_run(run_dir: Path, *, active_run_dir: Optional[Path]) -> OptimizationRunSummary:
    sp_path = run_dir / 'sp.json'
    payload = _safe_json(sp_path)
    log_path = run_dir / 'stage_runner.log'
    result_path = run_dir / 'results_all.csv'
    if not result_path.exists():
        alt = payload.get('combined_csv')
        try:
            alt_p = Path(str(alt))
        except Exception:
            alt_p = None
        if alt_p is not None and alt_p.exists():
            result_path = alt_p
    row_count = _csv_row_count(result_path if result_path.exists() else None)
    status_raw = str(payload.get('status') or '').strip().lower()
    note = ''
    if active_run_dir is not None and Path(active_run_dir).resolve() == run_dir.resolve():
        status = 'running'
        note = 'Этот staged run активен в текущей странице.'
    elif status_raw == 'done' or (result_path.exists() and row_count > 0):
        status = 'done'
        note = f'rows={row_count}' if row_count > 0 else 'staged artifacts present'
    elif status_raw in {'fail', 'failed', 'error'}:
        status = 'error'
        note = 'staged runner reported error'
    elif (run_dir / 'STOP_OPTIMIZATION.txt').exists():
        status = 'stopped'
        note = 'STOP file present'
    elif any(run_dir.glob('s*/o*.csv')):
        status = 'partial'
        note = 'stage CSVs exist but final sp.json status is not done'
    else:
        status = 'unknown'
        note = 'no final staged status found'
    started_at = str(payload.get('ts') or '')
    try:
        updated_ts = max(
            sp_path.stat().st_mtime if sp_path.exists() else 0.0,
            result_path.stat().st_mtime if result_path.exists() else 0.0,
            log_path.stat().st_mtime if log_path.exists() else 0.0,
        )
    except Exception:
        updated_ts = 0.0
    contract = _objective_contract_fields(run_dir)
    problem_scope = _problem_scope_fields(run_dir)
    baseline_source = _baseline_source_fields(run_dir)
    return OptimizationRunSummary(
        run_dir=run_dir,
        pipeline_mode='staged',
        backend='StageRunner',
        status=status,
        status_label=_status_label(status),
        started_at=started_at,
        updated_ts=float(updated_ts),
        log_path=log_path if log_path.exists() else None,
        result_path=result_path if result_path.exists() else None,
        row_count=int(row_count),
        note=note,
        objective_keys=tuple(contract['objective_keys']),
        penalty_key=str(contract['penalty_key']),
        penalty_tol=contract['penalty_tol'],
        objective_source=str(contract['objective_source']),
        objective_contract_path=contract['objective_contract_path'],
        problem_hash=str(problem_scope['problem_hash']),
        problem_hash_path=problem_scope['problem_hash_path'],
        problem_hash_mode=str(problem_scope['problem_hash_mode']),
        problem_hash_mode_path=problem_scope['problem_hash_mode_path'],
        baseline_source_kind=str(baseline_source['baseline_source_kind']),
        baseline_source_label=str(baseline_source['baseline_source_label']),
        baseline_source_path=baseline_source['baseline_source_path'],
    )


def _summarize_coordinator_trials(trials_csv: Path) -> tuple[int, int, int, str]:
    done = 0
    running = 0
    error = 0
    last_error = ''
    try:
        with trials_csv.open('r', encoding='utf-8', errors='ignore', newline='') as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                status = str((row or {}).get('status') or '').strip().upper()
                if status == 'DONE':
                    done += 1
                elif status == 'RUNNING':
                    running += 1
                elif status == 'ERROR':
                    error += 1
                    if not last_error:
                        last_error = str((row or {}).get('error_text') or '').strip()
    except Exception:
        pass
    return done, running, error, last_error


def _summarize_coordinator_run(run_dir: Path, *, active_run_dir: Optional[Path]) -> OptimizationRunSummary:
    log_path = run_dir / 'coordinator.log'
    trials_csv = run_dir / 'export' / 'trials.csv'
    result_path = trials_csv if trials_csv.exists() else None
    done_count, running_count, error_count, last_error = _summarize_coordinator_trials(trials_csv) if trials_csv.exists() else (0, 0, 0, '')
    if active_run_dir is not None and Path(active_run_dir).resolve() == run_dir.resolve():
        status = 'running'
        note = f'done={done_count}, running={running_count}, error={error_count}'
    elif running_count > 0:
        status = 'partial'
        note = f'Coordinator left unfinished trials on disk: done={done_count}, running={running_count}, error={error_count}'
    elif done_count > 0 and error_count > 0:
        status = 'partial'
        note = f'Coordinator produced results with evaluation errors: done={done_count}, error={error_count}'
    elif done_count > 0:
        status = 'done'
        note = f'done={done_count}'
    elif error_count > 0:
        status = 'error'
        note = f'error={error_count}'
    elif (run_dir / 'STOP_OPTIMIZATION.txt').exists():
        status = 'stopped'
        note = 'STOP file present'
    else:
        status = 'unknown'
        note = 'No coordinator completion markers found'
    started_at = ''
    run_id_txt = run_dir / 'run_id.txt'
    if run_id_txt.exists():
        try:
            started_at = run_id_txt.read_text(encoding='utf-8', errors='ignore').strip()
        except Exception:
            started_at = ''
    try:
        updated_ts = max(
            log_path.stat().st_mtime if log_path.exists() else 0.0,
            trials_csv.stat().st_mtime if trials_csv.exists() else 0.0,
            (run_dir / 'progress_hv.csv').stat().st_mtime if (run_dir / 'progress_hv.csv').exists() else 0.0,
        )
    except Exception:
        updated_ts = 0.0
    contract = _objective_contract_fields(run_dir)
    problem_scope = _problem_scope_fields(run_dir)
    baseline_source = _baseline_source_fields(run_dir)
    return OptimizationRunSummary(
        run_dir=run_dir,
        pipeline_mode='coordinator',
        backend='Distributed coordinator',
        status=status,
        status_label=_status_label(status),
        started_at=started_at,
        updated_ts=float(updated_ts),
        log_path=log_path if log_path.exists() else None,
        result_path=result_path,
        row_count=_csv_row_count(result_path),
        done_count=int(done_count),
        running_count=int(running_count),
        error_count=int(error_count),
        note=note,
        last_error=last_error,
        objective_keys=tuple(contract['objective_keys']),
        penalty_key=str(contract['penalty_key']),
        penalty_tol=contract['penalty_tol'],
        objective_source=str(contract['objective_source']),
        objective_contract_path=contract['objective_contract_path'],
        problem_hash=str(problem_scope['problem_hash']),
        problem_hash_path=problem_scope['problem_hash_path'],
        problem_hash_mode=str(problem_scope['problem_hash_mode']),
        problem_hash_mode_path=problem_scope['problem_hash_mode_path'],
        baseline_source_kind=str(baseline_source['baseline_source_kind']),
        baseline_source_label=str(baseline_source['baseline_source_label']),
        baseline_source_path=baseline_source['baseline_source_path'],
    )


def summarize_optimization_run(run_dir: Path, *, active_run_dir: Optional[Path] = None) -> Optional[OptimizationRunSummary]:
    run_dir = Path(run_dir)
    if not run_dir.exists() or not run_dir.is_dir():
        return None
    name = run_dir.name.lower()
    if 'stag' in name or (run_dir / 'sp.json').exists():
        return _summarize_staged_run(run_dir, active_run_dir=active_run_dir)
    if 'coord' in name or (run_dir / 'coordinator.log').exists():
        return _summarize_coordinator_run(run_dir, active_run_dir=active_run_dir)
    return None


def discover_workspace_optimization_runs(workspace_dir: Path, *, active_run_dir: Optional[Path] = None) -> list[OptimizationRunSummary]:
    workspace_dir = Path(workspace_dir)
    root = workspace_dir / 'opt_runs'
    out: list[OptimizationRunSummary] = []
    if not root.exists():
        return out
    for mode_dir in sorted(root.iterdir()):
        if not mode_dir.is_dir():
            continue
        for run_dir in sorted(mode_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            summary = summarize_optimization_run(run_dir, active_run_dir=active_run_dir)
            if summary is not None:
                out.append(summary)
    out.sort(key=lambda item: (item.updated_ts, str(item.run_dir)), reverse=True)
    return out


def format_run_choice(summary: OptimizationRunSummary) -> str:
    suffix = ''
    if summary.pipeline_mode == 'staged' and summary.row_count > 0:
        suffix = f' · rows={summary.row_count}'
    if summary.pipeline_mode == 'coordinator':
        suffix = f' · done={summary.done_count}/run={summary.running_count}/err={summary.error_count}'
    if summary.baseline_source_kind:
        suffix += f' · base={baseline_source_short_label(summary.baseline_source_kind)}'
    return f'[{summary.status_label}] {summary.backend} · {summary.run_dir.name}{suffix}'


__all__ = [
    'OptimizationRunPackagingSnapshot',
    'OptimizationRunSummary',
    'discover_workspace_optimization_runs',
    'format_run_choice',
    'summarize_run_packaging_snapshot',
    'summarize_optimization_run',
]
