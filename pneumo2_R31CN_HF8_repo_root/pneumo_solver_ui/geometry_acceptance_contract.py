# -*- coding: utf-8 -*-
"""Shared geometry acceptance summary helpers.

This module computes a lightweight, serializable acceptance summary for the
canonical solver-point geometry contract:

- frame_corner_<corner>_{x,y,z}_м
- wheel_center_<corner>_{x,y,z}_м
- road_contact_<corner>_{x,y,z}_м

No synthetic geometry is reconstructed here. The goal is to surface contract
health in Compare/Validation UIs and send-bundle summaries without depending on
Desktop Animator runtime classes.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Mapping

import numpy as np
import pandas as pd

CORNERS: tuple[str, ...] = ("ЛП", "ПП", "ЛЗ", "ПЗ")
GEOMETRY_ACCEPTANCE_JSON_NAME = "geometry_acceptance_report.json"
GEOMETRY_ACCEPTANCE_MD_NAME = "geometry_acceptance_report.md"
_FAIL_METRICS: tuple[tuple[str, str], ...] = (
    ("max_invariant_err_m", "Σ"),
    ("max_scalar_err_wheel_frame_m", "WF"),
    ("max_scalar_err_wheel_road_m", "WR"),
    ("max_scalar_err_frame_road_m", "FR"),
)
_GATE_RANK = {"MISSING": 0, "PASS": 1, "WARN": 2, "FAIL": 3}


def _nanmax_abs(arr: np.ndarray | None) -> float:
    if arr is None:
        return 0.0
    try:
        a = np.asarray(arr, dtype=float)
        if a.size == 0:
            return 0.0
        mask = np.isfinite(a)
        if not np.any(mask):
            return 0.0
        return float(np.nanmax(np.abs(a[mask])))
    except Exception:
        return 0.0


def _nanmin(arr: np.ndarray | None) -> float | None:
    if arr is None:
        return None
    try:
        a = np.asarray(arr, dtype=float)
        if a.size == 0:
            return None
        mask = np.isfinite(a)
        if not np.any(mask):
            return None
        return float(np.nanmin(a[mask]))
    except Exception:
        return None


def _safe_float(v: Any) -> float | None:
    try:
        out = float(v)
    except Exception:
        return None
    return out if np.isfinite(out) else None


def _ensure_df(frame_or_mapping: Any) -> pd.DataFrame:
    if isinstance(frame_or_mapping, pd.DataFrame):
        return frame_or_mapping
    if isinstance(frame_or_mapping, Mapping):
        try:
            return pd.DataFrame(dict(frame_or_mapping))
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def _series(df: pd.DataFrame, name: str) -> np.ndarray | None:
    if name not in df.columns:
        return None
    try:
        arr = np.asarray(df[name], dtype=float)
    except Exception:
        return None
    if arr.ndim == 0:
        return None
    return arr


def _triplet(df: pd.DataFrame, prefix: str, corner: str) -> tuple[np.ndarray | None, list[str]]:
    cols = [f"{prefix}_{corner}_x_м", f"{prefix}_{corner}_y_м", f"{prefix}_{corner}_z_м"]
    arrays = [_series(df, c) for c in cols]
    missing = [c for c, a in zip(cols, arrays) if a is None]
    if missing:
        return None, missing
    assert all(a is not None for a in arrays)
    n = min(len(arrays[0]), len(arrays[1]), len(arrays[2]))
    if n <= 0:
        return None, cols
    xyz = np.column_stack([arrays[0][:n], arrays[1][:n], arrays[2][:n]]).astype(float, copy=False)
    return xyz, []


def _trim_scalar_to(actual: np.ndarray, scalar: np.ndarray | None) -> np.ndarray | None:
    if scalar is None:
        return None
    n = min(len(actual), len(scalar))
    if n <= 0:
        return None
    return np.asarray(scalar[:n], dtype=float) - np.asarray(actual[:n], dtype=float)


def _missing_preview(names: List[str], *, limit: int = 2) -> str:
    if not names:
        return ""
    uniq = list(dict.fromkeys(str(x) for x in names if str(x).strip()))
    if not uniq:
        return ""
    preview = ", ".join(uniq[:limit])
    if len(uniq) > limit:
        preview += f", +{len(uniq) - limit}"
    return preview


def _enrich_gate_fields(summary: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(summary or {})
    tol = _safe_float(out.get("tol_m"))
    tol = tol if tol is not None else 1e-6
    corners_in = dict(out.get("corners") or {})
    corners_out: Dict[str, Dict[str, Any]] = {}
    min_fr_corner: str | None = None
    min_wr_corner: str | None = None
    min_fr_value: float | None = None
    min_wr_value: float | None = None

    worst_gate = "MISSING"
    worst_corner = ""
    worst_metric = ""
    worst_value_m: float | None = None
    worst_reason = ""

    def _register_worst(gate: str, corner: str, metric: str, value_m: float | None, reason: str) -> None:
        nonlocal worst_gate, worst_corner, worst_metric, worst_value_m, worst_reason
        rank = _GATE_RANK.get(gate, 0)
        best_rank = _GATE_RANK.get(worst_gate, 0)
        value_cmp = abs(value_m) if value_m is not None else -1.0
        best_cmp = abs(worst_value_m) if worst_value_m is not None else -1.0
        if rank > best_rank or (rank == best_rank and value_cmp > best_cmp):
            worst_gate = gate
            worst_corner = str(corner)
            worst_metric = str(metric)
            worst_value_m = value_m if value_m is None else float(value_m)
            worst_reason = str(reason)

    for corner in CORNERS:
        item = dict(corners_in.get(corner) or {})
        missing = [str(x) for x in (item.get("missing_triplets") or []) if str(x).strip()]
        fr_min = _safe_float(item.get("frame_road_min_m"))
        wr_min = _safe_float(item.get("wheel_road_min_m"))
        inv = _safe_float(item.get("max_invariant_err_m")) or 0.0
        xy = _safe_float(item.get("max_xy_err_m")) or 0.0
        fr_err = _safe_float(item.get("max_scalar_err_frame_road_m")) or 0.0
        wr_err = _safe_float(item.get("max_scalar_err_wheel_road_m")) or 0.0
        wf_err = _safe_float(item.get("max_scalar_err_wheel_frame_m")) or 0.0

        if fr_min is not None and (min_fr_value is None or fr_min < min_fr_value):
            min_fr_value = fr_min
            min_fr_corner = corner
        if wr_min is not None and (min_wr_value is None or wr_min < min_wr_value):
            min_wr_value = wr_min
            min_wr_corner = corner

        gate = "PASS"
        reason = "solver-point contract consistent"
        metric = ""
        metric_value: float | None = 0.0
        if missing:
            gate = "WARN"
            metric = "missing_triplets"
            metric_value = None
            reason = f"missing triplets: {_missing_preview(missing)}"
        else:
            fail_candidates = [
                (label, _safe_float(item.get(key)) or 0.0)
                for key, label in _FAIL_METRICS
                if (_safe_float(item.get(key)) or 0.0) > tol
            ]
            if fail_candidates:
                metric, metric_value = max(fail_candidates, key=lambda kv: abs(float(kv[1])))
                gate = "FAIL"
                reason = f"{metric} mismatch {float(metric_value) * 1000.0:.3f} мм"
            elif xy > tol:
                gate = "WARN"
                metric = "XY"
                metric_value = float(xy)
                reason = f"wheel-road XY mismatch {float(metric_value) * 1000.0:.3f} мм"

        item["gate"] = gate
        item["level"] = {"PASS": "ok", "WARN": "warn", "FAIL": "fail", "MISSING": "missing"}.get(gate, "missing")
        item["reason"] = reason
        item["worst_metric"] = metric
        item["worst_value_m"] = metric_value
        corners_out[corner] = item
        _register_worst(gate, corner, metric or "ok", metric_value, reason)

    available = bool(out.get("available", False))
    missing_all = [str(x) for x in (out.get("missing_triplets") or []) if str(x).strip()]
    fail_present = any(str(dict(v).get("gate") or "") == "FAIL" for v in corners_out.values())
    warn_present = any(str(dict(v).get("gate") or "") == "WARN" for v in corners_out.values())

    if not available:
        release_gate = "MISSING"
        release_reason = "solver-point triplet-ы отсутствуют"
        dominant_kind = "missing"
        worst_corner = ""
        worst_metric = "missing"
        worst_value_m = None
    elif fail_present:
        release_gate = "FAIL"
        release_reason = f"{worst_corner}: {worst_reason}" if worst_corner and worst_reason else "нарушен Z/scalar-инвариант"
        dominant_kind = "fail"
    elif missing_all:
        release_gate = "WARN"
        release_reason = f"missing triplets: {_missing_preview(missing_all)}"
        dominant_kind = "missing_triplets"
        if not worst_corner:
            worst_corner = str(next(iter(corners_out.keys()), ""))
            worst_metric = "missing_triplets"
            worst_value_m = None
    elif warn_present:
        release_gate = "WARN"
        release_reason = f"{worst_corner}: {worst_reason}" if worst_corner and worst_reason else "wheel-road XY mismatch"
        dominant_kind = "warn"
    else:
        release_gate = "PASS"
        release_reason = "solver-point contract consistent"
        dominant_kind = "pass"
        worst_corner = ""
        worst_metric = "ok"
        worst_value_m = 0.0

    out["corners"] = corners_out
    out["min_frame_road_corner"] = min_fr_corner
    out["min_wheel_road_corner"] = min_wr_corner
    out["release_gate"] = release_gate
    out["release_gate_reason"] = release_reason
    out["worst_corner"] = worst_corner
    out["worst_metric"] = worst_metric
    out["worst_value_m"] = worst_value_m
    out["dominant_kind"] = dominant_kind
    out["corner_gates"] = {c: str(dict(v).get("gate") or "MISSING") for c, v in corners_out.items()}
    return out


def build_geometry_acceptance_rows(summary: Mapping[str, Any]) -> List[Dict[str, Any]]:
    enriched = _enrich_gate_fields(summary)
    rows: List[Dict[str, Any]] = []
    for corner in CORNERS:
        item = dict(dict(enriched.get("corners") or {}).get(corner) or {})
        if not item:
            continue
        rows.append({
            "угол": str(corner),
            "gate": str(item.get("gate") or "MISSING"),
            "reason": str(item.get("reason") or ""),
            "рама‑дорога min, м": item.get("frame_road_min_m"),
            "колесо‑дорога min, м": item.get("wheel_road_min_m"),
            "Σ err, мм": float(item.get("max_invariant_err_m", 0.0) or 0.0) * 1000.0 if item.get("max_invariant_err_m") is not None else None,
            "XY wheel-road err, мм": float(item.get("max_xy_err_m", 0.0) or 0.0) * 1000.0 if item.get("max_xy_err_m") is not None else None,
            "XY frame-wheel offset, мм": float(item.get("max_xy_frame_wheel_offset_m", 0.0) or 0.0) * 1000.0 if item.get("max_xy_frame_wheel_offset_m") is not None else None,
            "XY frame-road offset, мм": float(item.get("max_xy_frame_road_offset_m", 0.0) or 0.0) * 1000.0 if item.get("max_xy_frame_road_offset_m") is not None else None,
            "WF err, мм": float(item.get("max_scalar_err_wheel_frame_m", 0.0) or 0.0) * 1000.0 if item.get("max_scalar_err_wheel_frame_m") is not None else None,
            "WR err, мм": float(item.get("max_scalar_err_wheel_road_m", 0.0) or 0.0) * 1000.0 if item.get("max_scalar_err_wheel_road_m") is not None else None,
            "FR err, мм": float(item.get("max_scalar_err_frame_road_m", 0.0) or 0.0) * 1000.0 if item.get("max_scalar_err_frame_road_m") is not None else None,
            "missing": ", ".join(str(x) for x in (item.get("missing_triplets") or [])),
        })
    return rows


def build_geometry_acceptance_report(
    summary: Mapping[str, Any],
    *,
    updated_utc: str = "",
    npz_path: str | Path | None = None,
    pointer_path: str | Path | None = None,
    source_label: str = "anim_latest export",
) -> Dict[str, Any]:
    """Build the producer-side evidence object required by PB-001/GAP-006.

    The report is intentionally derived only from exported solver-point columns:
    no hardpoints, road traces, or scalar clearances are reconstructed here.
    """
    enriched = _enrich_gate_fields(summary)
    gate = str(enriched.get("release_gate") or "MISSING")
    available = bool(enriched.get("available", False))
    missing_fields = list(dict.fromkeys(str(x) for x in (enriched.get("missing_triplets") or []) if str(x).strip()))
    warnings: list[str] = []
    if gate in {"WARN", "FAIL", "MISSING"}:
        reason = str(enriched.get("release_gate_reason") or "geometry acceptance is incomplete")
        warnings.append(reason)
    if missing_fields:
        warnings.append("missing producer-side fields: " + _missing_preview(missing_fields, limit=8))

    if gate == "PASS":
        graphics_truth_state = "solver_confirmed"
        inspection_status = "ok"
    elif available:
        graphics_truth_state = "approximate_inferred_with_warning"
        inspection_status = "warning" if gate == "WARN" else "fail"
    else:
        graphics_truth_state = "unavailable"
        inspection_status = "missing"

    report: Dict[str, Any] = {
        "schema": "geometry_acceptance_report.v1",
        "updated_utc": str(updated_utc or ""),
        "source_label": str(source_label or ""),
        "npz_path": str(npz_path or ""),
        "pointer_path": str(pointer_path or ""),
        "inspection_status": inspection_status,
        "truth_state_summary": {
            "graphics_truth_state": graphics_truth_state,
            "release_gate": gate,
            "release_gate_reason": str(enriched.get("release_gate_reason") or ""),
            "available": available,
            "ok": bool(enriched.get("ok", False)),
            "producer_owned": True,
            "no_synthetic_geometry": True,
        },
        "missing_fields": missing_fields,
        "warnings": list(dict.fromkeys(str(x) for x in warnings if str(x).strip())),
        "summary": dict(enriched),
        "rows": build_geometry_acceptance_rows(enriched),
        "summary_lines": format_geometry_acceptance_summary_lines(enriched, label=source_label),
    }
    return report


def render_geometry_acceptance_report_md(report: Mapping[str, Any] | None) -> str:
    rep = dict(report or {})
    truth = dict(rep.get("truth_state_summary") or {}) if isinstance(rep.get("truth_state_summary"), Mapping) else {}
    lines = [
        "# geometry acceptance report",
        "",
        f"- inspection_status: **{rep.get('inspection_status') or 'missing'}**",
        f"- graphics_truth_state: {truth.get('graphics_truth_state') or 'unavailable'}",
        f"- release_gate: {truth.get('release_gate') or 'MISSING'}",
        f"- producer_owned: {truth.get('producer_owned')}",
        f"- no_synthetic_geometry: {truth.get('no_synthetic_geometry')}",
    ]
    reason = str(truth.get("release_gate_reason") or "").strip()
    if reason:
        lines.append(f"- release_gate_reason: {reason}")
    missing = [str(x) for x in (rep.get("missing_fields") or []) if str(x).strip()]
    if missing:
        lines.extend(["", "## missing producer-side fields", *[f"- {x}" for x in missing]])
    warnings = [str(x) for x in (rep.get("warnings") or []) if str(x).strip()]
    if warnings:
        lines.extend(["", "## warnings", *[f"- {x}" for x in warnings]])
    summary_lines = [str(x) for x in (rep.get("summary_lines") or []) if str(x).strip()]
    if summary_lines:
        lines.extend(["", "## summary", *[f"- {x}" for x in summary_lines]])
    return "\n".join(lines).rstrip() + "\n"


def write_geometry_acceptance_artifacts(
    exports_dir: str | Path,
    *,
    frame_or_mapping: Any,
    updated_utc: str = "",
    npz_path: str | Path | None = None,
    pointer_path: str | Path | None = None,
    source_label: str = "anim_latest export",
    tol_m: float = 1e-6,
) -> Dict[str, Any]:
    exports = Path(exports_dir)
    exports.mkdir(parents=True, exist_ok=True)
    summary = collect_geometry_acceptance_from_frame(frame_or_mapping, tol_m=tol_m)
    report = build_geometry_acceptance_report(
        summary,
        updated_utc=updated_utc,
        npz_path=npz_path,
        pointer_path=pointer_path,
        source_label=source_label,
    )
    json_path = exports / GEOMETRY_ACCEPTANCE_JSON_NAME
    md_path = exports / GEOMETRY_ACCEPTANCE_MD_NAME
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_geometry_acceptance_report_md(report), encoding="utf-8")
    return {
        "geometry_acceptance_json_path": str(json_path),
        "geometry_acceptance_md_path": str(md_path),
        "geometry_acceptance_report": report,
    }


def collect_geometry_acceptance_from_frame(frame_or_mapping: Any, *, tol_m: float = 1e-6) -> Dict[str, Any]:
    """Return serializable acceptance summary from a main dataframe/mapping."""
    df = _ensure_df(frame_or_mapping)
    if df.empty:
        return _enrich_gate_fields({
            "available": False,
            "ok": False,
            "level": "missing",
            "tol_m": float(tol_m),
            "missing_triplets": [],
            "corners": {},
            "frame_road_min_m": None,
            "wheel_road_min_m": None,
            "max_invariant_err_m": 0.0,
            "max_xy_err_m": 0.0,
            "max_xy_frame_wheel_offset_m": 0.0,
            "max_xy_frame_road_offset_m": 0.0,
            "max_scalar_err_frame_road_m": 0.0,
            "max_scalar_err_wheel_road_m": 0.0,
            "max_scalar_err_wheel_frame_m": 0.0,
        })

    any_relevant = any(
        str(c).startswith(("frame_corner_", "wheel_center_", "road_contact_"))
        for c in df.columns
    )
    missing_all: list[str] = []
    corners: Dict[str, Dict[str, Any]] = {}
    frame_road_global_min: float | None = None
    wheel_road_global_min: float | None = None
    max_inv = 0.0
    max_xy = 0.0
    max_xy_fw = 0.0
    max_xy_fr = 0.0
    max_fr = 0.0
    max_wr = 0.0
    max_wf = 0.0

    for corner in CORNERS:
        frame_xyz, missing_frame = _triplet(df, "frame_corner", corner)
        wheel_xyz, missing_wheel = _triplet(df, "wheel_center", corner)
        road_xyz, missing_road = _triplet(df, "road_contact", corner)
        missing = list(missing_frame + missing_wheel + missing_road)
        if missing:
            if any(
                c in df.columns
                for c in [
                    f"frame_corner_{corner}_z_м",
                    f"wheel_center_{corner}_z_м",
                    f"road_contact_{corner}_z_м",
                    f"рама_относительно_дороги_{corner}_м",
                    f"колесо_относительно_дороги_{corner}_м",
                    f"колесо_относительно_рамы_{corner}_м",
                ]
            ):
                any_relevant = True
            missing_all.extend(missing)
            corners[corner] = {
                "ok": False,
                "missing_triplets": missing,
                "frame_road_min_m": None,
                "wheel_road_min_m": None,
                "max_invariant_err_m": None,
                "max_xy_err_m": None,
                    "max_xy_frame_wheel_offset_m": None,
                    "max_xy_frame_road_offset_m": None,
                "max_scalar_err_frame_road_m": None,
                "max_scalar_err_wheel_road_m": None,
                "max_scalar_err_wheel_frame_m": None,
            }
            continue

        assert frame_xyz is not None and wheel_xyz is not None and road_xyz is not None
        any_relevant = True
        n = min(len(frame_xyz), len(wheel_xyz), len(road_xyz))
        frame_xyz = np.asarray(frame_xyz[:n], dtype=float)
        wheel_xyz = np.asarray(wheel_xyz[:n], dtype=float)
        road_xyz = np.asarray(road_xyz[:n], dtype=float)

        frame_road = frame_xyz[:, 2] - road_xyz[:, 2]
        wheel_road = wheel_xyz[:, 2] - road_xyz[:, 2]
        wheel_frame = wheel_xyz[:, 2] - frame_xyz[:, 2]
        invariant = wheel_road - (wheel_frame + frame_road)

        xy_fw = np.linalg.norm(frame_xyz[:, :2] - wheel_xyz[:, :2], axis=1)
        xy_wr = np.linalg.norm(wheel_xyz[:, :2] - road_xyz[:, :2], axis=1)
        xy_fr = np.linalg.norm(frame_xyz[:, :2] - road_xyz[:, :2], axis=1)

        scalar_fr = _series(df, f"рама_относительно_дороги_{corner}_м")
        scalar_wr = _series(df, f"колесо_относительно_дороги_{corner}_м")
        scalar_wf = _series(df, f"колесо_относительно_рамы_{corner}_м")

        scalar_err_fr = _trim_scalar_to(frame_road, scalar_fr)
        scalar_err_wr = _trim_scalar_to(wheel_road, scalar_wr)
        scalar_err_wf = _trim_scalar_to(wheel_frame, scalar_wf)

        corner_fr_min = _nanmin(frame_road)
        corner_wr_min = _nanmin(wheel_road)
        corner_inv = _nanmax_abs(invariant)
        # Acceptance gate must stay strict only for wheel_center <-> road_contact
        # XY consistency. frame_corner is a distinct structural solver point and
        # may legitimately have an XY offset relative to wheel/road.
        corner_xy = _nanmax_abs(xy_wr)
        corner_xy_fw = _nanmax_abs(xy_fw)
        corner_xy_fr = _nanmax_abs(xy_fr)
        corner_fr_err = _nanmax_abs(scalar_err_fr)
        corner_wr_err = _nanmax_abs(scalar_err_wr)
        corner_wf_err = _nanmax_abs(scalar_err_wf)

        if corner_fr_min is not None:
            frame_road_global_min = corner_fr_min if frame_road_global_min is None else min(frame_road_global_min, corner_fr_min)
        if corner_wr_min is not None:
            wheel_road_global_min = corner_wr_min if wheel_road_global_min is None else min(wheel_road_global_min, corner_wr_min)

        max_inv = max(max_inv, corner_inv)
        max_xy = max(max_xy, corner_xy)
        max_xy_fw = max(max_xy_fw, corner_xy_fw)
        max_xy_fr = max(max_xy_fr, corner_xy_fr)
        max_fr = max(max_fr, corner_fr_err)
        max_wr = max(max_wr, corner_wr_err)
        max_wf = max(max_wf, corner_wf_err)

        corners[corner] = {
            "ok": (corner_inv <= float(tol_m)) and (corner_fr_err <= float(tol_m)) and (corner_wr_err <= float(tol_m)) and (corner_wf_err <= float(tol_m)),
            "missing_triplets": [],
            "frame_road_min_m": corner_fr_min,
            "wheel_road_min_m": corner_wr_min,
            "max_invariant_err_m": corner_inv,
            "max_xy_err_m": corner_xy,
            "max_xy_frame_wheel_offset_m": corner_xy_fw,
            "max_xy_frame_road_offset_m": corner_xy_fr,
            "max_scalar_err_frame_road_m": corner_fr_err,
            "max_scalar_err_wheel_road_m": corner_wr_err,
            "max_scalar_err_wheel_frame_m": corner_wf_err,
        }

    missing_all = list(dict.fromkeys(str(x) for x in missing_all if str(x).strip()))
    z_fail = max(max_inv, max_fr, max_wr, max_wf) > float(tol_m)
    xy_warn = max_xy > float(tol_m)
    if not any_relevant:
        level = "missing"
    elif z_fail:
        level = "fail"
    elif missing_all:
        level = "warn"
    elif xy_warn:
        level = "warn"
    else:
        level = "ok"

    return _enrich_gate_fields({
        "available": bool(any_relevant),
        "ok": bool(any_relevant and not missing_all and not z_fail and not xy_warn),
        "level": level,
        "tol_m": float(tol_m),
        "missing_triplets": missing_all,
        "corners": corners,
        "frame_road_min_m": frame_road_global_min,
        "wheel_road_min_m": wheel_road_global_min,
        "max_invariant_err_m": float(max_inv),
        "max_xy_err_m": float(max_xy),
        "max_xy_frame_wheel_offset_m": float(max_xy_fw),
        "max_xy_frame_road_offset_m": float(max_xy_fr),
        "max_scalar_err_frame_road_m": float(max_fr),
        "max_scalar_err_wheel_road_m": float(max_wr),
        "max_scalar_err_wheel_frame_m": float(max_wf),
    })


def _main_df_from_npz(npz_source: Any) -> pd.DataFrame:
    closer = None
    try:
        if isinstance(npz_source, (str, Path)):
            npz = np.load(Path(npz_source).expanduser().resolve(), allow_pickle=True)
        elif isinstance(npz_source, (bytes, bytearray)):
            npz = np.load(BytesIO(npz_source), allow_pickle=True)
        else:
            npz = np.load(npz_source, allow_pickle=True)
        closer = getattr(npz, "close", None)
        if "main_cols" not in npz or "main_values" not in npz:
            return pd.DataFrame()
        cols = [str(c) for c in npz["main_cols"].tolist()]
        vals = np.asarray(npz["main_values"])
        try:
            return pd.DataFrame(vals, columns=cols)
        except Exception:
            return pd.DataFrame(vals)
    except Exception:
        return pd.DataFrame()
    finally:
        if callable(closer):
            try:
                closer()
            except Exception:
                pass


def collect_geometry_acceptance_from_npz(npz_source: Any, *, tol_m: float = 1e-6) -> Dict[str, Any]:
    return collect_geometry_acceptance_from_frame(_main_df_from_npz(npz_source), tol_m=tol_m)


def format_geometry_acceptance_summary_lines(summary: Mapping[str, Any], *, label: str = "") -> List[str]:
    enriched = _enrich_gate_fields(summary)
    prefix = f"[{label}] " if str(label).strip() else ""
    gate = str(enriched.get("release_gate") or "MISSING")
    reason = str(enriched.get("release_gate_reason") or "")
    available = bool(enriched.get("available", False))
    if not available:
        return [prefix + f"Геом.acceptance gate={gate}: {reason}"]

    fr_min = _safe_float(enriched.get("frame_road_min_m"))
    wr_min = _safe_float(enriched.get("wheel_road_min_m"))
    fr_corner = str(enriched.get("min_frame_road_corner") or "—")
    wr_corner = str(enriched.get("min_wheel_road_corner") or "—")
    inv_mm = float(enriched.get("max_invariant_err_m", 0.0) or 0.0) * 1000.0
    xy_mm = float(enriched.get("max_xy_err_m", 0.0) or 0.0) * 1000.0
    xy_fw_mm = float(enriched.get("max_xy_frame_wheel_offset_m", 0.0) or 0.0) * 1000.0
    xy_fr_mm = float(enriched.get("max_xy_frame_road_offset_m", 0.0) or 0.0) * 1000.0
    wf_mm = float(enriched.get("max_scalar_err_wheel_frame_m", 0.0) or 0.0) * 1000.0
    wr_mm = float(enriched.get("max_scalar_err_wheel_road_m", 0.0) or 0.0) * 1000.0
    fr_mm = float(enriched.get("max_scalar_err_frame_road_m", 0.0) or 0.0) * 1000.0
    worst_corner = str(enriched.get("worst_corner") or "—")
    worst_metric = str(enriched.get("worst_metric") or "—")
    worst_value_m = _safe_float(enriched.get("worst_value_m"))
    worst_value_mm_txt = "—" if worst_value_m is None else f"{float(worst_value_m) * 1000.0:.3f} мм"
    lines = [prefix + f"Геом.acceptance gate={gate}: {reason}"]
    if fr_min is not None or wr_min is not None:
        lines.append(
            prefix + f"Геом.acceptance: рама‑дорога min {float(fr_min or 0.0):+.3f} м ({fr_corner})  колесо‑дорога min {float(wr_min or 0.0):+.3f} м ({wr_corner})"
        )
    lines.append(
        prefix + f"Геом.acceptance max: Σ {inv_mm:.3f} мм  XYwr {xy_mm:.3f} мм  XYfw/XYfr {xy_fw_mm:.3f}/{xy_fr_mm:.3f} мм  WF/WR/FR {wf_mm:.3f}/{wr_mm:.3f}/{fr_mm:.3f} мм"
    )
    lines.append(prefix + f"Геом.acceptance worst: {worst_corner}  metric={worst_metric}  value={worst_value_mm_txt}")
    return lines
