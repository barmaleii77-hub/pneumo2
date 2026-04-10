from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np
try:
    import pandas as pd
except Exception:  # pragma: no cover - optional dependency for lightweight diagnostics
    pd = None  # type: ignore[assignment]

from pneumo_solver_ui.data_contract import read_visual_geometry_meta, supplement_animator_geometry_meta
from pneumo_solver_ui.solver_points_contract import collect_solver_points_contract_issues

CORNERS = ["ЛП", "ПП", "ЛЗ", "ПЗ"]
LogFn = Callable[[str], None]


def _emit(msg: str, log: LogFn | None) -> None:
    if log is None:
        return
    try:
        log(msg)
    except Exception:
        pass


def _is_dataframe(value: Any) -> bool:
    return bool(pd is not None and isinstance(value, pd.DataFrame))


def format_missing_preview(items: List[str], *, limit: int = 4) -> str:
    if not items:
        return ""
    if len(items) <= limit:
        return ", ".join(items)
    return ", ".join(items[:limit]) + f", +{len(items) - limit} more"


def _coerce_columns(df_main_or_columns: Any) -> set[str]:
    if _is_dataframe(df_main_or_columns):
        return {str(c) for c in df_main_or_columns.columns}
    if df_main_or_columns is None:
        return set()
    try:
        return {str(c) for c in df_main_or_columns}
    except Exception:
        return set()


def _coerce_time_vector(df_main_or_columns: Any, time_vector: Sequence[float] | np.ndarray | None) -> np.ndarray | None:
    if time_vector is not None:
        try:
            arr = np.asarray(time_vector, dtype=float)
            if arr.ndim == 1 and arr.size:
                return arr
        except Exception:
            return None
    if _is_dataframe(df_main_or_columns) and "время_с" in df_main_or_columns.columns:
        try:
            arr = np.asarray(df_main_or_columns["время_с"], dtype=float)
            if arr.ndim == 1 and arr.size:
                return arr
        except Exception:
            return None
    return None




ROAD_CONTRACT_WEB_JSON_NAME = "road_contract_web.json"
ROAD_CONTRACT_DESKTOP_JSON_NAME = "road_contract_desktop.json"


def _road_contract_consumer_label(consumer: str) -> str:
    c = str(consumer or "").strip().lower()
    if c == "web":
        return "Web UI"
    if c == "desktop":
        return "Desktop Animator"
    return str(consumer or "consumer")


def _road_width_contract_status(meta: Mapping[str, Any] | None, *, log: LogFn | None = None) -> Dict[str, object]:
    meta_dict = dict(meta or {})
    raw_geom = meta_dict.get("geometry") if isinstance(meta_dict.get("geometry"), Mapping) else {}
    vis_geom = read_visual_geometry_meta(meta_dict, context="road contract meta_json", log=log) if isinstance(meta_dict, Mapping) else {}
    explicit = vis_geom.get("road_width_m")
    try:
        supplemented = supplement_animator_geometry_meta(raw_geom, log=log) if isinstance(raw_geom, Mapping) else {}
    except Exception:
        supplemented = {}
    effective = supplemented.get("road_width_m") if isinstance(supplemented, Mapping) else None
    track = vis_geom.get("track_m")
    wheel_width = vis_geom.get("wheel_width_m")
    if explicit is not None:
        status = "explicit"
    elif effective is not None:
        status = "derived_from_track_and_wheel_width"
    else:
        status = "missing"
    return {
        "status": status,
        "explicit_road_width_m": float(explicit) if explicit is not None else None,
        "effective_road_width_m": float(effective) if effective is not None else None,
        "track_m": float(track) if track is not None else None,
        "wheel_width_m": float(wheel_width) if wheel_width is not None else None,
    }


def build_road_contract_report(
    df_main_or_columns: pd.DataFrame | Iterable[str] | None,
    *,
    meta: Mapping[str, Any] | None = None,
    npz_path: str | Path | None = None,
    pointer_path: str | Path | None = None,
    time_vector: Sequence[float] | np.ndarray | None = None,
    road_sidecar: Mapping[str, Any] | None = None,
    consumer: str,
    updated_utc: str = "",
    log: LogFn | None = None,
) -> Dict[str, object]:
    consumer_key = str(consumer or "").strip().lower()
    if consumer_key not in {"web", "desktop"}:
        raise ValueError(f"Unsupported road contract consumer: {consumer!r}")

    consumer_label = _road_contract_consumer_label(consumer_key)
    status = collect_visual_contract_status(
        df_main_or_columns,
        meta=meta,
        npz_path=npz_path,
        time_vector=time_vector,
        road_sidecar=road_sidecar,
        context=f"{consumer_label} road contract",
        log=log,
    )
    width_info = _road_width_contract_status(meta, log=log)

    failures: list[str] = []
    warnings: list[str] = []
    messages: list[str] = []

    if not bool(status.get("road_complete")):
        missing = [str(x) for x in (status.get("road_missing_corners") or []) if str(x).strip()]
        failures.append(
            f"{consumer_label}: missing canonical road traces for corners: "
            + (", ".join(missing) if missing else "unknown")
        )

    if not bool(status.get("geometry_contract_ok", True)):
        warnings.extend([str(x) for x in (status.get("geometry_contract_issues") or []) if str(x).strip()])

    road_width_status = str(width_info.get("status") or "missing")
    if road_width_status == "derived_from_track_and_wheel_width":
        warnings.append(
            f"{consumer_label}: road_width_m is not explicit in nested geometry; using SERVICE/DERIVED width from track_m + wheel_width_m."
        )
    elif road_width_status == "missing":
        warnings.append(
            f"{consumer_label}: road_width_m is missing and cannot be derived from nested geometry."
        )

    if failures:
        level = "FAIL"
        messages.extend(failures)
        messages.extend(warnings)
    elif warnings:
        level = "WARN"
        messages.extend(warnings)
    else:
        level = "PASS"
        messages.append(f"{consumer_label}: road parameters are explicit and consumer-ready")

    out: Dict[str, object] = {
        "schema": f"road_contract.{consumer_key}.v1",
        "consumer": consumer_key,
        "consumer_label": consumer_label,
        "updated_utc": str(updated_utc or ""),
        "npz_path": str(npz_path or ""),
        "pointer_path": str(pointer_path or ""),
        "level": level,
        "messages": messages,
        "failures": failures,
        "warnings": warnings,
        "road_complete": bool(status.get("road_complete")),
        "road_source": str(status.get("road_source") or "none"),
        "road_available_corners": list(status.get("road_available_corners") or []),
        "road_missing_corners": list(status.get("road_missing_corners") or []),
        "road_direct_available_corners": list(status.get("road_direct_available_corners") or []),
        "road_sidecar_available_corners": list(status.get("road_sidecar_available_corners") or []),
        "road_sidecar_path": str(status.get("road_sidecar_path") or ""),
        "road_issue_messages": list(status.get("road_issue_messages") or []),
        "geometry_contract_ok": bool(status.get("geometry_contract_ok", True)),
        "geometry_contract_issues": list(status.get("geometry_contract_issues") or []),
        "road_width_status": road_width_status,
        "explicit_road_width_m": width_info.get("explicit_road_width_m"),
        "effective_road_width_m": width_info.get("effective_road_width_m"),
        "track_m": width_info.get("track_m"),
        "wheel_width_m": width_info.get("wheel_width_m"),
        "required_evidence": [
            "road params present check PASS for this consumer",
            "road_source and available/missing corners are explicit",
            "road_width_status is explicit or clearly marked as derived/missing",
        ],
        "notes": [
            "Consumer-specific road contract is separate so failures can be addressed to the correct surface (Web UI vs Desktop Animator).",
            "No consumer may invent missing road traces or silently borrow them from unrelated channels.",
        ],
    }
    return out


def write_road_contract_artifacts(
    exports_dir: str | Path,
    *,
    df_main_or_columns: pd.DataFrame | Iterable[str] | None,
    meta: Mapping[str, Any] | None,
    npz_path: str | Path | None = None,
    pointer_path: str | Path | None = None,
    updated_utc: str = "",
    time_vector: Sequence[float] | np.ndarray | None = None,
    log: LogFn | None = None,
) -> Dict[str, object]:
    exports_dir = Path(exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)
    web_report = build_road_contract_report(
        df_main_or_columns,
        meta=meta,
        npz_path=npz_path,
        pointer_path=pointer_path,
        time_vector=time_vector,
        consumer="web",
        updated_utc=updated_utc,
        log=log,
    )
    desktop_report = build_road_contract_report(
        df_main_or_columns,
        meta=meta,
        npz_path=npz_path,
        pointer_path=pointer_path,
        time_vector=time_vector,
        consumer="desktop",
        updated_utc=updated_utc,
        log=log,
    )
    web_path = exports_dir / ROAD_CONTRACT_WEB_JSON_NAME
    desktop_path = exports_dir / ROAD_CONTRACT_DESKTOP_JSON_NAME
    web_path.write_text(json.dumps(web_report, ensure_ascii=False, indent=2), encoding="utf-8")
    desktop_path.write_text(json.dumps(desktop_report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "road_contract_web_path": str(web_path),
        "road_contract_desktop_path": str(desktop_path),
        "road_contract_web": web_report,
        "road_contract_desktop": desktop_report,
    }
def _path_fingerprint(path: str | Path | None) -> Dict[str, object]:
    if path in (None, ""):
        return {}
    try:
        p = Path(str(path)).expanduser().resolve()
    except Exception:
        return {"path": str(path)}
    out: Dict[str, object] = {"path": str(p), "exists": bool(p.exists())}
    if not p.exists():
        return out
    try:
        st = p.stat()
        out["mtime_ns"] = int(st.st_mtime_ns)
        out["size"] = int(st.st_size)
    except Exception:
        pass
    return out


def _read_minimal_npz_meta(npz_path: str | Path | None) -> Dict[str, Any]:
    if npz_path in (None, ""):
        return {}
    try:
        with np.load(Path(str(npz_path)).expanduser().resolve(), allow_pickle=True) as npz:
            if "meta_json" not in npz:
                return {}
            raw = npz["meta_json"].tolist()
    except Exception:
        return {}
    try:
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", errors="replace")
        if isinstance(raw, str):
            data = json.loads(raw)
            return dict(data) if isinstance(data, dict) else {}
        if isinstance(raw, dict):
            return dict(raw)
    except Exception:
        return {}
    return {}


def collect_visual_cache_dependencies(
    npz_path: str | Path | None,
    meta: Mapping[str, Any] | None = None,
    *,
    context: str = "visual consumers",
    log: LogFn | None = None,
) -> Dict[str, object]:
    """Collect external file dependencies for UI cache invalidation.

    The main NPZ file already invalidates caches when its mtime/size changes.
    However visual consumers may also depend on files referenced from ``meta_json``
    (currently canonical ``road_csv``). This helper returns a plain dict suitable
    for using as a Streamlit cache argument and for building stable hash keys in
    ``ui_heavy_cache``.

    The helper is strict/non-magical:
    - it never invents sidecars;
    - it only fingerprints the canonical ``road_csv`` reference when present;
    - missing sidecars are still reflected in the dependency payload.
    """
    meta_obj: Mapping[str, Any] = meta if isinstance(meta, Mapping) else _read_minimal_npz_meta(npz_path)
    raw_sidecar = meta_obj.get("road_csv") if isinstance(meta_obj, Mapping) else None
    resolved = _resolve_sidecar_path(npz_path, raw_sidecar)

    deps: Dict[str, object] = {
        "version": 1,
        "context": str(context),
        "npz": _path_fingerprint(npz_path),
        "road_csv_ref": str(raw_sidecar or ""),
        "road_csv_path": str(resolved) if resolved is not None else "",
        "road_csv": _path_fingerprint(resolved) if resolved is not None else {},
    }
    if raw_sidecar and resolved is None:
        msg = (
            f"[contract] {context} cache dependencies could not resolve road_csv={raw_sidecar!r}; "
            "using NPZ fingerprint only."
        )
        _emit(msg, log)
    return deps


def visual_cache_dependencies_token(deps: Mapping[str, object] | None) -> str:
    """Return a stable token for visual dependency reload / cache keys.

    Important: the token must be **context-agnostic**.
    Human-readable labels like ``context="compare_ui NPZ"`` help logs and diagnostics,
    but must not change the token for the same underlying NPZ + sidecars.
    """
    if not isinstance(deps, Mapping):
        return ""
    try:
        base = {str(k): v for k, v in dict(deps).items() if str(k) != 'context'}
        payload = json.dumps(base, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        try:
            payload = repr(sorted((str(k), repr(v)) for k, v in dict(deps).items() if str(k) != 'context'))
        except Exception:
            return ""
    return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()




def build_visual_reload_diagnostics(
    npz_path: str | Path | None,
    meta: Mapping[str, Any] | None = None,
    *,
    context: str = "visual consumers",
    log: LogFn | None = None,
) -> Dict[str, object]:
    """Build human-readable diagnostics for visual reload / cache invalidation.

    This is stricter than ad-hoc UI fields: it always derives diagnostics from
    the same canonical dependency payload that web/desktop use for cache busting.
    """
    deps = collect_visual_cache_dependencies(
        npz_path,
        meta=meta,
        context=context,
        log=log,
    )
    token = visual_cache_dependencies_token(deps)
    inputs: List[str] = ["npz"]
    if str(deps.get("road_csv_ref") or "").strip():
        inputs.append("road_csv")
    return {
        "version": 1,
        "context": str(context),
        "inputs": inputs,
        "visual_cache_token": str(token or ""),
        "visual_cache_dependencies": dict(deps),
        "road_csv_declared": bool(str(deps.get("road_csv_ref") or "").strip()),
        "road_csv_resolved": bool(str(deps.get("road_csv_path") or "").strip()),
    }


def _resolve_sidecar_path(npz_path: str | Path | None, raw_path: Any) -> Path | None:
    if raw_path in (None, ""):
        return None
    try:
        p = Path(str(raw_path)).expanduser()
    except Exception:
        return None
    if p.is_absolute():
        return p
    if npz_path in (None, ""):
        return None
    try:
        base = Path(str(npz_path)).expanduser().resolve().parent
    except Exception:
        return None
    return (base / p).resolve()


def load_visual_road_sidecar(
    npz_path: str | Path | None,
    meta: Mapping[str, Any] | None,
    *,
    time_vector: Sequence[float] | np.ndarray | None = None,
    context: str = "visual consumers",
    log: LogFn | None = None,
) -> Dict[str, object]:
    """Load canonical road traces from ``meta_json.road_csv`` if available.

    Returns a dict with:
      - ``wheels``: {corner -> list[float]}
      - ``available_corners``: list[str]
      - ``path``: resolved CSV path (when known)
      - ``issues`` / ``warnings``: human-readable audit messages
      - ``ok``: whether all 4 wheel traces were loaded successfully

    This helper is strict:
    - it does not invent any road samples;
    - it only accepts canonical ``t`` + ``z0..z3`` (or first 4 ``z*`` columns);
    - if ``time_vector`` is provided, the sidecar is aligned to it by interpolation.
    """
    out: Dict[str, object] = {
        "wheels": {},
        "available_corners": [],
        "path": "",
        "issues": [],
        "warnings": [],
        "ok": False,
    }

    def _issue(msg: str) -> None:
        issues = list(out.get("issues") or [])
        if msg not in issues:
            issues.append(msg)
            out["issues"] = issues
            _emit(msg, log)

    def _warn(msg: str) -> None:
        warnings = list(out.get("warnings") or [])
        if msg not in warnings:
            warnings.append(msg)
            out["warnings"] = warnings
            _emit(msg, log)

    if not isinstance(meta, Mapping):
        return out

    raw_sidecar = meta.get("road_csv")
    if not raw_sidecar:
        return out

    resolved = _resolve_sidecar_path(npz_path, raw_sidecar)
    out["path"] = str(resolved or raw_sidecar)

    if resolved is None:
        _issue(
            f"[contract] {context} references road_csv={raw_sidecar!r}, "
            "but sidecar path cannot be resolved without the NPZ location."
        )
        return out

    if not resolved.exists():
        _issue(
            f"[contract] {context} references road_csv '{resolved}', but the file does not exist."
        )
        return out

    if pd is None:
        _warn(
            f"[contract] pandas is unavailable; skipping road_csv content validation for '{resolved}'."
        )
        return out

    try:
        df = pd.read_csv(resolved)
    except Exception as e:
        _issue(f"[contract] Failed to read road_csv sidecar '{resolved}': {type(e).__name__}: {e}")
        return out

    if "t" not in df.columns:
        _issue(f"[contract] road_csv sidecar '{resolved}' must contain canonical column 't'.")
        return out

    zcols = [c for c in ("z0", "z1", "z2", "z3") if c in df.columns]
    if len(zcols) != 4:
        alt = [str(c) for c in df.columns if str(c).lower().startswith("z")]
        if len(alt) >= 4:
            zcols = alt[:4]
            _warn(
                f"[contract] road_csv sidecar '{resolved}' uses non-canonical z-columns {alt[:4]}; "
                "canonical 'z0..z3' is preferred."
            )
    if len(zcols) != 4:
        _issue(
            f"[contract] road_csv sidecar '{resolved}' must contain canonical wheel traces "
            "z0, z1, z2, z3 (or at least four z* columns)."
        )
        return out

    try:
        t_src = np.asarray(df["t"], dtype=float)
    except Exception as e:
        _issue(f"[contract] road_csv sidecar '{resolved}' has non-numeric 't': {type(e).__name__}: {e}")
        return out

    if t_src.ndim != 1 or t_src.size == 0:
        _issue(f"[contract] road_csv sidecar '{resolved}' has empty/invalid 't' column.")
        return out

    t_dst = _coerce_time_vector(None, time_vector)
    wheels: Dict[str, list[float]] = {}
    for corner, zcol in zip(CORNERS, zcols):
        try:
            arr = np.asarray(df[zcol], dtype=float)
        except Exception as e:
            _issue(
                f"[contract] road_csv sidecar '{resolved}' has non-numeric wheel trace '{zcol}': "
                f"{type(e).__name__}: {e}"
            )
            return out
        if arr.ndim != 1 or arr.size == 0:
            _issue(f"[contract] road_csv sidecar '{resolved}' has empty/invalid wheel trace '{zcol}'.")
            return out
        if t_dst is not None and t_dst.size:
            if t_src.size < 2:
                _issue(
                    f"[contract] road_csv sidecar '{resolved}' has only one sample and cannot be aligned "
                    "to the NPZ time vector."
                )
                return out
            same_shape = arr.shape == t_dst.shape and t_src.shape == t_dst.shape
            same_time = False
            if same_shape:
                try:
                    same_time = bool(float(np.max(np.abs(t_src - t_dst))) <= 1e-9)
                except Exception:
                    same_time = False
            if (not same_shape) or (not same_time):
                arr = np.interp(t_dst, t_src, arr, left=float(arr[0]), right=float(arr[-1]))
        wheels[corner] = np.asarray(arr, dtype=float).tolist()

    out["wheels"] = wheels
    out["available_corners"] = [corner for corner in CORNERS if corner in wheels]
    out["ok"] = len(out["available_corners"]) == len(CORNERS)
    return out


def collect_visual_contract_status(
    df_main_or_columns: pd.DataFrame | Iterable[str] | None,
    *,
    meta: Mapping[str, Any] | None = None,
    npz_path: str | Path | None = None,
    time_vector: Sequence[float] | np.ndarray | None = None,
    road_sidecar: Mapping[str, Any] | None = None,
    context: str = "visual consumers",
    log: LogFn | None = None,
) -> Dict[str, object]:
    """Collect a unified visual-consumer contract status.

    Unifies four checks in one place:
      - nested ``meta_json.geometry`` audit (strict, canonical-only)
      - canonical road availability (df_main and/or canonical ``road_csv`` sidecar)
      - canonical solver-point triplets
      - human-readable overlay text for web/desktop consumers

    The function is non-mutating and returns a plain dict suitable for:
      - ``meta["_visual_contract"]`` in loaded bundles;
      - web overlays / captions;
      - CLI/self-check summaries.
    """
    cols = _coerce_columns(df_main_or_columns)
    t = _coerce_time_vector(df_main_or_columns, time_vector)

    sidecar_report = dict(road_sidecar or {})
    if not sidecar_report:
        sidecar_report = load_visual_road_sidecar(
            npz_path,
            meta,
            time_vector=t,
            context=context,
            log=log,
        )

    sidecar_wheels = dict(sidecar_report.get("wheels") or {})
    sidecar_available = [c for c in CORNERS if c in sidecar_wheels]
    direct_available = [c for c in CORNERS if f"дорога_{c}_м" in cols]
    road_available = [c for c in CORNERS if (c in direct_available) or (c in sidecar_available)]
    road_missing = [c for c in CORNERS if c not in road_available]
    road_complete = not bool(road_missing)

    if direct_available and sidecar_available:
        road_source = "df_main+road_csv"
    elif direct_available:
        road_source = "df_main"
    elif sidecar_available:
        road_source = "road_csv"
    else:
        road_source = "none"

    geometry_issues: List[str] = []
    geometry_warnings: List[str] = []
    geometry_contract_ok = True
    if isinstance(meta, Mapping):
        vis_geom = read_visual_geometry_meta(
            meta,
            context=f"{context} meta_json",
            log=log,
        )
        geometry_issues = list(vis_geom.get("issues") or [])
        geometry_warnings = list(vis_geom.get("warnings") or [])
        geometry_contract_ok = not bool(geometry_issues)

    solver_status = collect_solver_points_contract_issues(
        cols,
        context=context,
    )
    solver_complete = bool(solver_status.get("ok"))
    solver_missing_triplets = list(solver_status.get("missing_triplets") or [])
    solver_partial_triplets = list(solver_status.get("partial_triplets") or [])

    road_overlay_text = ""
    road_issue_messages = list(sidecar_report.get("issues") or [])
    if not road_complete:
        msg = "[contract] " + context + " missing canonical road traces for corners: " + ", ".join(road_missing) + "."
        road_issue_messages.append(msg)
        road_overlay_text = "NO ROAD DATA: missing " + format_missing_preview(road_missing)

    solver_overlay_text = ""
    if not solver_complete:
        missing_preview = format_missing_preview(solver_missing_triplets or solver_partial_triplets)
        solver_overlay_text = "NO SOLVER POINTS: missing " + (missing_preview or "canonical triplets")

    issues: List[str] = []
    warnings: List[str] = []
    issues.extend(geometry_issues)
    issues.extend(road_issue_messages)
    issues.extend(list(solver_status.get("issues") or []))
    warnings.extend(geometry_warnings)
    warnings.extend(list(sidecar_report.get("warnings") or []))

    status: Dict[str, object] = {
        "geometry_contract_ok": geometry_contract_ok,
        "geometry_contract_issues": geometry_issues,
        "geometry_contract_warnings": geometry_warnings,
        "road_complete": road_complete,
        "road_missing_corners": road_missing,
        "road_available_corners": road_available,
        "road_direct_available_corners": direct_available,
        "road_sidecar_available_corners": sidecar_available,
        "road_source": road_source,
        "road_overlay_text": road_overlay_text,
        "road_issue_messages": road_issue_messages,
        "road_sidecar_path": str(sidecar_report.get("path") or ""),
        "road_sidecar_warnings": list(sidecar_report.get("warnings") or []),
        "solver_points_complete": solver_complete,
        "solver_points_missing_triplets": solver_missing_triplets,
        "solver_points_partial_triplets": solver_partial_triplets,
        "solver_points_overlay_text": solver_overlay_text,
        "solver_points_issues": list(solver_status.get("issues") or []),
        "issues": issues,
        "warnings": warnings,
    }
    return status


def filter_road_payload(road: Dict[str, List[float]], status: Dict[str, object]) -> Dict[str, List[float]]:
    allowed = {str(c) for c in (status.get("road_available_corners") or [])}
    out: Dict[str, List[float]] = {}
    for c in CORNERS:
        if c in allowed and isinstance(road.get(c), list):
            out[c] = list(road[c])
    return out


__all__ = [
    "CORNERS",
    "ROAD_CONTRACT_WEB_JSON_NAME",
    "ROAD_CONTRACT_DESKTOP_JSON_NAME",
    "build_visual_reload_diagnostics",
    "build_road_contract_report",
    "write_road_contract_artifacts",
    "collect_visual_cache_dependencies",
    "visual_cache_dependencies_token",
    "load_visual_road_sidecar",
    "collect_visual_contract_status",
    "filter_road_payload",
]
