# -*- coding: utf-8 -*-
"""pneumo_solver_ui.npz_bundle

Единый экспорт логов (UI → NPZ) и экспорт "anim_latest" для Desktop Animator.

Ключевая цель: **не терять данные** при передаче из Streamlit UI в Windows Desktop Animator.

См. также: 00_READ_FIRST__ABSOLUTE_LAW.md и 01_PARAMETER_REGISTRY.md (в корне релиза).

Поддерживаемые контейнеры:
  - full_log: произвольный .npz (обычно Txx_osc.npz)
  - anim_latest: workspace/exports/anim_latest.npz + anim_latest.json (pointer)

NPZ schema (массивы):
  - main_cols, main_values
  - p_cols, p_values (optional)
  - q_cols, q_values (optional)
  - open_cols, open_values (optional)
  - meta_json (JSON string, optional)

Meta contract (канон):
  - schema_version = "pneumo_npz_meta_v1"
  - road_csv / axay_csv / scenario_json: sidecar пути (для anim_latest копируются рядом)
  - алиасы запрещены (ABSOLUTE LAW): legacy keys только логируются, без авто‑миграции.

Важно:
  - При export_anim_latest_bundle() sidecar-файлы копируются в exports/ и meta переписывается
    на относительные имена (portable bundle).
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import json
import shutil
import logging
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .data_contract import (
    ANIM_LATEST_POINTER_SCHEMA_VERSION,
    normalize_npz_meta,
    dumps_meta_json,
    assert_required_geometry_meta,
    supplement_animator_geometry_meta,
)
from .solver_points_contract import assert_required_solver_points_contract
from .visual_contract import (
    ROAD_CONTRACT_DESKTOP_JSON_NAME,
    ROAD_CONTRACT_WEB_JSON_NAME,
    build_visual_reload_diagnostics,
    write_road_contract_artifacts,
)
from .anim_export_contract import (
    ANIM_EXPORT_CONTRACT_SIDECAR_NAME,
    ANIM_EXPORT_CONTRACT_VALIDATION_JSON_NAME,
    ANIM_EXPORT_CONTRACT_VALIDATION_MD_NAME,
    CYLINDER_PACKAGING_PASSPORT_JSON_NAME,
    HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME,
    augment_anim_latest_meta,
    ensure_cylinder_length_columns,
    validate_anim_export_contract_meta,
    write_anim_export_contract_artifacts,
)


# NOTE: версии и ключи централизованы в pneumo_solver_ui.data_contract

ANIMATOR_TIME_COL = "время_с"
ANIMATOR_MAX_FRAME_DT_S = 1.0 / 120.0
ANIMATOR_MAX_FRAME_DS_M = 0.10
ANIMATOR_MAX_EXPORT_POINTS = 20000


def _table_time_vector(df: pd.DataFrame) -> np.ndarray:
    if df is None or len(df) == 0:
        return np.zeros((0,), dtype=float)
    if ANIMATOR_TIME_COL in df.columns:
        try:
            return np.asarray(df[ANIMATOR_TIME_COL], dtype=float).reshape(-1)
        except Exception:
            pass
    try:
        return np.arange(len(df), dtype=float)
    except Exception:
        return np.zeros((0,), dtype=float)


def _column_prefers_step_hold(name: str, values: np.ndarray) -> bool:
    lname = str(name or "").lower()
    discrete_tokens = (
        "id", "индекс", "сегмент", "segment", "mode", "режим", "state", "состояни",
        "open", "клапан", "в_воздухе", "air", "count", "n_", "flag", "флаг",
    )
    if any(tok in lname for tok in discrete_tokens):
        return True
    arr = np.asarray(values, dtype=float).reshape(-1)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return False
    if np.all(np.abs(finite - np.round(finite)) <= 1e-9) and np.unique(np.round(finite)).size <= 64:
        return True
    return False


def _linear_resample_series(t_src: np.ndarray, y_src: np.ndarray, t_new: np.ndarray) -> np.ndarray:
    t_src = np.asarray(t_src, dtype=float).reshape(-1)
    y_src = np.asarray(y_src, dtype=float).reshape(-1)
    t_new = np.asarray(t_new, dtype=float).reshape(-1)
    if t_src.size == 0 or y_src.size == 0 or t_new.size == 0:
        return np.zeros((t_new.size,), dtype=float)
    finite = np.isfinite(t_src) & np.isfinite(y_src)
    if not np.any(finite):
        return np.full((t_new.size,), np.nan, dtype=float)
    ts = np.asarray(t_src[finite], dtype=float)
    ys = np.asarray(y_src[finite], dtype=float)
    if ts.size == 1:
        return np.full((t_new.size,), float(ys[0]), dtype=float)
    order = np.argsort(ts, kind="mergesort")
    ts = ts[order]
    ys = ys[order]
    keep = np.concatenate(([True], np.diff(ts) > 1e-12))
    ts = ts[keep]
    ys = ys[keep]
    if ts.size == 1:
        return np.full((t_new.size,), float(ys[0]), dtype=float)
    return np.interp(t_new, ts, ys, left=float(ys[0]), right=float(ys[-1]))


def _step_resample_series(t_src: np.ndarray, y_src: np.ndarray, t_new: np.ndarray) -> np.ndarray:
    t_src = np.asarray(t_src, dtype=float).reshape(-1)
    y_src = np.asarray(y_src, dtype=float).reshape(-1)
    t_new = np.asarray(t_new, dtype=float).reshape(-1)
    if t_src.size == 0 or y_src.size == 0 or t_new.size == 0:
        return np.zeros((t_new.size,), dtype=float)
    finite = np.isfinite(t_src) & np.isfinite(y_src)
    if not np.any(finite):
        return np.full((t_new.size,), np.nan, dtype=float)
    ts = np.asarray(t_src[finite], dtype=float)
    ys = np.asarray(y_src[finite], dtype=float)
    if ts.size == 1:
        return np.full((t_new.size,), float(ys[0]), dtype=float)
    order = np.argsort(ts, kind="mergesort")
    ts = ts[order]
    ys = ys[order]
    keep = np.concatenate(([True], np.diff(ts) > 1e-12))
    ts = ts[keep]
    ys = ys[keep]
    if ts.size == 1:
        return np.full((t_new.size,), float(ys[0]), dtype=float)
    idx = np.searchsorted(ts, t_new, side="right") - 1
    idx = np.clip(idx, 0, ts.size - 1)
    return ys[idx].astype(float, copy=False)


def _resample_dataframe_for_animator(df: Optional[pd.DataFrame], t_new: np.ndarray, *, force_step: bool = False) -> Optional[pd.DataFrame]:
    if df is None:
        return None
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
    if len(df) == 0:
        out = pd.DataFrame(columns=list(df.columns))
        if ANIMATOR_TIME_COL in out.columns:
            out[ANIMATOR_TIME_COL] = np.asarray(t_new, dtype=float)
        return out
    t_src = _table_time_vector(df)
    t_new = np.asarray(t_new, dtype=float).reshape(-1)
    out: Dict[str, np.ndarray] = {}
    for col in df.columns:
        if str(col) == ANIMATOR_TIME_COL:
            out[str(col)] = t_new.astype(float, copy=False)
            continue
        try:
            vals = np.asarray(df[col], dtype=float).reshape(-1)
        except Exception:
            vals = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float, copy=True)
        use_step = bool(force_step) or _column_prefers_step_hold(str(col), vals)
        if use_step:
            out[str(col)] = _step_resample_series(t_src, vals, t_new)
        else:
            out[str(col)] = _linear_resample_series(t_src, vals, t_new)
    if ANIMATOR_TIME_COL not in out:
        out[ANIMATOR_TIME_COL] = t_new.astype(float, copy=False)
    return pd.DataFrame(out, columns=[str(c) for c in df.columns] if len(df.columns) else list(out.keys()))


def _build_animator_dense_time_grid(df_main: pd.DataFrame, meta: Optional[Dict[str, Any]]) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
    diag: Dict[str, Any] = {
        "enabled": False,
        "source_points": 0,
        "target_points": 0,
        "target_dt_s": None,
        "source_median_dt_s": None,
        "source_max_dt_s": None,
        "source_max_distance_step_m": None,
        "vmax_mps": None,
        "reason": "",
        "max_frame_dt_s": float(ANIMATOR_MAX_FRAME_DT_S),
        "max_frame_distance_step_m": float(ANIMATOR_MAX_FRAME_DS_M),
        "max_export_points": int(ANIMATOR_MAX_EXPORT_POINTS),
    }
    if df_main is None or len(df_main) < 2:
        diag["reason"] = "insufficient_rows"
        return None, diag
    t = _table_time_vector(df_main)
    if t.size < 2:
        diag["reason"] = "missing_time"
        return None, diag
    dt = np.diff(t)
    dt = dt[np.isfinite(dt) & (dt > 1e-9)]
    if dt.size == 0:
        diag["reason"] = "invalid_time_step"
        return None, diag
    source_points = int(t.size)
    duration = float(t[-1] - t[0])
    if duration <= 0.0:
        diag["reason"] = "nonpositive_duration"
        return None, diag
    diag["source_points"] = source_points
    diag["source_median_dt_s"] = float(np.median(dt))
    diag["source_max_dt_s"] = float(np.max(dt))

    speed = None
    try:
        if {"скорость_vx_м_с", "скорость_vy_м_с"}.issubset(df_main.columns):
            vx = np.asarray(df_main["скорость_vx_м_с"], dtype=float)
            vy = np.asarray(df_main["скорость_vy_м_с"], dtype=float)
            speed = np.hypot(vx, vy)
        elif "скорость_vx_м_с" in df_main.columns:
            speed = np.abs(np.asarray(df_main["скорость_vx_м_с"], dtype=float))
    except Exception:
        speed = None
    vmax = float(np.nanmax(speed)) if speed is not None and np.isfinite(np.nanmax(speed)) else 0.0
    if (not np.isfinite(vmax)) or vmax <= 1e-9:
        try:
            vmax = float(meta.get("ring_nominal_speed_max_mps") or meta.get("vx0_м_с") or 0.0) if isinstance(meta, dict) else 0.0
        except Exception:
            vmax = 0.0
    vmax = float(max(0.0, vmax))
    diag["vmax_mps"] = vmax

    source_max_ds = 0.0
    if speed is not None and speed.size >= 2:
        ds = np.asarray(speed[:-1], dtype=float) * np.asarray(np.diff(t), dtype=float)
        ds = ds[np.isfinite(ds)]
        if ds.size:
            source_max_ds = float(np.max(np.abs(ds)))
    diag["source_max_distance_step_m"] = source_max_ds

    dt_limit_s = float(ANIMATOR_MAX_FRAME_DT_S)
    ds_limit_s = float(ANIMATOR_MAX_FRAME_DS_M / vmax) if vmax > 1e-9 else float("inf")
    target_dt = float(min(float(np.median(dt)), dt_limit_s, ds_limit_s))
    target_dt = float(max(1e-4, target_dt))
    need_dt = float(np.median(dt)) > (dt_limit_s * 1.02)
    need_ds = source_max_ds > (float(ANIMATOR_MAX_FRAME_DS_M) * 1.05)
    if not need_dt and not need_ds:
        diag["reason"] = "already_dense_enough"
        return None, diag

    target_points = int(np.ceil(duration / target_dt)) + 1
    if target_points <= source_points:
        diag["reason"] = "target_not_larger_than_source"
        return None, diag
    if target_points > int(ANIMATOR_MAX_EXPORT_POINTS):
        target_points = int(ANIMATOR_MAX_EXPORT_POINTS)
        target_dt = float(duration / max(1, target_points - 1))
    if target_points <= source_points:
        diag["reason"] = "target_capped_to_source"
        return None, diag

    t_new = np.linspace(float(t[0]), float(t[-1]), target_points, dtype=float)
    diag.update({
        "enabled": True,
        "target_points": int(target_points),
        "target_dt_s": float(target_dt),
        "reason": "max_dt_and_distance_step_cap",
    })
    return t_new, diag


def _densify_animator_tables(
    df_main: pd.DataFrame,
    df_p: Optional[pd.DataFrame],
    df_q: Optional[pd.DataFrame],
    df_open: Optional[pd.DataFrame],
    meta: Optional[Dict[str, Any]],
) -> Tuple[pd.DataFrame, Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame], Dict[str, Any]]:
    t_new, diag = _build_animator_dense_time_grid(df_main, meta)
    if t_new is None:
        return df_main, df_p, df_q, df_open, diag
    return (
        _resample_dataframe_for_animator(df_main, t_new),
        _resample_dataframe_for_animator(df_p, t_new),
        _resample_dataframe_for_animator(df_q, t_new),
        _resample_dataframe_for_animator(df_open, t_new, force_step=True),
        diag,
    )


def _df_to_numpy(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Convert a DataFrame to (cols, values) for NPZ.

    Goals:
      - preserve column order
      - coerce values to float where possible
      - tolerate mixed dtypes (best-effort)
    """
    if df is None:
        return np.array([], dtype=str), np.zeros((0, 0), dtype=float)
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
    cols = np.array([str(c) for c in df.columns], dtype=str)

    try:
        values = df.to_numpy(dtype=float, copy=True)
    except Exception:
        tmp = {}
        for c in df.columns:
            s = df[c]
            try:
                tmp[c] = pd.to_numeric(s, errors="coerce")
            except Exception:
                try:
                    tmp[c] = pd.to_numeric(s.astype(str), errors="coerce")
                except Exception:
                    tmp[c] = pd.Series([np.nan] * len(df))
        values = pd.DataFrame(tmp).to_numpy(dtype=float, copy=True)

    # Preserve NaN as-is (results must reflect model output).
    # Replace +/-inf with NaN (cannot be represented meaningfully downstream).
    try:
        values = values.astype(float, copy=False)
        values[~np.isfinite(values)] = np.nan
    except Exception:
        pass
    return cols, values


def _coerce_jsonable(x: Any) -> Any:
    """Best-effort conversion of arbitrary Python objects to JSON-safe values."""
    if x is None:
        return None
    if isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, bytes):
        try:
            return x.decode("utf-8", errors="ignore")
        except Exception:
            return str(x)
    if isinstance(x, Path):
        return str(x)
    if is_dataclass(x):
        try:
            return _coerce_jsonable(asdict(x))
        except Exception:
            return str(x)

    # numpy scalar
    try:
        if hasattr(x, "shape") and getattr(x, "shape", None) == ():
            return _coerce_jsonable(x.item())
    except Exception:
        pass

    if isinstance(x, np.ndarray):
        try:
            if x.size <= 2000:
                return [_coerce_jsonable(v) for v in x.tolist()]
        except Exception:
            pass
        return str(x)

    if isinstance(x, (list, tuple)):
        return [_coerce_jsonable(v) for v in x]
    if isinstance(x, dict):
        return {str(k): _coerce_jsonable(v) for k, v in x.items()}
    return str(x)


def _normalize_meta(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Thin wrapper (kept for module-local API)."""
    return normalize_npz_meta(meta)


def _safe_json_dumps(meta: Dict[str, Any]) -> str:
    """Thin wrapper (kept for module-local API)."""
    return dumps_meta_json(meta)


def _copy_sidecar(src: Any, dst: Path) -> Optional[str]:
    """Copy sidecar file if it exists. Return dst.name if copied."""
    if not src:
        return None
    try:
        p = Path(str(src)).expanduser()
        if not p.is_absolute():
            # Streamlit/launcher могут менять CWD; пробуем несколько базовых директорий.
            bases = [
                Path.cwd(),
                Path(__file__).resolve().parents[1],  # корень приложения (PneumoApp_v6_80)
                Path(__file__).resolve().parent,      # папка pneumo_solver_ui
            ]
            found = None
            for b in bases:
                cand = (b / p).resolve()
                if cand.exists():
                    found = cand
                    break
            p = found if found is not None else (Path.cwd() / p).resolve()
        if not p.exists() or not p.is_file():
            return None
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
        return dst.name
    except Exception:
        return None



def _should_mirror_global_anim_pointer(exports_dir: Path, *, explicit: Optional[bool] = None) -> bool:
    """Decide whether export_anim_latest_bundle may update the global anim pointer.

    Absolute-law intent: only the canonical workspace export path may mutate the
    durable global pointer automatically. Ad-hoc exports (pytest temp dirs,
    offline inspections, manual copies) must not poison workspace/_pointers.
    """
    if explicit is not None:
        return bool(explicit)
    raw_ws = os.environ.get("PNEUMO_WORKSPACE_DIR", "").strip()
    if not raw_ws:
        return False
    try:
        expected = (Path(raw_ws).expanduser().resolve() / "exports").resolve()
        actual = Path(exports_dir).expanduser().resolve()
        return actual == expected
    except Exception:
        return False


def export_full_log_to_npz(
    npz_path: str | Path,
    df_main: pd.DataFrame,
    *,
    df_p: Optional[pd.DataFrame] = None,
    df_q: Optional[pd.DataFrame] = None,
    df_open: Optional[pd.DataFrame] = None,
    meta: Optional[Dict[str, Any]] = None,
    require_geometry_contract: bool = False,
    require_solver_points_contract: bool = False,
) -> Path:
    """Export dataframes into NPZ bundle."""
    npz_path = Path(npz_path)
    npz_path.parent.mkdir(parents=True, exist_ok=True)

    meta_norm = _normalize_meta(meta)
    if require_solver_points_contract:
        assert_required_solver_points_contract(
            df_main,
            context=f"NPZ export {npz_path.name} df_main",
            log=logging.warning,
        )
    if require_geometry_contract:
        meta_norm = assert_required_geometry_meta(
            meta_norm,
            context=f"NPZ export {npz_path.name} meta_json",
            log=logging.warning,
            require_nested=True,
        )

    main_cols, main_values = _df_to_numpy(df_main)
    p_cols, p_values = _df_to_numpy(df_p) if df_p is not None else (np.array([], dtype=str), np.zeros((0, 0), dtype=float))
    q_cols, q_values = _df_to_numpy(df_q) if df_q is not None else (np.array([], dtype=str), np.zeros((0, 0), dtype=float))
    open_cols, open_values = _df_to_numpy(df_open) if df_open is not None else (np.array([], dtype=str), np.zeros((0, 0), dtype=float))

    meta_json = _safe_json_dumps(meta_norm)

    np.savez_compressed(
        npz_path,
        main_cols=main_cols,
        main_values=main_values,
        p_cols=p_cols,
        p_values=p_values,
        q_cols=q_cols,
        q_values=q_values,
        open_cols=open_cols,
        open_values=open_values,
        meta_json=np.array(meta_json, dtype=str),
    )
    return npz_path


def export_anim_latest_bundle(
    *,
    exports_dir: str | Path,
    df_main: pd.DataFrame,
    df_p: Optional[pd.DataFrame] = None,
    df_q: Optional[pd.DataFrame] = None,
    df_open: Optional[pd.DataFrame] = None,
    meta: Optional[Dict[str, Any]] = None,
    mirror_global_pointer: Optional[bool] = None,
) -> Tuple[Path, Path]:
    """Export anim_latest bundle for Desktop Animator.

    Creates:
      - <exports_dir>/anim_latest.npz
      - <exports_dir>/anim_latest.json  (pointer)

    Additionally, if meta contains sidecars (road_csv/axay_csv/scenario_json), they are
    copied into <exports_dir>/ and meta is rewritten to relative names.
    """
    exports_dir = Path(exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    try:
        assert_required_solver_points_contract(
            df_main,
            context="anim_latest export df_main",
            log=logging.warning,
        )
    except Exception as exc:
        logging.warning("[anim_latest] solver-point contract failed: %s", exc)
        raise

    meta_norm = _normalize_meta(meta)
    meta_norm = assert_required_geometry_meta(
        meta_norm,
        context="anim_latest export meta_json",
        log=logging.warning,
        require_nested=True,
    )
    try:
        geom_in = meta_norm.get("geometry") if isinstance(meta_norm.get("geometry"), dict) else {}
        geom_out = supplement_animator_geometry_meta(geom_in, log=logging.warning)
        if geom_out:
            meta_norm["geometry"] = dict(geom_out)
    except Exception as exc:
        logging.warning("[anim_latest] failed to supplement geometry meta for %s: %s", exports_dir, exc)

    sidecars = {
        "road_csv": exports_dir / "anim_latest_road_csv.csv",
        "axay_csv": exports_dir / "anim_latest_axay_csv.csv",
        "scenario_json": exports_dir / "anim_latest_scenario_json.json",
    }
    for k, dst in sidecars.items():
        copied = _copy_sidecar(meta_norm.get(k), dst)
        if copied:
            meta_norm[k] = copied  # store relative name

    df_main_anim, df_p_anim, df_q_anim, df_open_anim, animator_frame_diag = _densify_animator_tables(
        df_main,
        df_p,
        df_q,
        df_open,
        meta_norm,
    )
    try:
        meta_norm["animator_frame_export"] = dict(animator_frame_diag)
    except Exception:
        pass

    df_main_anim, length_repair = ensure_cylinder_length_columns(
        df_main_anim,
        log=logging.warning,
    )
    try:
        meta_norm["anim_export_length_repair"] = dict(length_repair)
    except Exception:
        pass
    meta_norm = augment_anim_latest_meta(
        meta_norm,
        df_main=df_main_anim,
        length_repair=length_repair,
    )
    contract_validation = validate_anim_export_contract_meta(meta_norm)
    try:
        validation_summary = dict(contract_validation.get("summary") or {})
        validation_summary["validation_level"] = str(contract_validation.get("level") or "")
        meta_norm["anim_export_validation"] = validation_summary
        meta_norm["anim_export_contract_artifacts"] = {
            "sidecar": ANIM_EXPORT_CONTRACT_SIDECAR_NAME,
            "validation_json": ANIM_EXPORT_CONTRACT_VALIDATION_JSON_NAME,
            "validation_md": ANIM_EXPORT_CONTRACT_VALIDATION_MD_NAME,
            "hardpoints_source_of_truth": HARDPOINTS_SOURCE_OF_TRUTH_JSON_NAME,
            "cylinder_packaging_passport": CYLINDER_PACKAGING_PASSPORT_JSON_NAME,
            "road_contract_web": ROAD_CONTRACT_WEB_JSON_NAME,
            "road_contract_desktop": ROAD_CONTRACT_DESKTOP_JSON_NAME,
        }
        meta_norm["anim_export_truth_ready"] = bool(str(contract_validation.get("level") or "") == "PASS")
    except Exception:
        pass

    npz_path = exports_dir / "anim_latest.npz"
    export_full_log_to_npz(
        npz_path,
        df_main_anim,
        df_p=df_p_anim,
        df_q=df_q_anim,
        df_open=df_open_anim,
        meta=meta_norm,
        require_geometry_contract=True,
        require_solver_points_contract=True,
    )

    pointer_path = exports_dir / "anim_latest.json"
    updated_utc = datetime.now(timezone.utc).isoformat()
    reload_diag = build_visual_reload_diagnostics(
        npz_path,
        meta=meta_norm,
        context="anim_latest export pointer",
        log=logging.warning,
    )
    pointer = {
        "schema_version": ANIM_LATEST_POINTER_SCHEMA_VERSION,
        "updated_utc": updated_utc,
        "npz_path": str(npz_path.resolve()),
        "meta": meta_norm,
        "visual_cache_token": reload_diag.get("visual_cache_token", ""),
        "visual_reload_inputs": list(reload_diag.get("inputs") or []),
        "visual_cache_dependencies": dict(reload_diag.get("visual_cache_dependencies") or {}),
        "anim_export_validation_level": str((contract_validation.get("level") or "")),
        "anim_export_truth_ready": bool(str(contract_validation.get("level") or "") == "PASS"),
    }
    pointer_path.write_text(json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8")

    contract_artifacts = {}
    try:
        contract_artifacts = write_anim_export_contract_artifacts(
            exports_dir,
            meta=meta_norm,
            updated_utc=updated_utc,
            npz_path=npz_path,
            pointer_path=pointer_path,
        )
    except Exception as exc:
        logging.warning("[anim_latest] failed to write anim export contract artifacts for %s: %s", exports_dir, exc)

    road_contract_artifacts = {}
    try:
        road_contract_artifacts = write_road_contract_artifacts(
            exports_dir,
            df_main_or_columns=df_main_anim,
            meta=meta_norm,
            npz_path=npz_path,
            pointer_path=pointer_path,
            updated_utc=updated_utc,
            time_vector=_table_time_vector(df_main_anim),
            log=logging.warning,
        )
    except Exception as exc:
        logging.warning("[anim_latest] failed to write road contract artifacts for %s: %s", exports_dir, exc)

    mirrored_global_pointer = False
    if _should_mirror_global_anim_pointer(exports_dir, explicit=mirror_global_pointer):
        try:
            from .run_artifacts import save_latest_animation_ptr

            save_latest_animation_ptr(npz_path=npz_path, pointer_json=pointer_path, meta=meta_norm)
            mirrored_global_pointer = True
        except Exception as exc:
            logging.warning("[anim_latest] failed to mirror global pointer for %s: %s", exports_dir, exc)

    # Debug trace (helps diagnose “ничего не передалось в аниматор”)
    try:
        trace = {
            "ts_utc": updated_utc,
            "npz_path": str(npz_path),
            "exports_dir": str(exports_dir),
            "pointer_path": str(pointer_path),
            "pointer": pointer,
            "meta": meta_norm,
            "visual_reload_diagnostics": reload_diag,
            "anim_export_contract": {
                "level": str(contract_validation.get("level") or ""),
                "summary": dict(contract_validation.get("summary") or {}),
                "artifacts": {k: v for k, v in dict(contract_artifacts or {}).items() if k != "report"},
            },
            "road_contract": {
                "artifacts": {
                    k: v
                    for k, v in dict(road_contract_artifacts or {}).items()
                    if k not in {"road_contract_web", "road_contract_desktop"}
                },
                "web": dict((road_contract_artifacts or {}).get("road_contract_web") or {}),
                "desktop": dict((road_contract_artifacts or {}).get("road_contract_desktop") or {}),
            },
            "mirrored_global_pointer": mirrored_global_pointer,
        }
        (exports_dir / "anim_latest_trace.json").write_text(
            json.dumps(trace, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        # best effort only
        pass
    return npz_path, pointer_path
