from __future__ import annotations

import argparse
import json
from pathlib import Path

from pneumo_solver_ui.desktop_animator.data_bundle import load_npz
from pneumo_solver_ui.desktop_animator.suspension_geometry_diagnostics import collect_suspension_geometry_status


def main() -> int:
    ap = argparse.ArgumentParser(description='Inspect suspension geometry in anim_latest/NPZ bundle.')
    ap.add_argument('npz', help='Path to anim_latest.npz')
    ap.add_argument('--json', dest='json_out', default='', help='Optional JSON report path')
    ns = ap.parse_args()

    bundle = load_npz(Path(ns.npz))
    status = collect_suspension_geometry_status(bundle)

    print('# Suspension geometry diagnostics')
    print(f"ok: {status.get('ok')}")
    for row in status.get('rows') or []:
        print(
            f"- {row['corner']}: arms={row['arm_geometries_present']}/{row['expected_arm_geometries']}, "
            f"arm_joint_delta_max={row.get('max_lower_upper_joint_delta_m', 0.0):.6f} m, "
            f"cyl_channels={row['cylinder_channels_present']}, distinct_axes={row['distinct_cylinder_axes']}, "
            f"coincident_arms={row.get('coincident_arm_joints')}, coincident_cyl={row['coincident_cylinder_axes']}"
        )
    for msg in status.get('issues') or []:
        print(f"WARN: {msg}")

    if ns.json_out:
        out = Path(ns.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"wrote: {out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
