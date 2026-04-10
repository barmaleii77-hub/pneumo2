from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np


def _candidate_paths(raw: Any, *, base_dirs: Iterable[Path] | None = None) -> Iterable[Path]:
    if raw is None:
        return
    s = str(raw).strip()
    if not s:
        return
    p = Path(s)
    if p.is_absolute():
        yield p
        return
    seen: set[str] = set()
    for base in list(base_dirs or []) + [Path.cwd()]:
        try:
            cand = (Path(base) / p).resolve()
            key = str(cand)
            if key not in seen:
                seen.add(key)
                yield cand
        except Exception:
            continue
    try:
        cand = p.resolve()
        key = str(cand)
        if key not in seen:
            yield cand
    except Exception:
        pass


def resolve_existing_path(raw: Any, *, base_dirs: Iterable[Path] | None = None) -> Optional[Path]:
    for cand in _candidate_paths(raw, base_dirs=base_dirs):
        try:
            if cand.exists():
                return cand
        except Exception:
            continue
    return None


def _json_load(path: Path) -> Optional[dict]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def infer_ring_scenario_json_path(
    *,
    scenario_json: Any = None,
    road_csv: Any = None,
    axay_csv: Any = None,
    base_dirs: Iterable[Path] | None = None,
) -> Optional[Path]:
    direct = resolve_existing_path(scenario_json, base_dirs=base_dirs)
    if direct is not None and direct.is_file():
        return direct

    for raw in (road_csv, axay_csv):
        src = resolve_existing_path(raw, base_dirs=base_dirs)
        if src is None or not src.exists():
            continue
        parent = src.parent
        name = src.name
        candidates: list[Path] = []
        if name.endswith("_road.csv"):
            candidates.append(parent / name.replace("_road.csv", "_spec.json"))
        if name.endswith("_axay.csv"):
            candidates.append(parent / name.replace("_axay.csv", "_spec.json"))
        stem = src.stem
        if stem.endswith("_road"):
            candidates.append(parent / (stem[:-5] + "_spec.json"))
        if stem.endswith("_axay"):
            candidates.append(parent / (stem[:-5] + "_spec.json"))
        # generic siblings for ring generator outputs
        candidates.extend([
            parent / "scenario_spec.json",
            parent / "scenario.json",
        ])
        for cand in candidates:
            try:
                if cand.exists() and cand.is_file():
                    spec = _json_load(cand)
                    if isinstance(spec, dict) and isinstance(spec.get("segments"), list):
                        return cand
            except Exception:
                continue
    return None


def _resolve_effective_ring_v0_kph(spec: Dict[str, Any]) -> float:
    try:
        from .scenario_ring import _resolve_initial_speed_kph  # canonical helper inside package

        v0_kph = float(_resolve_initial_speed_kph(spec))
        if np.isfinite(v0_kph) and v0_kph > 0.0:
            return v0_kph
    except Exception:
        pass
    return 0.0


def _nominal_ring_speed_stats(spec: Dict[str, Any]) -> Dict[str, float]:
    try:
        from .scenario_ring import generate_ring_drive_profile

        dt_s = float(spec.get("dt_s", 0.02) or 0.02)
        if not np.isfinite(dt_s) or dt_s <= 0.0:
            dt_s = 0.02
        dt_s = float(min(max(dt_s, 0.01), 0.25))
        n_laps = int(spec.get("n_laps", 1) or 1)
        prof = generate_ring_drive_profile(spec, dt_s=dt_s, n_laps=max(1, n_laps))
        v = np.asarray(prof.get("v_mps", []), dtype=float).reshape(-1)
        v = v[np.isfinite(v)]
        if v.size:
            return {
                "ring_nominal_speed_min_mps": float(np.min(v)),
                "ring_nominal_speed_max_mps": float(np.max(v)),
                "ring_nominal_speed_mean_mps": float(np.mean(v)),
            }
    except Exception:
        pass
    return {}


def _ring_closure_meta(spec: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from .scenario_ring import generate_ring_tracks

        dx_m = float(spec.get("dx_m", 0.02) or 0.02)
        if not np.isfinite(dx_m) or dx_m <= 0.0:
            dx_m = 0.02
        dx_m = float(min(max(dx_m, 1e-4), 0.25))
        seed_raw = spec.get("seed", None)
        try:
            seed = None if seed_raw is None else int(seed_raw)
        except Exception:
            seed = None
        tracks = generate_ring_tracks(spec, dx_m=dx_m, seed=seed)
        meta = dict(tracks.get("meta") or {})
        return {
            "ring_closure_policy": str(meta.get("closure_policy") or ""),
            "ring_closure_applied": bool(meta.get("closure_applied", False)),
            "ring_seam_open": bool(meta.get("seam_open", False)),
            "ring_seam_max_jump_m": float(meta.get("seam_max_jump_m", 0.0) or 0.0),
            "ring_raw_seam_max_jump_m": float(meta.get("raw_seam_max_jump_m", 0.0) or 0.0),
        }
    except Exception:
        pass
    return {}


def extract_anim_sidecar_meta(
    test_cfg: Any,
    *,
    base_dirs: Iterable[Path] | None = None,
    log: Any = logging.warning,
) -> Dict[str, Any]:
    """Extract portable anim-sidecar meta from a suite test.

    Key goals:
    - preserve road/axay/scenario sidecars for anim_latest export;
    - infer missing ring scenario_json next to generated road/axay sidecars;
    - enforce canonical ring initial speed in exported meta (`vx0_м_с`);
    - avoid geometry aliases / bridges.
    """
    if not isinstance(test_cfg, dict):
        return {}

    inner = test_cfg.get("test") if isinstance(test_cfg.get("test"), dict) else test_cfg
    if not isinstance(inner, dict):
        return {}

    m: Dict[str, Any] = {}

    road_csv = inner.get("road_csv")
    axay_csv = inner.get("axay_csv")
    scenario_json = inner.get("scenario_json")

    resolved_road = resolve_existing_path(road_csv, base_dirs=base_dirs)
    resolved_axay = resolve_existing_path(axay_csv, base_dirs=base_dirs)
    resolved_scenario = infer_ring_scenario_json_path(
        scenario_json=scenario_json,
        road_csv=road_csv,
        axay_csv=axay_csv,
        base_dirs=base_dirs,
    )

    if resolved_road is not None:
        m["road_csv"] = str(resolved_road)
    elif road_csv:
        m["road_csv"] = road_csv
    if resolved_axay is not None:
        m["axay_csv"] = str(resolved_axay)
    elif axay_csv:
        m["axay_csv"] = axay_csv
    if resolved_scenario is not None:
        m["scenario_json"] = str(resolved_scenario)
    elif scenario_json:
        m["scenario_json"] = scenario_json

    if inner.get("scenario_kind"):
        m["scenario_kind"] = inner.get("scenario_kind")
    if inner.get("type"):
        m["test_type"] = inner.get("type")

    # Generic scenario/road params.
    for k in (
        "road_len_m",
        "road_dx_m",
        "road_class",
        "road_seed",
        "left_right_coherence",
    ):
        if k in inner and inner.get(k) is not None:
            m[k] = inner.get(k)

    spec = _json_load(resolved_scenario) if resolved_scenario is not None else None
    if isinstance(spec, dict) and isinstance(spec.get("segments"), list):
        m["scenario_kind"] = "ring"
        v0_kph = _resolve_effective_ring_v0_kph(spec)
        if v0_kph > 0.0:
            vx0_mps = float(v0_kph / 3.6)
            prev_vx = inner.get("vx0_м_с")
            try:
                prev_vx_f = float(prev_vx) if prev_vx is not None else float("nan")
            except Exception:
                prev_vx_f = float("nan")
            # For ring exports canonical speed must come from the authored ring spec.
            if not np.isfinite(prev_vx_f) or prev_vx_f <= 0.0 or abs(prev_vx_f - vx0_mps) > 1e-9:
                try:
                    log(
                        "[ANIM_META] ring scenario overrides/export-fixes vx0_м_с -> %.6f m/s (suite had %r)",
                        vx0_mps,
                        prev_vx,
                    )
                except Exception:
                    pass
            m["vx0_м_с"] = vx0_mps
            m["ring_v0_kph"] = float(v0_kph)
            m["ring_v0_mps"] = float(vx0_mps)
        m.update(_nominal_ring_speed_stats(spec))
        m.update(_ring_closure_meta(spec))
        m["ring_speed_profile_source"] = "scenario_json"
    elif inner.get("vx0_м_с") is not None:
        m["vx0_м_с"] = inner.get("vx0_м_с")

    return m
