"""CLI helper to run desktop animator self-checks on an exported NPZ.

Usage (Windows PowerShell / cmd):
  python -m pneumo_solver_ui.desktop_animator.selfcheck_cli path\\to\\export.npz

This script does NOT require Qt GUI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

from pneumo_solver_ui.data_contract import read_visual_geometry_meta
from pneumo_solver_ui.visual_contract import collect_visual_contract_status

from .data_bundle import load_npz
from .self_checks import run_self_checks


def _safe_float(x: Any, default: float) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)


def infer_geometry_headless(meta: Dict[str, Any]) -> Dict[str, float]:
    """Infer geometry values without importing Qt-heavy modules.

    Reads only canonical nested ``meta_json.geometry``. No fallback to top-level/base
    geometry is allowed for new bundles.
    """
    if not isinstance(meta, dict):
        meta = {}

    vis_geom = read_visual_geometry_meta(
        meta,
        context="Desktop Animator NPZ meta_json",
    )

    return {
        "wheelbase_m": _safe_float(vis_geom.get("wheelbase_m"), 0.0),
        "track_m": _safe_float(vis_geom.get("track_m"), 0.0),
        "wheel_radius_m": _safe_float(vis_geom.get("wheel_radius_m"), 0.0),
        "wheel_width_m": _safe_float(vis_geom.get("wheel_width_m"), 0.0),
        "frame_length_m": _safe_float(vis_geom.get("frame_length_m"), 0.0),
        "frame_width_m": _safe_float(vis_geom.get("frame_width_m"), 0.0),
        "frame_height_m": _safe_float(vis_geom.get("frame_height_m"), 0.0),
        "geometry_contract_issues": list(vis_geom.get("issues") or []),
        "geometry_contract_warnings": list(vis_geom.get("warnings") or []),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print('Usage: python -m pneumo_solver_ui.desktop_animator.selfcheck_cli path/to/export.npz')
        return 2

    path = Path(argv[1]).expanduser().resolve()
    if not path.exists():
        print(f'File not found: {path}')
        return 2

    b = load_npz(path)
    geom = infer_geometry_headless(getattr(b, 'meta', {}) or {})
    visual_contract = dict((getattr(b, "meta", {}) or {}).get("_visual_contract") or {})
    if not visual_contract:
        visual_contract = collect_visual_contract_status(
            getattr(b.main, "cols", []),
            meta=getattr(b, "meta", {}) or {},
            npz_path=path,
            time_vector=getattr(b, "t", None),
            context="Desktop Animator NPZ",
        )

    rep = run_self_checks(
        b,
        wheel_radius_m=geom['wheel_radius_m'],
        track_m=geom['track_m'],
        wheelbase_m=geom['wheelbase_m'],
    )

    print('=== Self-check report ===')
    print(f'Level: {rep.level}')
    print(f'OK: {rep.ok}')
    if geom.get("geometry_contract_issues"):
        print("\n--- geometry contract ---")
        for m in geom["geometry_contract_issues"]:
            print(m)
    if visual_contract.get("road_overlay_text") or visual_contract.get("solver_points_overlay_text"):
        print("\n--- visual contract ---")
        if visual_contract.get("road_overlay_text"):
            print(visual_contract["road_overlay_text"])
        if visual_contract.get("solver_points_overlay_text"):
            print(visual_contract["solver_points_overlay_text"])

    for m in rep.messages:
        print(m)

    if rep.stats:
        print('\n--- stats ---')
        for k in sorted(rep.stats.keys()):
            print(f'{k}: {rep.stats[k]}')

    return 0 if rep.ok else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
