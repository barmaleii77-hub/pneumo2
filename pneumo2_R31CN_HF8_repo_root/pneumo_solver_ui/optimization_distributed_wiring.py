from __future__ import annotations

"""Helpers for honest UI ↔ distributed coordinator wiring.

Why this module exists:
- optimization settings are shown in more than one Streamlit surface;
- the dedicated optimization page and the main UI must write/read the same
  session_state keys;
- coordinator CLI must only receive flags that it actually understands.

This module keeps the wiring machine-checkable and testable without importing
Streamlit pages in unit tests.
"""

import importlib.util
from typing import Any, Iterable, Mapping

from .optimization_defaults import (
    DIST_OPT_BOTORCH_MAXITER_DEFAULT,
    DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT,
    DIST_OPT_BOTORCH_N_INIT_DEFAULT,
    DIST_OPT_BOTORCH_NORMALIZE_OBJECTIVES_DEFAULT,
    DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT,
    DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT,
    DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT,
    DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT,
    DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT,
    DIST_OPT_DB_ENGINE_DEFAULT,
    DIST_OPT_EXPORT_EVERY_DEFAULT,
    DIST_OPT_HV_LOG_DEFAULT,
    DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT,
    DIST_OPT_STALE_TTL_SEC_DEFAULT,
)

RAY_RUNTIME_ENV_MODES: tuple[str, ...] = ("auto", "on", "off")


def _state_get(state: Mapping[str, Any], key: str, default: Any = None) -> Any:
    try:
        return state.get(key, default)
    except Exception:
        return default


def _state_int(state: Mapping[str, Any], key: str, default: int) -> int:
    raw = _state_get(state, key, default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _state_float(state: Mapping[str, Any], key: str, default: float) -> float:
    raw = _state_get(state, key, default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _state_bool(state: Mapping[str, Any], key: str, default: bool = False) -> bool:
    raw = _state_get(state, key, default)
    if isinstance(raw, bool):
        return bool(raw)
    if isinstance(raw, (int, float)):
        return bool(raw)
    txt = str(raw).strip().lower()
    if txt in {"1", "true", "yes", "y", "on", "да"}:
        return True
    if txt in {"0", "false", "no", "n", "off", "нет", ""}:
        return False
    return bool(default)


def _state_str(state: Mapping[str, Any], key: str, default: str = "") -> str:
    raw = _state_get(state, key, default)
    return str(raw) if raw is not None else str(default)


def split_multiline_values(raw: Any) -> list[str]:
    if raw is None:
        return []
    out: list[str] = []
    for line in str(raw).replace(";", "\n").splitlines():
        val = str(line).strip()
        if val:
            out.append(val)
    return out


def detect_optional_module(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def botorch_runtime_status() -> dict[str, Any]:
    torch_ok = detect_optional_module("torch")
    botorch_ok = detect_optional_module("botorch")
    gpytorch_ok = detect_optional_module("gpytorch")
    cuda_available = False
    if torch_ok:
        try:
            import torch  # type: ignore

            cuda_available = bool(torch.cuda.is_available())
        except Exception:
            cuda_available = False
    ready = bool(torch_ok and botorch_ok and gpytorch_ok)
    return {
        "torch": bool(torch_ok),
        "botorch": bool(botorch_ok),
        "gpytorch": bool(gpytorch_ok),
        "cuda_available": bool(cuda_available),
        "ready": bool(ready),
    }


def botorch_status_markdown(status: Mapping[str, Any] | None = None) -> str:
    st = dict(status or botorch_runtime_status())
    pkg_bits = [
        f"torch={'yes' if st.get('torch') else 'no'}",
        f"botorch={'yes' if st.get('botorch') else 'no'}",
        f"gpytorch={'yes' if st.get('gpytorch') else 'no'}",
        f"cuda={'yes' if st.get('cuda_available') else 'no'}",
    ]
    if st.get("ready"):
        return "BoTorch path is available: " + ", ".join(pkg_bits)
    return "BoTorch path is NOT fully available yet: " + ", ".join(pkg_bits)


def migrated_ray_runtime_env_mode(state: Mapping[str, Any]) -> str:
    direct = _state_str(state, "ray_runtime_env_mode", "").strip().lower()
    if direct in RAY_RUNTIME_ENV_MODES:
        return direct
    legacy = _state_str(state, "ray_runtime_env", "").strip().lower()
    if legacy in RAY_RUNTIME_ENV_MODES:
        return legacy
    return DIST_OPT_RAY_RUNTIME_ENV_MODE_DEFAULT


def migrated_ray_runtime_env_json(state: Mapping[str, Any]) -> str:
    direct = _state_str(state, "ray_runtime_env_json", "")
    if direct.strip():
        return direct
    legacy = _state_str(state, "ray_runtime_env", "").strip()
    if legacy and legacy.lower() not in RAY_RUNTIME_ENV_MODES:
        return legacy
    return ""


def append_coordinator_runtime_args(
    cmd: list[str],
    state: Mapping[str, Any],
    *,
    backend_cli: str,
) -> list[str]:
    """Append supported coordinator flags based on shared session_state keys."""

    if str(backend_cli).strip().lower() == "dask":
        mode = _state_str(state, "dask_mode", "Локальный кластер (создать автоматически)")
        if mode.startswith("Подключ"):
            sched = _state_str(state, "dask_scheduler", "").strip()
            if sched:
                cmd += ["--dask-scheduler", sched]
        else:
            cmd += [
                "--dask-workers",
                str(_state_int(state, "dask_workers", 0)),
                "--dask-threads-per-worker",
                str(_state_int(state, "dask_threads_per_worker", DIST_OPT_DASK_THREADS_PER_WORKER_DEFAULT)),
            ]
            dask_memory_limit = _state_str(state, "dask_memory_limit", "").strip()
            if dask_memory_limit:
                cmd += ["--dask-memory-limit", dask_memory_limit]
            dask_dashboard_address = _state_str(state, "dask_dashboard_address", DIST_OPT_DASK_DASHBOARD_ADDRESS_DEFAULT).strip()
            cmd += ["--dask-dashboard-address", dask_dashboard_address or "none"]
    else:
        mode = _state_str(state, "ray_mode", "Локальный кластер (создать автоматически)")
        if mode.startswith("Подключ"):
            addr = _state_str(state, "ray_address", "auto").strip() or "auto"
            cmd += ["--ray-address", addr]
        else:
            cmd += [
                "--ray-address",
                "local",
                "--ray-local-num-cpus",
                str(_state_int(state, "ray_local_num_cpus", 0)),
                "--ray-local-dashboard-port",
                str(_state_int(state, "ray_local_dashboard_port", 0)),
            ]
            if _state_bool(state, "ray_local_dashboard", False):
                cmd.append("--ray-local-dashboard")

        cmd += ["--ray-runtime-env", migrated_ray_runtime_env_mode(state)]
        runtime_env_json = migrated_ray_runtime_env_json(state).strip()
        if runtime_env_json:
            cmd += ["--ray-runtime-env-json", runtime_env_json]
        for pattern in split_multiline_values(_state_str(state, "ray_runtime_exclude", "")):
            cmd += ["--ray-runtime-exclude", pattern]
        cmd += [
            "--ray-num-evaluators",
            str(_state_int(state, "ray_num_evaluators", 0)),
            "--ray-cpus-per-evaluator",
            str(_state_float(state, "ray_cpus_per_evaluator", 1.0)),
            "--ray-num-proposers",
            str(_state_int(state, "ray_num_proposers", 0)),
            "--ray-gpus-per-proposer",
            str(_state_float(state, "ray_gpus_per_proposer", 1.0)),
            "--proposer-buffer",
            str(_state_int(state, "proposer_buffer", 128)),
        ]

    db_path = _state_str(state, "opt_db_path", "").strip()
    if db_path:
        cmd += ["--db", db_path]
    db_engine = _state_str(state, "opt_db_engine", DIST_OPT_DB_ENGINE_DEFAULT).strip().lower() or DIST_OPT_DB_ENGINE_DEFAULT
    cmd += ["--db-engine", db_engine]
    if _state_bool(state, "opt_resume", False):
        cmd.append("--resume")
    explicit_run_id = _state_str(state, "opt_dist_run_id", "").strip()
    if explicit_run_id:
        cmd += ["--run-id", explicit_run_id]
    cmd += [
        "--stale-ttl-sec",
        str(_state_int(state, "opt_stale_ttl_sec", DIST_OPT_STALE_TTL_SEC_DEFAULT)),
    ]
    if _state_bool(state, "opt_hv_log", DIST_OPT_HV_LOG_DEFAULT):
        cmd.append("--hv-log")
    else:
        cmd.append("--no-hv-log")
    cmd += [
        "--export-every",
        str(_state_int(state, "opt_export_every", DIST_OPT_EXPORT_EVERY_DEFAULT)),
        "--n-init",
        str(_state_int(state, "opt_botorch_n_init", DIST_OPT_BOTORCH_N_INIT_DEFAULT)),
        "--min-feasible",
        str(_state_int(state, "opt_botorch_min_feasible", DIST_OPT_BOTORCH_MIN_FEASIBLE_DEFAULT)),
        "--botorch-num-restarts",
        str(_state_int(state, "opt_botorch_num_restarts", DIST_OPT_BOTORCH_NUM_RESTARTS_DEFAULT)),
        "--botorch-raw-samples",
        str(_state_int(state, "opt_botorch_raw_samples", DIST_OPT_BOTORCH_RAW_SAMPLES_DEFAULT)),
        "--botorch-maxiter",
        str(_state_int(state, "opt_botorch_maxiter", DIST_OPT_BOTORCH_MAXITER_DEFAULT)),
        "--botorch-ref-margin",
        str(_state_float(state, "opt_botorch_ref_margin", DIST_OPT_BOTORCH_REF_MARGIN_DEFAULT)),
    ]
    if not _state_bool(state, "opt_botorch_normalize_objectives", DIST_OPT_BOTORCH_NORMALIZE_OBJECTIVES_DEFAULT):
        cmd.append("--botorch-no-normalize-objectives")
    return cmd
