"""Run artifacts: durable pointers to latest results (simulation/optimization) + lightweight storage.

Цель модуля:
- хранить "указатели" на последние результаты (симуляция/оптимизация) на диске;
- при старте UI подхватывать эти указатели обратно в session_state, чтобы все страницы
  знали, что уже было посчитано;
- поддерживать не только summary (таблицы), но и таймсерийные NPZ-логи (osc).

Важно:
- файл-указатель хранит ТОЛЬКО пути и метаданные (без больших данных);
- схема обратнос совместима: старые pointer-файлы (_last_baseline.json/_last_opt.json)
  продолжают писаться и читаться.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

import importlib

if TYPE_CHECKING:
    import pandas as pd

from .browser_perf_artifacts import collect_browser_perf_artifacts_summary


# ----------------------- paths -----------------------


def _optional_config_workspace_dir() -> Optional[Path]:
    """Best-effort legacy config lookup, imported lazily.

    Important: when PNEUMO_WORKSPACE_DIR is already set we must not even try to
    import optional config modules, otherwise diag/bootstrap logs a fake internal
    ModuleNotFoundError noise.
    """
    try:
        mod = importlib.import_module("pneumo_solver_ui.config")
    except Exception:
        return None
    raw = getattr(mod, "WORKSPACE_DIR", None)
    if not raw:
        return None
    try:
        return Path(raw).expanduser().resolve()
    except Exception:
        try:
            return Path(str(raw))
        except Exception:
            return None


def _workspace_dir() -> Path:
    """Resolve workspace directory without noisy optional imports."""
    raw = os.environ.get("PNEUMO_WORKSPACE_DIR", "").strip()
    if raw:
        try:
            return Path(raw).expanduser().resolve()
        except Exception:
            return Path(raw)
    cfg_ws = _optional_config_workspace_dir()
    if cfg_ws is not None:
        return cfg_ws
    return (Path(__file__).resolve().parent / "workspace").resolve()


def pointers_dir() -> Path:
    """Global pointers directory (durable pointers, survives restarts)."""
    d = _workspace_dir() / "_pointers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def baseline_cache_dir() -> Path:
    """Directory for legacy baseline pointer file."""
    d = _workspace_dir() / "baseline"
    d.mkdir(parents=True, exist_ok=True)
    return d


def opt_runs_dir() -> Path:
    """Directory for legacy optimization pointer file."""
    d = _workspace_dir() / "opt"
    d.mkdir(parents=True, exist_ok=True)
    return d


def last_baseline_ptr_path() -> Path:
    # legacy location
    return baseline_cache_dir() / "_last_baseline.json"


def last_opt_ptr_path() -> Path:
    # legacy location
    return opt_runs_dir() / "_last_opt.json"


def latest_simulation_ptr_path() -> Path:
    return pointers_dir() / "latest_simulation.json"


def latest_optimization_ptr_path() -> Path:
    return pointers_dir() / "latest_optimization.json"


def latest_animation_ptr_path() -> Path:
    return pointers_dir() / "anim_latest.json"


# ----------------------- utils -----------------------


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _write_json_atomic(path: Path, data: dict) -> None:
    """Atomic-ish JSON write (write to tmp then replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _merge_meta(dst: Optional[dict], src: Optional[dict]) -> dict:
    out = dict(dst or {})
    if not isinstance(src, dict):
        return out
    for k, v in src.items():
        # prefer explicit new values, but don't drop existing
        if v is None:
            continue
        out[k] = v
    return out


def _resolve_pointer_npz(pointer_json: Path, raw_npz: Any) -> Optional[Path]:
    if not isinstance(raw_npz, str) or not raw_npz.strip():
        return None
    try:
        p = Path(raw_npz).expanduser()
    except Exception:
        return None
    if p.is_absolute():
        return p
    return (pointer_json.parent / p).resolve()


def _extract_anim_pointer_payload(
    *,
    npz_path: Optional[Path] = None,
    pointer_json: Optional[Path] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> dict:
    payload: dict = {
        "kind": "anim_latest",
        "updated_at": _utc_iso(),
        "meta": dict(meta or {}),
    }

    pointer_obj: Optional[dict] = None
    pointer_abs: Optional[Path] = None
    if pointer_json is not None:
        try:
            pointer_abs = Path(pointer_json).expanduser().resolve()
            payload["pointer_json"] = str(pointer_abs)
            pointer_obj = _read_json(pointer_abs)
        except Exception:
            pointer_abs = None
            pointer_obj = None

    if npz_path is not None:
        try:
            payload["npz_path"] = str(Path(npz_path).expanduser().resolve())
        except Exception:
            payload["npz_path"] = str(npz_path)

    if isinstance(pointer_obj, dict):
        payload["schema_version"] = pointer_obj.get("schema_version")
        payload["updated_utc"] = pointer_obj.get("updated_utc")
        payload["visual_cache_token"] = str(pointer_obj.get("visual_cache_token") or "")
        payload["visual_reload_inputs"] = list(pointer_obj.get("visual_reload_inputs") or [])
        payload["visual_cache_dependencies"] = dict(pointer_obj.get("visual_cache_dependencies") or {})
        payload["meta"] = _merge_meta(payload.get("meta"), pointer_obj.get("meta"))
        if "npz_path" not in payload:
            resolved_npz = _resolve_pointer_npz(pointer_abs, pointer_obj.get("npz_path")) if pointer_abs else None
            if resolved_npz is not None:
                payload["npz_path"] = str(resolved_npz)

    return payload


# ----------------------- pointers: animation -----------------------


def save_latest_animation_ptr(
    *,
    npz_path: Optional[Path] = None,
    pointer_json: Optional[Path] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> dict:
    """Persist global anim_latest pointer with visual reload diagnostics."""
    payload = _extract_anim_pointer_payload(npz_path=npz_path, pointer_json=pointer_json, meta=meta)
    _write_json_atomic(latest_animation_ptr_path(), payload)
    return payload


def load_latest_animation_ptr() -> Optional[dict]:
    return _read_json(latest_animation_ptr_path())




def _safe_path(value: Any) -> Optional[Path]:
    if value in (None, ""):
        return None
    try:
        return Path(str(value)).expanduser().resolve(strict=False)
    except Exception:
        try:
            return Path(str(value))
        except Exception:
            return None


def _path_exists_flag(value: Any) -> Optional[bool]:
    p = _safe_path(value)
    if p is None:
        return None
    try:
        return bool(p.exists())
    except Exception:
        return False


def _path_within_flag(value: Any, base: Path) -> Optional[bool]:
    p = _safe_path(value)
    if p is None:
        return None
    try:
        p.relative_to(base.resolve())
        return True
    except Exception:
        return False


def collect_anim_latest_diagnostics_summary(
    info: Optional[Dict[str, Any]] = None,
    *,
    include_meta: bool = False,
) -> dict:
    """Return canonical anim_latest diagnostics for registry / launcher / bundle flows.

    The summary is intentionally flat and human-readable so it can be safely stored
    in run-registry events, bundle sidecars, and launcher diagnostics without any
    alias bridges or ad-hoc field remapping.

    In addition to the pointer/token payload, the summary must expose whether the
    referenced files are actually usable from the current workspace. This lets
    send-bundle / validator surfaces distinguish between a valid current anim
    export and a stale external pointer copied into diagnostics by mistake.
    """
    src = info if isinstance(info, dict) else None
    if src is None:
        src = load_latest_animation_ptr() or load_last_baseline_ptr() or {}

    try:
        global_pointer = latest_animation_ptr_path().resolve()
    except Exception:
        global_pointer = latest_animation_ptr_path()

    pointer_json = str(src.get("pointer_json") or src.get("anim_latest_json") or "")
    npz_path = str(src.get("npz_path") or src.get("anim_latest_npz") or "")
    workspace = _workspace_dir()
    pointer_exists = _path_exists_flag(pointer_json) if pointer_json else None
    npz_exists = _path_exists_flag(npz_path) if npz_path else None
    pointer_in_workspace = _path_within_flag(pointer_json, workspace) if pointer_json else None
    npz_in_workspace = _path_within_flag(npz_path, workspace) if npz_path else None

    issues: list[str] = []
    if pointer_json and pointer_exists is False:
        issues.append(f"anim_latest pointer_json is missing on disk: {pointer_json}")
    if npz_path and npz_exists is False:
        issues.append(f"anim_latest npz_path is missing on disk: {npz_path}")
    if pointer_json and pointer_in_workspace is False:
        issues.append(f"anim_latest pointer_json is outside current workspace: {pointer_json}")
    if npz_path and npz_in_workspace is False:
        issues.append(f"anim_latest npz_path is outside current workspace: {npz_path}")

    usable = bool(pointer_json and npz_path and pointer_exists is True and npz_exists is True)

    meta_dict = dict(src.get("meta") or {}) if isinstance(src.get("meta"), dict) else {}
    artifact_refs = dict(meta_dict.get("anim_export_contract_artifacts") or {}) if isinstance(meta_dict.get("anim_export_contract_artifacts"), dict) else {}

    def _resolve_pointer_relative(ref: Any, default_name: str = "") -> tuple[str, str, Optional[bool]]:
        ref_s = str(ref or default_name or "").strip()
        if not ref_s:
            return "", "", None
        p = Path(ref_s)
        if not p.is_absolute() and pointer_json:
            try:
                p = (Path(pointer_json).expanduser().resolve(strict=False).parent / p).resolve(strict=False)
            except Exception:
                p = Path(ref_s)
        try:
            exists = bool(p.exists())
        except Exception:
            exists = None
        return ref_s, str(p), exists

    contract_ref, contract_path, contract_exists = _resolve_pointer_relative(
        artifact_refs.get("sidecar"),
        default_name="anim_latest.contract.sidecar.json",
    )
    validation_ref, validation_path, validation_exists = _resolve_pointer_relative(
        artifact_refs.get("validation_json"),
        default_name="anim_latest.contract.validation.json",
    )
    hardpoints_ref, hardpoints_path, hardpoints_exists = _resolve_pointer_relative(
        artifact_refs.get("hardpoints_source_of_truth"),
        default_name="HARDPOINTS_SOURCE_OF_TRUTH.json",
    )
    packaging_ref, packaging_path, packaging_exists = _resolve_pointer_relative(
        artifact_refs.get("cylinder_packaging_passport"),
        default_name="CYLINDER_PACKAGING_PASSPORT.json",
    )
    road_web_ref, road_web_path, road_web_exists = _resolve_pointer_relative(
        artifact_refs.get("road_contract_web"),
        default_name="road_contract_web.json",
    )
    road_desktop_ref, road_desktop_path, road_desktop_exists = _resolve_pointer_relative(
        artifact_refs.get("road_contract_desktop"),
        default_name="road_contract_desktop.json",
    )

    out: dict = {
        "anim_latest_available": bool(pointer_json or npz_path or src.get("visual_cache_token") or src.get("visual_reload_inputs")),
        "anim_latest_global_pointer_json": str(global_pointer) if global_pointer else "",
        "anim_latest_pointer_json": pointer_json,
        "anim_latest_npz_path": npz_path,
        "anim_latest_visual_cache_token": str(src.get("visual_cache_token") or ""),
        "anim_latest_visual_reload_inputs": list(src.get("visual_reload_inputs") or []),
        "anim_latest_visual_cache_dependencies": dict(src.get("visual_cache_dependencies") or {}),
        "anim_latest_updated_utc": str(src.get("updated_utc") or src.get("updated_at") or ""),
        "anim_latest_pointer_json_exists": pointer_exists,
        "anim_latest_npz_exists": npz_exists,
        "anim_latest_pointer_json_in_workspace": pointer_in_workspace,
        "anim_latest_npz_in_workspace": npz_in_workspace,
        "anim_latest_usable": usable,
        "anim_latest_issues": issues,
        "anim_latest_contract_sidecar_ref": contract_ref,
        "anim_latest_contract_sidecar_path": contract_path,
        "anim_latest_contract_sidecar_exists": contract_exists,
        "anim_latest_contract_validation_json_ref": validation_ref,
        "anim_latest_contract_validation_json_path": validation_path,
        "anim_latest_contract_validation_json_exists": validation_exists,
        "anim_latest_hardpoints_source_of_truth_ref": hardpoints_ref,
        "anim_latest_hardpoints_source_of_truth_path": hardpoints_path,
        "anim_latest_hardpoints_source_of_truth_exists": hardpoints_exists,
        "anim_latest_cylinder_packaging_passport_ref": packaging_ref,
        "anim_latest_cylinder_packaging_passport_path": packaging_path,
        "anim_latest_cylinder_packaging_passport_exists": packaging_exists,
        "anim_latest_road_contract_web_ref": road_web_ref,
        "anim_latest_road_contract_web_path": road_web_path,
        "anim_latest_road_contract_web_exists": road_web_exists,
        "anim_latest_road_contract_desktop_ref": road_desktop_ref,
        "anim_latest_road_contract_desktop_path": road_desktop_path,
        "anim_latest_road_contract_desktop_exists": road_desktop_exists,
    }
    try:
        browser_perf = dict(collect_browser_perf_artifacts_summary(_workspace_dir() / "exports") or {})
    except Exception:
        browser_perf = {}
    if browser_perf:
        out.update(browser_perf)
    if include_meta and isinstance(src.get("meta"), dict):
        out["anim_latest_meta"] = dict(src.get("meta") or {})
    return out


# ----------------------- pointers: simulation -----------------------


def save_last_baseline_ptr(
    cache_dir: Path,
    meta: Optional[Dict[str, Any]] = None,
    ts_npz_dir: Optional[Path] = None,
    ts_npz_latest: Optional[Path] = None,
    anim_latest_npz: Optional[Path] = None,
    anim_latest_json: Optional[Path] = None,
) -> dict:
    """Save baseline pointer.

    Backward compatible:
    - writes legacy pointer baseline/_last_baseline.json
    - also writes global pointer _pointers/latest_simulation.json

    Additionally can store pointers to time-series NPZ logs (osc) and anim_latest bundle.
    """
    payload: dict = {
        "cache_dir": str(Path(cache_dir).resolve()),
        "meta": meta or {},
        "updated_at": _utc_iso(),
        "kind": "simulation",
    }
    if ts_npz_dir is not None:
        payload["ts_npz_dir"] = str(Path(ts_npz_dir).resolve())
    if ts_npz_latest is not None:
        payload["ts_npz_latest"] = str(Path(ts_npz_latest).resolve())
    if anim_latest_npz is not None:
        payload["anim_latest_npz"] = str(Path(anim_latest_npz).resolve())
    if anim_latest_json is not None:
        payload["anim_latest_json"] = str(Path(anim_latest_json).resolve())

    if anim_latest_npz is not None or anim_latest_json is not None:
        anim_payload = save_latest_animation_ptr(
            npz_path=anim_latest_npz,
            pointer_json=anim_latest_json,
            meta=meta,
        )
        payload["visual_cache_token"] = anim_payload.get("visual_cache_token", "")
        payload["visual_reload_inputs"] = list(anim_payload.get("visual_reload_inputs") or [])
        payload["visual_cache_dependencies"] = dict(anim_payload.get("visual_cache_dependencies") or {})
        payload["pointer_json"] = anim_payload.get("pointer_json")
        payload["npz_path"] = anim_payload.get("npz_path")
        payload["updated_utc"] = anim_payload.get("updated_utc")
        payload["meta"] = _merge_meta(payload.get("meta"), anim_payload.get("meta"))

    # legacy + new
    _write_json_atomic(last_baseline_ptr_path(), payload)
    _write_json_atomic(latest_simulation_ptr_path(), payload)
    return payload


def load_last_baseline_ptr() -> Optional[dict]:
    """Load baseline pointer (prefers global latest_simulation.json, falls back to legacy)."""
    ptr = _read_json(latest_simulation_ptr_path())
    if ptr:
        return ptr
    return _read_json(last_baseline_ptr_path())


def update_latest_simulation_npz(
    ts_npz_dir: Optional[Path] = None,
    ts_npz_latest: Optional[Path] = None,
    anim_latest_npz: Optional[Path] = None,
    anim_latest_json: Optional[Path] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Optional[dict]:
    """Update only NPZ-related fields in latest simulation pointer (do not drop cache_dir)."""
    ptr = load_last_baseline_ptr()
    if not ptr:
        return None

    meta = ptr.get("meta", {})
    if isinstance(meta, dict):
        ptr["meta"] = _merge_meta(meta, extra_meta)
    else:
        ptr["meta"] = extra_meta or {}

    if ts_npz_dir is not None:
        ptr["ts_npz_dir"] = str(Path(ts_npz_dir).resolve())
    if ts_npz_latest is not None:
        ptr["ts_npz_latest"] = str(Path(ts_npz_latest).resolve())
    if anim_latest_npz is not None:
        ptr["anim_latest_npz"] = str(Path(anim_latest_npz).resolve())
    if anim_latest_json is not None:
        ptr["anim_latest_json"] = str(Path(anim_latest_json).resolve())

    if anim_latest_npz is not None or anim_latest_json is not None:
        anim_payload = save_latest_animation_ptr(
            npz_path=anim_latest_npz,
            pointer_json=anim_latest_json,
            meta=ptr.get("meta"),
        )
        ptr["visual_cache_token"] = anim_payload.get("visual_cache_token", "")
        ptr["visual_reload_inputs"] = list(anim_payload.get("visual_reload_inputs") or [])
        ptr["visual_cache_dependencies"] = dict(anim_payload.get("visual_cache_dependencies") or {})
        ptr["pointer_json"] = anim_payload.get("pointer_json")
        ptr["npz_path"] = anim_payload.get("npz_path")
        ptr["updated_utc"] = anim_payload.get("updated_utc")
        ptr["meta"] = _merge_meta(ptr.get("meta"), anim_payload.get("meta"))

    ptr["updated_at"] = _utc_iso()
    ptr["kind"] = "simulation"

    # write both
    _write_json_atomic(last_baseline_ptr_path(), ptr)
    _write_json_atomic(latest_simulation_ptr_path(), ptr)
    return ptr


# ----------------------- pointers: optimization -----------------------


def save_last_opt_ptr(
    run_dir: Path,
    meta: Optional[Dict[str, Any]] = None,
    ts_npz_dir: Optional[Path] = None,
    ts_npz_latest: Optional[Path] = None,
) -> dict:
    """Save optimization pointer.

    Backward compatible:
    - writes legacy pointer opt/_last_opt.json
    - also writes global pointer _pointers/latest_optimization.json

    Optionally store time-series NPZ pointers if optimization exports them.
    """
    payload: dict = {
        "run_dir": str(Path(run_dir).resolve()),
        "meta": meta or {},
        "updated_at": _utc_iso(),
        "kind": "optimization",
    }
    if ts_npz_dir is not None:
        payload["ts_npz_dir"] = str(Path(ts_npz_dir).resolve())
    if ts_npz_latest is not None:
        payload["ts_npz_latest"] = str(Path(ts_npz_latest).resolve())

    _write_json_atomic(last_opt_ptr_path(), payload)
    _write_json_atomic(latest_optimization_ptr_path(), payload)
    return payload


def load_last_opt_ptr() -> Optional[dict]:
    """Load optimization pointer (prefers global latest_optimization.json, falls back to legacy)."""
    ptr = _read_json(latest_optimization_ptr_path())
    if ptr:
        return ptr
    return _read_json(last_opt_ptr_path())


def update_latest_optimization_npz(
    ts_npz_dir: Optional[Path] = None,
    ts_npz_latest: Optional[Path] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> Optional[dict]:
    ptr = load_last_opt_ptr()
    if not ptr:
        return None

    meta = ptr.get("meta", {})
    if isinstance(meta, dict):
        ptr["meta"] = _merge_meta(meta, extra_meta)
    else:
        ptr["meta"] = extra_meta or {}

    if ts_npz_dir is not None:
        ptr["ts_npz_dir"] = str(Path(ts_npz_dir).resolve())
    if ts_npz_latest is not None:
        ptr["ts_npz_latest"] = str(Path(ts_npz_latest).resolve())

    ptr["updated_at"] = _utc_iso()
    ptr["kind"] = "optimization"

    _write_json_atomic(last_opt_ptr_path(), ptr)
    _write_json_atomic(latest_optimization_ptr_path(), ptr)
    return ptr


# ----------------------- durable storage: baseline summary -----------------------


def baseline_table_path(cache_dir: Path) -> Path:
    return Path(cache_dir) / "baseline_table.csv"


def save_baseline_df(cache_dir: Path, df: "pd.DataFrame") -> Path:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    p = baseline_table_path(cache_dir)
    df.to_csv(p, index=False)
    return p


def load_baseline_df(cache_dir: Path) -> Optional["pd.DataFrame"]:
    p = baseline_table_path(cache_dir)
    if p.exists():
        try:
            import pandas as pd  # type: ignore

            return pd.read_csv(p)
        except Exception:
            return None
    return None


# ----------------------- autoload into streamlit session_state -----------------------


def autoload_to_session(session_state: dict) -> None:
    """Autoload persisted artifacts into a Streamlit-like `session_state` dict.

    Absolute-law notes:
      - We write ONLY canonical `st.session_state[...]` keys (no aliases, no duplicates).
      - If something can't be loaded, we just skip it (no crash).

    What we autoload:
      - Last optimization pointer + meta (from _pointers/latest_optimization.json)
      - Latest animation pointer (from _pointers/anim_latest.json)
    """
    # Baseline persistence is handled separately (baseline_table.csv). We only keep
    # the baseline session keys initialized here.
    session_state.setdefault("baseline_df", None)
    session_state.setdefault("baseline_loaded_from_disk", False)

    # ---------------------------
    # Optimization: last run folder + meta
    # ---------------------------
    opt_info = load_last_opt_ptr() or {}

    run_dir = opt_info.get("run_dir")
    if run_dir:
        session_state["last_opt_ptr"] = str(run_dir)

    opt_meta = opt_info.get("meta")
    if isinstance(opt_meta, dict):
        session_state["last_opt_meta"] = dict(opt_meta)
    else:
        meta_json = opt_info.get("meta_json")
        meta = _read_json(Path(meta_json)) if isinstance(meta_json, str) and meta_json else None
        session_state["last_opt_meta"] = meta or {}

    # ---------------------------
    # Animation: latest pointers
    # ---------------------------
    anim_info = load_latest_animation_ptr() or {}
    if not anim_info:
        anim_info = load_last_baseline_ptr() or {}

    if anim_info:
        session_state["anim_latest_npz"] = anim_info.get("npz_path") or anim_info.get("anim_latest_npz")
        session_state["anim_latest_pointer"] = anim_info.get("pointer_json") or anim_info.get("anim_latest_json")
        session_state["anim_latest_meta"] = dict(anim_info.get("meta") or {})
        session_state["anim_latest_visual_cache_token"] = str(anim_info.get("visual_cache_token") or "")
        session_state["anim_latest_visual_reload_inputs"] = list(anim_info.get("visual_reload_inputs") or [])
        session_state["anim_latest_visual_cache_dependencies"] = dict(anim_info.get("visual_cache_dependencies") or {})
        session_state["anim_latest_updated_utc"] = anim_info.get("updated_utc") or anim_info.get("updated_at")
