from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping

from pneumo_solver_ui.optimization_coordinator_handoff_runtime import (
    load_coordinator_handoff_payload,
)
from pneumo_solver_ui.optimization_coordinator_handoff_summary import (
    summarize_handoff_payload,
)
from pneumo_solver_ui.optimization_objective_contract import (
    metric_value_from_row,
    normalize_objective_keys,
    normalize_penalty_key,
    normalize_penalty_tol,
)


def _resolved_path_text(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        return str(Path(text).resolve())
    except Exception:
        return text


def _last_nonempty_line(text: str) -> str:
    for line in reversed(str(text or "").splitlines()):
        stripped = str(line or "").strip()
        if stripped:
            return stripped
    return ""


def _shorten(text: str, *, max_chars: int) -> str:
    clean = str(text or "").strip()
    if len(clean) <= max_chars:
        return clean
    if max_chars <= 3:
        return clean[:max_chars]
    return clean[: max_chars - 3].rstrip() + "..."


def _clean_error_text(raw: Any, *, max_chars: int) -> str:
    text = " ".join(str(raw or "").split())
    return _shorten(text, max_chars=max_chars)


def _float_or_none(raw: Any) -> float | None:
    try:
        out = float(raw)
    except Exception:
        return None
    if not math.isfinite(out):
        return None
    return float(out)


def _bool_like(raw: Any) -> bool | None:
    if isinstance(raw, bool):
        return bool(raw)
    text = str(raw or "").strip().lower()
    if not text:
        return None
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return None


def _json_mapping(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
    except Exception:
        return {}
    return dict(obj) if isinstance(obj, dict) else {}


def _json_float_list(raw: Any) -> list[float]:
    data = raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except Exception:
            return []
    if not isinstance(data, list):
        return []
    out: list[float] = []
    for item in data:
        value = _float_or_none(item)
        if value is None:
            continue
        out.append(float(value))
    return out


def _load_runtime_contract(run_dir: str) -> dict[str, Any]:
    candidate_paths = (
        Path(run_dir) / "export" / "run_scope.json",
        Path(run_dir) / "objective_contract.json",
    )
    payload: dict[str, Any] = {}
    for path in candidate_paths:
        if not path.exists():
            continue
        payload = _json_mapping(path.read_text(encoding="utf-8", errors="ignore"))
        if payload:
            break
    objective_keys = tuple(normalize_objective_keys(payload.get("objective_keys")))
    penalty_key = normalize_penalty_key(payload.get("penalty_key"))
    penalty_tol = None
    if "penalty_tol" in payload:
        penalty_tol = normalize_penalty_tol(payload.get("penalty_tol"))
    return {
        "objective_keys": objective_keys,
        "penalty_key": penalty_key,
        "penalty_tol": penalty_tol,
    }


def _objective_values_from_trial(
    objective_keys: tuple[str, ...],
    *,
    metrics: Mapping[str, Any],
    y_values: list[float],
) -> dict[str, float]:
    out: dict[str, float] = {}
    for idx, key in enumerate(objective_keys):
        value = metric_value_from_row(metrics, key, default=float("inf"))
        if not math.isfinite(value) and idx < len(y_values):
            value = float(y_values[idx])
        if math.isfinite(value):
            out[str(key)] = float(value)
    return out


def _build_handoff_provenance(
    active_launch_context: Mapping[str, Any] | None,
    *,
    current_run_dir: str,
) -> dict[str, Any]:
    context = dict(active_launch_context or {})
    if str(context.get("kind") or "").strip() != "handoff":
        return {}
    source_run_dir = _resolved_path_text(context.get("source_run_dir"))
    if not source_run_dir:
        return {}
    try:
        payload = load_coordinator_handoff_payload(source_run_dir=source_run_dir)
        summary = summarize_handoff_payload(payload, source_run_dir=Path(source_run_dir))
    except Exception:
        return {}
    target_run_dir = _resolved_path_text(summary.get("target_run_dir"))
    if target_run_dir and current_run_dir and target_run_dir != current_run_dir:
        return {}
    reason = dict(summary.get("recommendation_reason") or {})
    seed_bridge = dict(reason.get("seed_bridge") or {})
    return {
        "source_run_dir": source_run_dir,
        "source_run_name": Path(source_run_dir).name,
        "preset_tag": str(summary.get("preset_tag") or ""),
        "selection_pool": str(seed_bridge.get("selection_pool") or ""),
        "seed_count": int(seed_bridge.get("seed_count", summary.get("seed_count", 0)) or 0),
        "unique_param_candidates": int(seed_bridge.get("unique_param_candidates", 0) or 0),
        "promotable_rows": int(seed_bridge.get("promotable_rows", 0) or 0),
        "staged_rows_ok": int(seed_bridge.get("staged_rows_ok", 0) or 0),
        "pipeline_hint": str(reason.get("pipeline_hint") or ""),
        "fragment_count": int(reason.get("fragment_count", 0) or 0),
        "has_full_ring": bool(reason.get("has_full_ring", False)),
    }


def _read_trial_runtime_evidence(
    run_dir: str,
    *,
    recent_error_limit: int = 2,
    recent_error_max_chars: int = 96,
) -> tuple[dict[str, int], list[str], dict[str, Any]]:
    out = {"done": 0, "running": 0, "error": 0}
    errors: list[str] = []
    contract = _load_runtime_contract(run_dir)
    objective_keys = tuple(contract.get("objective_keys") or ())
    penalty_key = str(contract.get("penalty_key") or "").strip()
    penalty_tol_raw = contract.get("penalty_tol")
    penalty_tol = _float_or_none(penalty_tol_raw)
    feasible_best: dict[str, float] = {}
    last_infeasible: dict[str, Any] = {}
    infeasible_done = 0
    trials_csv = Path(run_dir) / "export" / "trials.csv"
    if not trials_csv.exists():
        return out, errors, {}
    try:
        with trials_csv.open("r", encoding="utf-8", errors="ignore", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                status = str((row or {}).get("status") or "").strip().upper()
                if status == "DONE":
                    out["done"] += 1
                    metrics = _json_mapping((row or {}).get("metrics_json"))
                    g_values = _json_float_list((row or {}).get("g_json"))
                    y_values = _json_float_list((row or {}).get("y_json"))
                    penalty_value = metric_value_from_row(metrics, penalty_key, default=float("inf"))
                    if not math.isfinite(penalty_value) and g_values:
                        g0 = _float_or_none(g_values[0])
                        if g0 is not None:
                            if penalty_tol is not None:
                                penalty_value = float(g0 + penalty_tol)
                            else:
                                penalty_value = float(g0)
                    feasible_flag = _bool_like(metrics.get("feasible"))
                    infeasible = False
                    if g_values:
                        infeasible = any(value > 0.0 for value in g_values)
                    elif math.isfinite(penalty_value) and penalty_tol is not None:
                        infeasible = bool(penalty_value > penalty_tol)
                    elif feasible_flag is not None:
                        infeasible = not bool(feasible_flag)

                    objective_values = _objective_values_from_trial(
                        objective_keys,
                        metrics=metrics,
                        y_values=y_values,
                    )
                    if infeasible:
                        infeasible_done += 1
                        last_infeasible = {
                            "trial_id": str((row or {}).get("trial_id") or "").strip(),
                            "penalty": penalty_value if math.isfinite(penalty_value) else None,
                            "objectives": objective_values,
                        }
                    else:
                        for key, value in objective_values.items():
                            prev = feasible_best.get(key)
                            feasible_best[key] = value if prev is None else min(prev, value)
                elif status == "RUNNING":
                    out["running"] += 1
                elif status == "ERROR":
                    out["error"] += 1
                    err = _clean_error_text(
                        (row or {}).get("error_text"),
                        max_chars=max(24, int(recent_error_max_chars or 96)),
                    )
                    if err:
                        errors.append(err)
    except Exception:
        return out, [], {}

    recent_errors: list[str] = []
    seen: set[str] = set()
    limit = max(1, int(recent_error_limit or 2))
    for err in reversed(errors):
        if err in seen:
            continue
        seen.add(err)
        recent_errors.append(err)
        if len(recent_errors) >= limit:
            break

    penalty_gate: dict[str, Any] = {}
    if infeasible_done > 0:
        objective_drift: dict[str, float] = {}
        for key in objective_keys:
            value = _float_or_none(dict(last_infeasible.get("objectives") or {}).get(key))
            best_value = _float_or_none(feasible_best.get(key))
            if value is None or best_value is None:
                continue
            drift = float(value - best_value)
            if drift > 1e-12:
                objective_drift[str(key)] = drift
        penalty_gate = {
            "infeasible_done": int(infeasible_done),
            "penalty_key": penalty_key,
            "penalty_tol": penalty_tol,
            "last_trial_id": str(last_infeasible.get("trial_id") or ""),
            "last_penalty": _float_or_none(last_infeasible.get("penalty")),
            "last_objective_values": dict(last_infeasible.get("objectives") or {}),
            "objective_drift": objective_drift,
        }

    return out, recent_errors, penalty_gate


def build_active_runtime_summary(
    job: Any,
    *,
    tail_file_text_fn: Callable[[Path], str],
    parse_done_from_log_fn: Callable[[str], int | None],
    active_launch_context: Mapping[str, Any] | None = None,
    tail_state_max_chars: int = 140,
) -> dict[str, Any]:
    if job is None:
        return {}

    proc = getattr(job, "proc", None)
    poll_fn = getattr(proc, "poll", None)
    if callable(poll_fn):
        try:
            if poll_fn() is not None:
                return {}
        except Exception:
            pass

    run_dir = _resolved_path_text(getattr(job, "run_dir", None))
    if not run_dir:
        return {}

    log_path = getattr(job, "log_path", None)
    log_text = ""
    if log_path is not None:
        try:
            log_text = str(tail_file_text_fn(Path(log_path)) or "")
        except Exception:
            log_text = ""

    done = None
    try:
        parsed_done = parse_done_from_log_fn(log_text)
        if parsed_done is not None:
            done = int(parsed_done)
    except Exception:
        done = None

    budget = int(getattr(job, "budget", 0) or 0)
    tail_state = _shorten(_last_nonempty_line(log_text), max_chars=max(16, int(tail_state_max_chars or 140)))
    trial_health, recent_errors, penalty_gate = _read_trial_runtime_evidence(run_dir)
    handoff_provenance = _build_handoff_provenance(
        active_launch_context,
        current_run_dir=run_dir,
    )

    return {
        "available": True,
        "run_dir": run_dir,
        "pipeline_mode": str(getattr(job, "pipeline_mode", "") or "").strip(),
        "backend": str(getattr(job, "backend", "") or "").strip(),
        "budget": budget,
        "done": done,
        "tail_state": tail_state,
        "trial_health": trial_health,
        "penalty_gate": penalty_gate,
        "recent_errors": recent_errors,
        "handoff_provenance": handoff_provenance,
    }


def build_run_runtime_summary(
    run_dir: Any,
    *,
    pipeline_mode: Any = "",
    backend: Any = "",
    budget: Any = 0,
    done: Any = None,
    tail_state: Any = "",
    active_launch_context: Mapping[str, Any] | None = None,
    tail_state_max_chars: int = 140,
) -> dict[str, Any]:
    resolved_run_dir = _resolved_path_text(run_dir)
    if not resolved_run_dir:
        return {}
    done_value = None
    try:
        if done is not None:
            done_value = int(done)
    except Exception:
        done_value = None
    trial_health, recent_errors, penalty_gate = _read_trial_runtime_evidence(resolved_run_dir)
    handoff_provenance = _build_handoff_provenance(
        active_launch_context,
        current_run_dir=resolved_run_dir,
    )
    return {
        "available": True,
        "run_dir": resolved_run_dir,
        "pipeline_mode": str(pipeline_mode or "").strip(),
        "backend": str(backend or "").strip(),
        "budget": int(budget or 0),
        "done": done_value,
        "tail_state": _shorten(
            _last_nonempty_line(str(tail_state or "")),
            max_chars=max(16, int(tail_state_max_chars or 140)),
        ),
        "trial_health": trial_health,
        "penalty_gate": penalty_gate,
        "recent_errors": recent_errors,
        "handoff_provenance": handoff_provenance,
    }


def active_runtime_progress_caption(
    summary: Mapping[str, Any] | None,
    *,
    prefix: str = "Active progress",
) -> str:
    payload = dict(summary or {})
    if not payload:
        return ""
    bits: list[str] = []
    done = payload.get("done")
    budget = int(payload.get("budget", 0) or 0)
    if budget > 0:
        bits.append(f"done={done if done is not None else '?'} / {budget}")
    elif done is not None:
        bits.append(f"done={done}")
    tail_state = str(payload.get("tail_state") or "").strip()
    if tail_state:
        bits.append(f"tail={tail_state}")
    if not bits:
        return ""
    return f"{prefix}: " + "; ".join(bits)


def active_runtime_trial_health_caption(
    summary: Mapping[str, Any] | None,
    *,
    prefix: str = "Trial health",
) -> str:
    payload = dict(summary or {})
    trial_health = dict(payload.get("trial_health") or {})
    if not trial_health:
        return ""
    done = int(trial_health.get("done", 0) or 0)
    running = int(trial_health.get("running", 0) or 0)
    error = int(trial_health.get("error", 0) or 0)
    if done == 0 and running == 0 and error == 0:
        return ""
    return f"{prefix}: DONE={done}, RUNNING={running}, ERROR={error}."


def active_runtime_recent_errors_caption(
    summary: Mapping[str, Any] | None,
    *,
    prefix: str = "Recent trial errors",
) -> str:
    payload = dict(summary or {})
    recent_errors = [str(item).strip() for item in list(payload.get("recent_errors") or ()) if str(item).strip()]
    if not recent_errors:
        return ""
    return f"{prefix}: " + " | ".join(recent_errors)


def active_runtime_penalty_gate_caption(
    summary: Mapping[str, Any] | None,
    *,
    prefix: str = "Penalty gate",
) -> str:
    payload = dict(summary or {})
    gate = dict(payload.get("penalty_gate") or {})
    infeasible_done = int(gate.get("infeasible_done", 0) or 0)
    if infeasible_done <= 0:
        return ""
    bits = [f"infeasible DONE={infeasible_done}"]
    penalty_key = str(gate.get("penalty_key") or "").strip()
    last_penalty = _float_or_none(gate.get("last_penalty"))
    penalty_tol = _float_or_none(gate.get("penalty_tol"))
    if penalty_key and last_penalty is not None:
        if penalty_tol is not None:
            bits.append(f"last `{penalty_key}`={last_penalty:g} > {penalty_tol:g}")
        else:
            bits.append(f"last `{penalty_key}`={last_penalty:g}")
    drift = dict(gate.get("objective_drift") or {})
    drift_bits = [
        f"{key} {float(value):+g}"
        for key, value in drift.items()
        if _float_or_none(value) is not None
    ]
    if drift_bits:
        bits.append("drift vs feasible best: " + ", ".join(drift_bits))
    else:
        last_objective_values = dict(gate.get("last_objective_values") or {})
        objective_bits = [
            f"{key}={float(value):g}"
            for key, value in last_objective_values.items()
            if _float_or_none(value) is not None
        ]
        if objective_bits:
            bits.append("last objectives: " + ", ".join(objective_bits))
    return f"{prefix}: " + "; ".join(bits) + "."


def active_handoff_provenance_caption(
    summary: Mapping[str, Any] | None,
    *,
    prefix: str = "Handoff provenance",
) -> str:
    payload = dict(summary or {})
    provenance = dict(payload.get("handoff_provenance") or {})
    if not provenance:
        return ""
    source_name = str(provenance.get("source_run_name") or "").strip()
    selection_pool = str(provenance.get("selection_pool") or "").strip() or "none"
    seed_count = int(provenance.get("seed_count", 0) or 0)
    unique_param_candidates = int(provenance.get("unique_param_candidates", 0) or 0)
    promotable_rows = int(provenance.get("promotable_rows", 0) or 0)
    staged_rows_ok = int(provenance.get("staged_rows_ok", 0) or 0)
    pipeline_hint = str(provenance.get("pipeline_hint") or "").strip() or "staged_then_manual"
    fragment_count = int(provenance.get("fragment_count", 0) or 0)
    has_full_ring = bool(provenance.get("has_full_ring", False))
    bits = []
    if source_name:
        bits.append(f"source={source_name}")
    bits.append(f"pool={selection_pool}")
    bits.append(
        f"seeds={seed_count} from {unique_param_candidates} unique / "
        f"{promotable_rows} promotable / {staged_rows_ok} valid"
    )
    bits.append(f"pipeline={pipeline_hint}")
    bits.append(f"fragments={fragment_count}")
    bits.append(f"full-ring={'yes' if has_full_ring else 'no'}")
    return f"{prefix}: " + "; ".join(bits) + "."


__all__ = [
    "active_handoff_provenance_caption",
    "build_run_runtime_summary",
    "active_runtime_penalty_gate_caption",
    "active_runtime_progress_caption",
    "active_runtime_recent_errors_caption",
    "active_runtime_trial_health_caption",
    "build_active_runtime_summary",
]
