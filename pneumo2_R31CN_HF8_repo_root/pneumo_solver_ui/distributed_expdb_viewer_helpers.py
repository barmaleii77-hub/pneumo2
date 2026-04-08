from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List

from pneumo_solver_ui.packaging_surface_ui import load_packaging_params_from_base_json

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None


def find_expdb_paths(repo_root: Path) -> List[Path]:
    candidates: list[Path] = []
    search_roots = [
        repo_root / "runs" / "dist_runs",
        repo_root / "runs_distributed",
        repo_root / "pneumo_solver_ui" / "runs_distributed",
    ]
    for base in search_roots:
        if not base.exists():
            continue
        for path in base.glob("**/experiments.*"):
            if path.suffix.lower() in {".sqlite", ".db", ".sqlite3", ".duckdb"}:
                try:
                    candidates.append(path.resolve())
                except Exception:
                    candidates.append(path)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True):
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def safe_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return float("nan")


def finite_float_or_none(value: Any) -> float | None:
    out = safe_float(value)
    return out if math.isfinite(out) else None


def resolve_existing_path(raw: Any, *, repo_root: Path, db_path: Path) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    path = Path(text)
    candidates = [path]
    if not path.is_absolute():
        candidates.extend(
            [
                repo_root / path,
                db_path.parent / path,
                db_path.parent.parent / path,
                Path.cwd() / path,
            ]
        )
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.resolve()
        except Exception:
            continue
    return None


def load_packaging_params_for_run(db: Any, run_id: str, db_path: Path, repo_root: Path) -> Dict[str, Any]:
    run = db.get_run(run_id) or {}
    spec = dict(run.get("spec") or {}) if isinstance(run.get("spec"), dict) else {}
    meta = dict(run.get("meta") or {}) if isinstance(run.get("meta"), dict) else {}
    for raw in (spec.get("base_json"), meta.get("base_json")):
        path = resolve_existing_path(raw, repo_root=repo_root, db_path=db_path)
        params = load_packaging_params_from_base_json(path)
        if params:
            return params
    return {}


def flatten_trial_rows(trials: List[Dict[str, Any]]) -> "pd.DataFrame":
    if pd is None:
        raise RuntimeError("pandas is required for distributed viewer")
    rows: List[Dict[str, Any]] = []
    for trial in trials:
        row: Dict[str, Any] = {
            "trial_id": str(trial.get("trial_id") or ""),
            "status": str(trial.get("status") or ""),
            "attempt": int(trial.get("attempt") or 0),
            "param_hash": str(trial.get("param_hash") or ""),
            "priority": int(trial.get("priority") or 0),
            "worker_tag": str(trial.get("worker_tag") or ""),
            "host": str(trial.get("host") or ""),
            "error_text": str(trial.get("error_text") or ""),
            "created_ts": trial.get("created_ts"),
            "started_ts": trial.get("started_ts"),
            "finished_ts": trial.get("finished_ts"),
            "heartbeat_ts": trial.get("heartbeat_ts"),
            "x_u": trial.get("x_u"),
            "y": trial.get("y"),
            "g": trial.get("g"),
        }
        metrics = dict(trial.get("metrics") or {}) if isinstance(trial.get("metrics"), dict) else {}
        for key, value in metrics.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                row[str(key)] = value
        rows.append(row)
    return pd.DataFrame(rows)


def done_trials_objective_rows(
    df: "pd.DataFrame",
    *,
    objective_keys: List[str],
    penalty_key: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if df is None or df.empty:
        return rows
    for row in df.to_dict(orient="records"):
        if str(row.get("status") or "") != "DONE":
            continue
        y_vals = row.get("y")
        if isinstance(y_vals, (list, tuple)) and len(y_vals) >= 2:
            obj1 = finite_float_or_none(y_vals[0])
            obj2 = finite_float_or_none(y_vals[1])
        else:
            key1 = objective_keys[0] if len(objective_keys) > 0 else ""
            key2 = objective_keys[1] if len(objective_keys) > 1 else ""
            obj1 = finite_float_or_none(row.get(key1)) if key1 else None
            obj2 = finite_float_or_none(row.get(key2)) if key2 else None
        if obj1 is None or obj2 is None:
            continue

        pen = None
        g_vals = row.get("g")
        if isinstance(g_vals, (list, tuple)) and len(g_vals) > 0:
            pen = finite_float_or_none(g_vals[0])
        if pen is None:
            pen = finite_float_or_none(row.get(penalty_key))
        if pen is None:
            pen = float("nan")

        rows.append(
            {
                "obj1": float(obj1),
                "obj2": float(obj2),
                "penalty": float(pen),
                "trial_id": str(row.get("trial_id") or ""),
            }
        )
    return rows


__all__ = [
    "done_trials_objective_rows",
    "find_expdb_paths",
    "finite_float_or_none",
    "flatten_trial_rows",
    "load_packaging_params_for_run",
    "resolve_existing_path",
    "safe_float",
]
