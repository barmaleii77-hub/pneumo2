from __future__ import annotations

from pathlib import Path
import numpy as np

from pneumo_solver_ui.desktop_animator.geom3d_helpers import (
    derive_wheel_pose_from_hardpoints,
    ellipse_mesh_on_plane,
)

ROOT = Path(__file__).resolve().parents[1]


def test_derive_wheel_pose_from_hardpoints_uses_explicit_hub_points() -> None:
    fallback = np.array([0.75, 0.50, 0.30], dtype=float)
    lf = np.array([0.79, 0.48, 0.25], dtype=float)
    lr = np.array([0.71, 0.48, 0.25], dtype=float)
    uf = np.array([0.79, 0.52, 0.35], dtype=float)
    ur = np.array([0.71, 0.52, 0.35], dtype=float)
    center, axle, fwd, up, toe_rad, camber_rad = derive_wheel_pose_from_hardpoints(
        fallback_center_xyz=fallback,
        lower_front_xyz=lf,
        lower_rear_xyz=lr,
        upper_front_xyz=uf,
        upper_rear_xyz=ur,
    )
    assert np.isclose(center[0], 0.75)
    assert np.isclose(center[1], 0.50)
    assert np.isclose(center[2], fallback[2])
    assert np.isfinite(toe_rad)
    assert np.isfinite(camber_rad)
    assert axle.shape == (3,)
    assert fwd.shape == (3,)
    assert up.shape == (3,)


def test_ellipse_mesh_on_plane_builds_nonempty_geometry() -> None:
    verts, faces = ellipse_mesh_on_plane(
        center_xyz=np.array([0.0, 0.0, 0.0], dtype=float),
        axis_u_xyz=np.array([1.0, 0.0, 0.0], dtype=float),
        axis_v_xyz=np.array([0.0, 1.0, 0.0], dtype=float),
        radius_u_m=0.12,
        radius_v_m=0.08,
        segments=16,
    )
    assert verts.shape[1] == 3
    assert faces.shape[1] == 3
    assert verts.shape[0] > 8
    assert faces.shape[0] >= 8
    # All points must lie in z=0 plane for the canonical XY test case.
    assert np.allclose(verts[:, 2], 0.0)


def test_start_cmd_no_longer_uses_pause() -> None:
    cmd_text = (ROOT / 'START_PNEUMO_APP.cmd').read_text(encoding='utf-8', errors='replace').lower()
    assert 'pause' not in cmd_text
    assert ('pythonw' in cmd_text) or ('pyw' in cmd_text)


def test_desktop_animator_spawns_use_no_console_on_windows() -> None:
    txt1 = (ROOT / 'pneumo_solver_ui' / 'pneumo_ui_app.py').read_text(encoding='utf-8', errors='replace')
    txt2 = (ROOT / 'pneumo_solver_ui' / 'app.py').read_text(encoding='utf-8', errors='replace')
    txt3 = (ROOT / 'pneumo_solver_ui' / 'pages' / '08_DesktopAnimator.py').read_text(encoding='utf-8', errors='replace')
    txt4 = (ROOT / 'pneumo_solver_ui' / 'ui_process_helpers.py').read_text(encoding='utf-8', errors='replace')
    assert 'CREATE_NO_WINDOW' in txt4
    assert 'start_background_worker' in txt1
    assert 'start_worker(cmd, cwd=HERE)' in txt2 or 'start_background_worker' in txt2
    assert '_spawn_no_console' in txt3
