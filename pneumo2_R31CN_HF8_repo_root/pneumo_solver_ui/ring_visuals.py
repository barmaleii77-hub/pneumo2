from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np

from .scenario_ring import generate_ring_tracks, summarize_ring_track_segments, generate_ring_drive_profile


_SEGMENT_PALETTE = [
    "#3b82f6",  # blue
    "#f97316",  # orange
    "#10b981",  # emerald
    "#ef4444",  # red
    "#8b5cf6",  # violet
    "#eab308",  # amber
    "#06b6d4",  # cyan
    "#f43f5e",  # rose
]


def _json_load(path: Path) -> Optional[dict]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _candidate_paths(raw: str, *, base_dir: Optional[Path] = None) -> Iterable[Path]:
    p = Path(str(raw))
    if p.is_absolute():
        yield p
        return
    if base_dir is not None:
        yield (base_dir / p).resolve()
    yield p.resolve()


def load_ring_spec_from_test_cfg(test_cfg: Dict[str, Any] | None, *, base_dir: Optional[Path] = None) -> Optional[dict]:
    if not isinstance(test_cfg, dict):
        return None
    inner = test_cfg.get("test") if isinstance(test_cfg.get("test"), dict) else test_cfg
    if not isinstance(inner, dict):
        return None
    if isinstance(inner.get("scenario_spec"), dict):
        spec = dict(inner["scenario_spec"])
        if isinstance(spec.get("segments"), list):
            return spec
    raw = str(inner.get("scenario_json") or "").strip()
    if raw:
        for cand in _candidate_paths(raw, base_dir=base_dir):
            if cand.exists():
                spec = _json_load(cand)
                if isinstance(spec, dict) and isinstance(spec.get("segments"), list):
                    return spec
    return None


def load_ring_spec_from_npz(npz_path: str | Path) -> Optional[dict]:
    npz_path = Path(npz_path)
    candidates = [
        npz_path.with_name(npz_path.stem + "_scenario_json.json"),
        npz_path.parent / "anim_latest_scenario_json.json",
    ]
    for cand in candidates:
        if cand.exists():
            spec = _json_load(cand)
            if isinstance(spec, dict) and isinstance(spec.get("segments"), list):
                return spec
    return None


def _segment_curvature_signed(seg: Dict[str, Any]) -> float:
    drive_mode = str(seg.get("drive_mode") or "").strip().upper()
    if drive_mode not in {"TURN_LEFT", "TURN_RIGHT"}:
        return 0.0
    try:
        r = float(seg.get("turn_radius_m") or 0.0)
    except Exception:
        r = 0.0
    if not np.isfinite(r) or r <= 0.0:
        return 0.0
    sign = 1.0 if drive_mode == "TURN_LEFT" else -1.0
    return sign / r


def build_ring_visual_payload_from_spec(
    spec: Dict[str, Any],
    *,
    track_m: float,
    wheel_width_m: float,
    seed: int = 0,
) -> Optional[Dict[str, Any]]:
    if not isinstance(spec, dict) or not isinstance(spec.get("segments"), list):
        return None

    spec_vis = dict(spec)
    spec_vis["closure_policy"] = "closed_c1_periodic"
    dx_m = float(spec_vis.get("dx_m", 0.02) or 0.02)
    tracks = generate_ring_tracks(spec_vis, dx_m=dx_m, seed=int(seed))
    rows = summarize_ring_track_segments(spec_vis, tracks)

    x = np.asarray(tracks.get("x_m", []), dtype=float).reshape(-1)
    z_l = np.asarray(tracks.get("zL_m", []), dtype=float).reshape(-1)
    z_r = np.asarray(tracks.get("zR_m", []), dtype=float).reshape(-1)
    if x.size < 4 or z_l.size != x.size or z_r.size != x.size:
        return None

    road_width_m = float(max(track_m + 2.0 * max(0.0, wheel_width_m), track_m * 1.35, 0.8))
    road_half_width_m = 0.5 * road_width_m
    ring_length_m = float(tracks.get("meta", {}).get("L_total_m", x[-1] - x[0]) or (x[-1] - x[0]))
    if not np.isfinite(ring_length_m) or ring_length_m <= 0.0:
        return None
    ring_radius_m = ring_length_m / (2.0 * math.pi)

    segments_out = []
    curv = np.zeros_like(x, dtype=float)
    curv_signed = np.zeros_like(x, dtype=float)
    segs = list(spec.get("segments") or [])
    for i, row in enumerate(rows):
        seg_src = segs[i] if i < len(segs) and isinstance(segs[i], dict) else {}
        kappa_signed = float(_segment_curvature_signed(seg_src))
        x0 = float(row.get("x_start_m", 0.0) or 0.0)
        x1 = float(row.get("x_end_m", x0) or x0)
        mask = (x >= x0 - 1e-9) & (x <= x1 + 1e-9)
        curv_signed[mask] = kappa_signed
        curv[mask] = abs(kappa_signed)
        segments_out.append(
            {
                "seg_idx": int(row.get("seg_idx", i + 1) or (i + 1)),
                "name": str(row.get("name") or f"S{i+1}"),
                "drive_mode": str(row.get("drive_mode") or ""),
                "road_mode": str(row.get("road_mode") or ""),
                "x_start_m": x0,
                "x_end_m": x1,
                "length_m": float(row.get("length_m", max(0.0, x1 - x0)) or max(0.0, x1 - x0)),
                "edge_color": _SEGMENT_PALETTE[i % len(_SEGMENT_PALETTE)],
                "curvature_signed_m_inv": kappa_signed,
                "curvature_abs_m_inv": abs(kappa_signed),
            }
        )

    curvature_max = float(np.nanmax(curv)) if curv.size else 0.0
    grid_step_m = float(max(0.2, min(road_width_m / 4.0, 1.0)))
    edge_step_m = float(max(0.05, min(dx_m * 2.0, 0.2)))

    return {
        "mode": "ring_closed_circle",
        "closure_policy": str(tracks.get("meta", {}).get("closure_policy") or "closed_c1_periodic"),
        "source_closure_policy": str(spec.get("closure_policy") or ""),
        "ring_length_m": ring_length_m,
        "ring_radius_m": ring_radius_m,
        "road_width_m": road_width_m,
        "road_half_width_m": road_half_width_m,
        "grid_step_m": grid_step_m,
        "edge_step_m": edge_step_m,
        "x_m": x.astype(float).tolist(),
        "z_left_m": z_l.astype(float).tolist(),
        "z_right_m": z_r.astype(float).tolist(),
        "curvature_abs_m_inv": curv.astype(float).tolist(),
        "curvature_signed_m_inv": curv_signed.astype(float).tolist(),
        "curvature_max_m_inv": curvature_max,
        "segments": segments_out,
        "meta": dict(tracks.get("meta") or {}),
    }



def build_nominal_ring_progress_from_spec(spec: Dict[str, Any], time_s: Iterable[float]) -> Dict[str, Any]:
    t = np.asarray(list(time_s), dtype=float).reshape(-1)
    if t.size == 0:
        return {"t_s": [], "distance_m": [], "v_mps": []}
    if t.size >= 2:
        dt_s = float(np.nanmedian(np.diff(t)))
    else:
        dt_s = float(spec.get("dt_s", 0.01) or 0.01)
    prof = generate_ring_drive_profile(spec, dt_s=max(1e-4, dt_s), n_laps=1)
    tp = np.asarray(prof.get("t_s", []), dtype=float).reshape(-1)
    sp = np.asarray(prof.get("distance_m", []), dtype=float).reshape(-1)
    vp = np.asarray(prof.get("v_mps", []), dtype=float).reshape(-1)
    if tp.size == 0 or sp.size != tp.size or vp.size != tp.size:
        return {"t_s": t.astype(float).tolist(), "distance_m": np.zeros_like(t).tolist(), "v_mps": np.zeros_like(t).tolist()}
    s_i = np.interp(t, tp, sp, left=float(sp[0]), right=float(sp[-1]))
    v_i = np.interp(t, tp, vp, left=float(vp[0]), right=float(vp[-1]))
    return {"t_s": t.astype(float).tolist(), "distance_m": s_i.astype(float).tolist(), "v_mps": v_i.astype(float).tolist()}

def build_segment_ranges_from_progress(
    ring_visual: Dict[str, Any],
    s_values: Iterable[float],
) -> list[Dict[str, Any]]:
    """Build contiguous sample-index ranges for authored ring segments.

    This is used by animator playhead/timeline overlays so segment colors live in
    the *real animator cockpit*, not as yet another big debug graph.
    """
    if not isinstance(ring_visual, dict):
        return []
    segs_in = list(ring_visual.get("segments") or [])
    if not segs_in:
        return []
    try:
        ring_len = float(ring_visual.get("ring_length_m") or 0.0)
    except Exception:
        ring_len = 0.0
    if not np.isfinite(ring_len) or ring_len <= 0.0:
        return []

    s_arr = np.asarray(list(s_values), dtype=float).reshape(-1)
    if s_arr.size == 0:
        return []

    segs = []
    for jj, seg in enumerate(segs_in):
        if not isinstance(seg, dict):
            continue
        try:
            x0 = float(seg.get("x_start_m") or 0.0)
            x1 = float(seg.get("x_end_m") or x0)
        except Exception:
            continue
        if not np.isfinite(x0) or not np.isfinite(x1) or x1 < x0:
            continue
        segs.append((x0, x1, dict(seg), jj))
    segs.sort(key=lambda item: item[0])
    if not segs:
        return []

    try:
        max_seg_end = max(float(item[1]) for item in segs)
    except Exception:
        max_seg_end = ring_len
    if np.all(np.diff(s_arr) >= -1e-9) and np.nanmax(s_arr) <= (max_seg_end + max(1e-6, 1e-3 * max_seg_end)):
        s_mod = np.asarray(s_arr, dtype=float)
    else:
        s_mod = np.mod(s_arr, ring_len)
        try:
            end_eps = max(1e-9, 1e-6 * ring_len)
            end_mask = (np.abs(s_mod) <= end_eps) & (s_arr > end_eps)
            s_mod[end_mask] = ring_len
        except Exception:
            pass

    labels = np.full(s_mod.shape, fill_value=-1, dtype=int)
    eps = 1e-9
    for ii, sval in enumerate(s_mod.tolist()):
        for kk, (x0, x1, _seg, _jj) in enumerate(segs):
            is_last = (kk == len(segs) - 1)
            if sval >= x0 - eps and (sval < x1 - eps or (is_last and sval <= x1 + eps)):
                labels[ii] = kk
                break
        if labels[ii] < 0:
            labels[ii] = len(segs) - 1

    out: list[Dict[str, Any]] = []
    cur = int(labels[0])
    start = 0
    for ii in range(1, labels.size + 1):
        if ii < labels.size and int(labels[ii]) == cur:
            continue
        x0, x1, seg, _jj = segs[cur]
        out.append({
            "seg_idx": int(seg.get("seg_idx", cur + 1) or (cur + 1)),
            "name": str(seg.get("name") or f"S{cur+1}"),
            "color": str(seg.get("edge_color") or _SEGMENT_PALETTE[cur % len(_SEGMENT_PALETTE)]),
            "edge_color": str(seg.get("edge_color") or _SEGMENT_PALETTE[cur % len(_SEGMENT_PALETTE)]),
            "idx0": int(start),
            "idx1": int(ii - 1),
            "x_start_m": float(x0),
            "x_end_m": float(x1),
        })
        if ii < labels.size:
            cur = int(labels[ii])
            start = ii
    return out


def _sample_signed_curvature_at_s(ring_visual: Dict[str, Any], s_values: np.ndarray) -> np.ndarray:
    segs = list(ring_visual.get("segments") or [])
    L = float(ring_visual.get("ring_length_m") or 0.0)
    if L <= 0.0 or len(segs) == 0:
        return np.zeros_like(s_values, dtype=float)
    s_mod = np.mod(np.asarray(s_values, dtype=float), L)
    out = np.zeros_like(s_mod, dtype=float)
    for seg in segs:
        try:
            x0 = float(seg.get("x_start_m") or 0.0)
            x1 = float(seg.get("x_end_m") or x0)
            kappa = float(seg.get("curvature_signed_m_inv") or 0.0)
        except Exception:
            continue
        mask = (s_mod >= x0 - 1e-9) & (s_mod <= x1 + 1e-9)
        out[mask] = kappa
    return out


def embed_path_payload_on_ring(
    path_payload: Dict[str, Any],
    ring_visual: Dict[str, Any],
    *,
    wheelbase_m: float,
) -> Dict[str, Any]:
    if not isinstance(path_payload, dict):
        return path_payload
    s = np.asarray(path_payload.get("s", []), dtype=float).reshape(-1)
    if s.size == 0:
        v = np.asarray(path_payload.get("v", []), dtype=float).reshape(-1)
        if v.size:
            s = np.cumsum(v)
        else:
            return path_payload
    L = float(ring_visual.get("ring_length_m") or 0.0)
    R = float(ring_visual.get("ring_radius_m") or 0.0)
    if L <= 0.0 or R <= 0.0:
        return path_payload

    s_mod = np.mod(s, L)
    theta = 2.0 * math.pi * s_mod / L
    x = R * np.sin(theta)
    z = -R * np.cos(theta)
    yaw = theta

    kappa_signed = _sample_signed_curvature_at_s(ring_visual, s_mod)
    steer = np.arctan(np.clip(float(wheelbase_m) * kappa_signed, -5.0, 5.0))

    out = dict(path_payload)
    out["x"] = x.astype(float).tolist()
    out["z"] = z.astype(float).tolist()
    out["yaw"] = yaw.astype(float).tolist()
    out["s"] = s.astype(float).tolist()
    if "v" in path_payload:
        out["v"] = np.asarray(path_payload.get("v", []), dtype=float).astype(float).tolist()
    out["steer"] = steer.astype(float).tolist()
    out["ring_mode"] = True
    return out
