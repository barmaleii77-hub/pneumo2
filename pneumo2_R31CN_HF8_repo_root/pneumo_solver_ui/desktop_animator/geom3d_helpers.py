# -*- coding: utf-8 -*-
"""Pure helpers for 3D animator geometry.

ABSOLUTE LAW
------------
- Keep canonical project basis unchanged: x forward, y left, z up.
- No hidden render-axis remapping.
- Any visual transform must be explicit and testable.
"""
from __future__ import annotations

from functools import lru_cache
import math
import numpy as np


def _quantize_display_count(count: int, *, quantum: int, min_count: int, max_count: int) -> int:
    """Keep presentation topology in stable buckets to avoid frame-to-frame churn."""
    q = int(max(1, quantum))
    lo = int(max(1, min_count))
    hi = int(max(lo, max_count))
    value = int(max(lo, min(hi, count)))
    if value <= lo or value >= hi:
        return value
    bucket = int(q * round(float(value) / float(q)))
    return int(max(lo, min(hi, bucket)))


def car_frame_rotate_xy(x: np.ndarray | float, y: np.ndarray | float, yaw_rad: float) -> tuple[np.ndarray, np.ndarray]:
    """Rotate world XY into local car frame (yaw removed).

    Canonical project basis is preserved strictly:
      x — вперёд, y — влево, z — вверх.
    We do NOT remap axes for rendering; we only remove yaw in the XY plane.
    """
    c = math.cos(-float(yaw_rad))
    s = math.sin(-float(yaw_rad))
    xx = np.asarray(x, dtype=float)
    yy = np.asarray(y, dtype=float)
    return c * xx - s * yy, s * xx + c * yy


def localize_world_points_to_car_frame(points_xyz: np.ndarray, *, x0: float, y0: float, yaw_rad: float) -> np.ndarray:
    """Convert world-space points (N,3) or (3,) into local car frame.

    Only XY is rotated; Z stays vertical and unchanged.
    """
    pts = np.asarray(points_xyz, dtype=float)
    if pts.ndim == 1:
        pts = pts.reshape(1, 3)
    out = np.asarray(pts, dtype=float).copy()
    lx, ly = car_frame_rotate_xy(out[:, 0] - float(x0), out[:, 1] - float(y0), float(yaw_rad))
    out[:, 0] = lx
    out[:, 1] = ly
    return out


def localize_world_point_to_car_frame(point_xyz: np.ndarray, *, x0: float, y0: float, yaw_rad: float) -> np.ndarray:
    """Fast path for a single world-space point -> local car frame."""
    pt = np.asarray(point_xyz, dtype=float).reshape(3)
    c = math.cos(-float(yaw_rad))
    s = math.sin(-float(yaw_rad))
    dx = float(pt[0]) - float(x0)
    dy = float(pt[1]) - float(y0)
    return np.asarray(
        [
            (c * dx) - (s * dy),
            (s * dx) + (c * dy),
            float(pt[2]),
        ],
        dtype=float,
    )


def orthonormal_frame_from_corners(lp: np.ndarray, pp: np.ndarray, lz: np.ndarray, pz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build a right-handed local frame from canonical frame-corner solver points.

    Returns (center_xyz, rotation_matrix_3x3). Columns of R are local axes expressed
    in local-car coordinates: X forward, Y left, Z up.
    """
    lp = np.asarray(lp, dtype=float)
    pp = np.asarray(pp, dtype=float)
    lz = np.asarray(lz, dtype=float)
    pz = np.asarray(pz, dtype=float)
    center = 0.25 * (lp + pp + lz + pz)

    front = 0.5 * (lp + pp)
    rear = 0.5 * (lz + pz)
    left = 0.5 * (lp + lz)
    right = 0.5 * (pp + pz)

    x_axis = front - rear
    x_norm = float(np.linalg.norm(x_axis))
    if not (np.isfinite(x_norm) and x_norm > 1e-12):
        raise ValueError('Degenerate frame-corner X axis in solver points')
    x_axis = x_axis / x_norm

    y_axis = left - right
    y_axis = y_axis - x_axis * float(np.dot(x_axis, y_axis))
    y_norm = float(np.linalg.norm(y_axis))
    if not (np.isfinite(y_norm) and y_norm > 1e-12):
        raise ValueError('Degenerate frame-corner Y axis in solver points')
    y_axis = y_axis / y_norm

    z_axis = np.cross(x_axis, y_axis)
    z_norm = float(np.linalg.norm(z_axis))
    if not (np.isfinite(z_norm) and z_norm > 1e-12):
        raise ValueError('Degenerate frame-corner Z axis in solver points')
    z_axis = z_axis / z_norm
    if float(z_axis[2]) < 0.0:
        y_axis = -y_axis
        z_axis = np.cross(x_axis, y_axis)
        z_axis = z_axis / max(float(np.linalg.norm(z_axis)), 1e-12)

    R = np.column_stack([x_axis, y_axis, z_axis])
    return center, R


def lifted_box_center_from_lower_corners(center_xyz: np.ndarray, rotation_matrix: np.ndarray, *, height_m: float) -> np.ndarray:
    """Lift a box center from lower-corner plane to geometric center.

    Solver `frame_corner_*` points represent the lower frame contour in the active
    worldroad contract. The chassis mesh, however, is centered around its origin.
    Therefore the visual box center must be raised by `frame_height/2` along the
    local +Z axis recovered from solver points.
    """
    center = np.asarray(center_xyz, dtype=float).reshape(3)
    R = np.asarray(rotation_matrix, dtype=float).reshape(3, 3)
    h = max(0.0, float(height_m))
    return center + np.asarray(R[:, 2], dtype=float) * (0.5 * h)


def contact_patch_extent_from_vertical_clearance(*, wheel_radius_m: float, wheel_width_m: float, clearance_m: float) -> tuple[float, float, float]:
    """Return (length_m, width_m, penetration_m) for a simple contact patch.

    This is a service-only visual helper. It does not invent new physical model
    parameters; it derives the visible contact size from wheel radius, wheel width
    and current vertical clearance between wheel center and road contact point.
    """
    r = max(0.0, float(wheel_radius_m))
    width = max(0.0, float(wheel_width_m))
    clearance = float(clearance_m)
    if not np.isfinite(clearance):
        clearance = r
    penetration = max(0.0, r - clearance)
    half_len = math.sqrt(max(0.0, 2.0 * r * penetration - penetration * penetration))
    return 2.0 * half_len, width, penetration


def center_and_orient_cylinder_vertices_to_y(vertices_xyz: np.ndarray, *, length_m: float) -> np.ndarray:
    """Center a Z-axis cylinder on its axis and orient it once to local +Y.

    Some MeshData.cylinder() implementations create vertices along Z in [0..L], not
    centered in [-L/2..+L/2]. This helper makes the wheel mesh canonical before any
    runtime translation, avoiding latent axis/translation mix-ups.
    """
    v = np.asarray(vertices_xyz, dtype=float).copy()
    if v.size == 0:
        return v
    v[:, 2] -= 0.5 * float(length_m)
    return orient_centered_cylinder_vertices_to_y(v)



def orient_centered_cylinder_vertices_to_y(vertices_xyz: np.ndarray) -> np.ndarray:
    """Rotate an already-centered Z-axis cylinder to local +Y without translating it.

    Why this helper exists:
    - explicit capped actuator meshes are constructed *already centered* in [-L/2, +L/2];
    - reusing ``center_and_orient_cylinder_vertices_to_y()`` on such meshes subtracts
      another half-length and silently shifts the whole segment away from its mounts;
    - the actuator body/rod then appear to protrude beyond the frame eye instead of
      spanning exactly between the exported points.
    """
    v = np.asarray(vertices_xyz, dtype=float).copy()
    if v.size == 0:
        return v
    # Rotate axis Z -> +Y once in mesh space, preserving canonical car basis.
    return np.column_stack([v[:, 0], v[:, 2], -v[:, 1]])



def _safe_normalize(vec_xyz: np.ndarray, *, fallback_xyz: np.ndarray) -> np.ndarray:
    """Normalize ``vec_xyz`` or return a normalized fallback."""
    v = np.asarray(vec_xyz, dtype=float).reshape(3)
    n = float(np.linalg.norm(v))
    if np.isfinite(n) and n > 1e-12:
        return v / n
    fb = np.asarray(fallback_xyz, dtype=float).reshape(3)
    fn = float(np.linalg.norm(fb))
    if np.isfinite(fn) and fn > 1e-12:
        return fb / fn
    return np.array([0.0, 1.0, 0.0], dtype=float)


def _normalize_xyz_or(
    x: float,
    y: float,
    z: float,
    *,
    fallback_xyz: np.ndarray,
) -> tuple[float, float, float]:
    n = math.sqrt((float(x) * float(x)) + (float(y) * float(y)) + (float(z) * float(z)))
    if math.isfinite(n) and n > 1e-12:
        inv = 1.0 / n
        return float(x) * inv, float(y) * inv, float(z) * inv
    fb = np.asarray(fallback_xyz, dtype=float).reshape(3)
    fx = float(fb[0])
    fy = float(fb[1])
    fz = float(fb[2])
    fn = math.sqrt((fx * fx) + (fy * fy) + (fz * fz))
    if math.isfinite(fn) and fn > 1e-12:
        inv = 1.0 / fn
        return fx * inv, fy * inv, fz * inv
    return 0.0, 1.0, 0.0


def _cross_xyz(
    ax: float,
    ay: float,
    az: float,
    bx: float,
    by: float,
    bz: float,
) -> tuple[float, float, float]:
    return (
        (float(ay) * float(bz)) - (float(az) * float(by)),
        (float(az) * float(bx)) - (float(ax) * float(bz)),
        (float(ax) * float(by)) - (float(ay) * float(bx)),
    )


def _project_xyz_to_plane_normalized(
    vx: float,
    vy: float,
    vz: float,
    *,
    plane_normal_xyz: np.ndarray,
    fallback_xyz: np.ndarray,
) -> tuple[float, float, float]:
    nx, ny, nz = _normalize_xyz_or(
        float(np.asarray(plane_normal_xyz, dtype=float).reshape(3)[0]),
        float(np.asarray(plane_normal_xyz, dtype=float).reshape(3)[1]),
        float(np.asarray(plane_normal_xyz, dtype=float).reshape(3)[2]),
        fallback_xyz=np.array([0.0, 0.0, 1.0], dtype=float),
    )
    dot = (float(vx) * nx) + (float(vy) * ny) + (float(vz) * nz)
    return _normalize_xyz_or(
        float(vx) - (nx * dot),
        float(vy) - (ny * dot),
        float(vz) - (nz * dot),
        fallback_xyz=fallback_xyz,
    )


def project_vector_to_plane(vec_xyz: np.ndarray, *, plane_normal_xyz: np.ndarray, fallback_xyz: np.ndarray) -> np.ndarray:
    """Project a vector to a plane and normalize the result."""
    v = np.asarray(vec_xyz, dtype=float).reshape(3)
    n = _safe_normalize(plane_normal_xyz, fallback_xyz=np.array([0.0, 0.0, 1.0], dtype=float))
    proj = v - n * float(np.dot(v, n))
    return _safe_normalize(proj, fallback_xyz=fallback_xyz)


def derive_wheel_pose_from_hardpoints(
    *,
    fallback_center_xyz: np.ndarray,
    lower_front_xyz: np.ndarray | None,
    lower_rear_xyz: np.ndarray | None,
    upper_front_xyz: np.ndarray | None,
    upper_rear_xyz: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, float]:
    """Derive wheel center/axis/orientation from explicit upper/lower hardpoints.

    Returns ``(center_xyz, wheel_axis_xyz, fwd_xyz, up_xyz, toe_rad, camber_rad)``.

    Design intent:
      - no hidden aliases or fake baseline geometry;
      - X/Y center follows explicit hub hardpoints when available;
      - Z stays anchored to the canonical solver wheel center (the reduced vertical
        models still own tire-center heave);
      - wheel orientation is reconstructed from hardpoints so track/camber/toe can
        be visualized whenever the exporter geometry actually implies them.
    """
    center = np.asarray(fallback_center_xyz, dtype=float).reshape(3).copy()

    def _opt(p: np.ndarray | None) -> np.ndarray | None:
        if p is None:
            return None
        arr = np.asarray(p, dtype=float).reshape(3)
        if not np.all(np.isfinite(arr)):
            return None
        return arr

    lf = _opt(lower_front_xyz)
    lr = _opt(lower_rear_xyz)
    uf = _opt(upper_front_xyz)
    ur = _opt(upper_rear_xyz)
    sum_x = 0.0
    sum_y = 0.0
    hardpoint_count = 0
    for p in (lf, lr, uf, ur):
        if p is None:
            continue
        sum_x += float(p[0])
        sum_y += float(p[1])
        hardpoint_count += 1
    if hardpoint_count > 0:
        center[0] = sum_x / float(hardpoint_count)
        center[1] = sum_y / float(hardpoint_count)

    lower_mid = None if (lf is None or lr is None) else 0.5 * (lf + lr)
    upper_mid = None if (uf is None or ur is None) else 0.5 * (uf + ur)

    front_mid = None
    front_count = 0
    front_x = 0.0
    front_y = 0.0
    front_z = 0.0
    for p in (lf, uf):
        if p is None:
            continue
        front_x += float(p[0])
        front_y += float(p[1])
        front_z += float(p[2])
        front_count += 1
    if front_count > 0:
        front_mid = np.asarray([front_x / front_count, front_y / front_count, front_z / front_count], dtype=float)

    rear_mid = None
    rear_count = 0
    rear_x = 0.0
    rear_y = 0.0
    rear_z = 0.0
    for p in (lr, ur):
        if p is None:
            continue
        rear_x += float(p[0])
        rear_y += float(p[1])
        rear_z += float(p[2])
        rear_count += 1
    if rear_count > 0:
        rear_mid = np.asarray([rear_x / rear_count, rear_y / rear_count, rear_z / rear_count], dtype=float)

    if upper_mid is not None and lower_mid is not None:
        upx = float(upper_mid[0] - lower_mid[0])
        upy = float(upper_mid[1] - lower_mid[1])
        upz = float(upper_mid[2] - lower_mid[2])
    else:
        upx, upy, upz = 0.0, 0.0, 1.0
    upx, upy, upz = _normalize_xyz_or(upx, upy, upz, fallback_xyz=np.array([0.0, 0.0, 1.0], dtype=float))

    if front_mid is not None and rear_mid is not None:
        fgx = float(front_mid[0] - rear_mid[0])
        fgy = float(front_mid[1] - rear_mid[1])
        fgz = float(front_mid[2] - rear_mid[2])
    else:
        fgx, fgy, fgz = 1.0, 0.0, 0.0
    fwdx, fwdy, fwdz = _project_xyz_to_plane_normalized(
        fgx,
        fgy,
        fgz,
        plane_normal_xyz=np.asarray([upx, upy, upz], dtype=float),
        fallback_xyz=np.array([1.0, 0.0, 0.0], dtype=float),
    )

    axx, axy, axz = _cross_xyz(upx, upy, upz, fwdx, fwdy, fwdz)
    axx, axy, axz = _normalize_xyz_or(
        axx,
        axy,
        axz,
        fallback_xyz=np.array([0.0, 1.0 if center[1] >= 0.0 else -1.0, 0.0], dtype=float),
    )
    fwdx, fwdy, fwdz = _cross_xyz(axx, axy, axz, upx, upy, upz)
    fwdx, fwdy, fwdz = _normalize_xyz_or(fwdx, fwdy, fwdz, fallback_xyz=np.asarray([fwdx, fwdy, fwdz], dtype=float))
    upx, upy, upz = _cross_xyz(fwdx, fwdy, fwdz, axx, axy, axz)
    upx, upy, upz = _normalize_xyz_or(upx, upy, upz, fallback_xyz=np.asarray([upx, upy, upz], dtype=float))

    axle = np.asarray([axx, axy, axz], dtype=float)
    fwd = np.asarray([fwdx, fwdy, fwdz], dtype=float)
    up = np.asarray([upx, upy, upz], dtype=float)
    toe_rad = math.atan2(float(axle[0]), max(1e-12, abs(float(axle[1]))))
    camber_rad = math.atan2(float(axle[2]), max(1e-12, abs(float(axle[1]))))
    return center, axle, fwd, up, float(toe_rad), float(camber_rad)


def ellipse_mesh_on_plane(
    *,
    center_xyz: np.ndarray,
    axis_u_xyz: np.ndarray,
    axis_v_xyz: np.ndarray,
    radius_u_m: float,
    radius_v_m: float,
    segments: int = 20,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a small ellipse mesh on an arbitrary plane."""
    ru = max(0.0, float(radius_u_m))
    rv = max(0.0, float(radius_v_m))
    if ru <= 0.0 or rv <= 0.0:
        return np.zeros((0, 3), dtype=float), np.zeros((0, 3), dtype=np.int32)
    u = _safe_normalize(axis_u_xyz, fallback_xyz=np.array([1.0, 0.0, 0.0], dtype=float))
    v = _safe_normalize(axis_v_xyz, fallback_xyz=np.array([0.0, 1.0, 0.0], dtype=float))
    # Make V orthogonal to U explicitly.
    v = project_vector_to_plane(v, plane_normal_xyz=u, fallback_xyz=np.array([0.0, 1.0, 0.0], dtype=float))
    c = np.asarray(center_xyz, dtype=float).reshape(3)
    nseg = int(max(8, segments))
    ang = np.linspace(0.0, 2.0 * math.pi, nseg, endpoint=False)
    ring = np.stack([c + ru * math.cos(a) * u + rv * math.sin(a) * v for a in ang], axis=0)
    verts = np.vstack([c.reshape(1, 3), ring])
    faces = []
    for j in range(nseg):
        a = 1 + j
        b = 1 + ((j + 1) % nseg)
        faces.append([0, a, b])
    return np.asarray(verts, dtype=float), np.asarray(faces, dtype=np.int32)



@lru_cache(maxsize=64)
def _grid_faces_rect_cached(n_s: int, n_l: int) -> np.ndarray:
    row_idx = np.arange(n_s - 1, dtype=np.int32).reshape(-1, 1)
    col_idx = np.arange(n_l - 1, dtype=np.int32).reshape(1, -1)
    row0 = row_idx * int(n_l)
    row1 = (row_idx + 1) * int(n_l)
    a = row0 + col_idx
    b = a + 1
    d = row1 + col_idx
    c = d + 1
    faces = np.stack(
        [
            np.stack([a, b, c], axis=-1),
            np.stack([a, c, d], axis=-1),
        ],
        axis=-2,
    ).reshape(-1, 3)
    faces = np.ascontiguousarray(faces, dtype=np.int32)
    try:
        faces.setflags(write=False)
    except Exception:
        pass
    return faces


def grid_faces_rect(n_long: int, n_lat: int) -> np.ndarray:
    """Return triangle faces for a regular (longitudinal x lateral) road grid."""
    n_s = int(max(2, n_long))
    n_l = int(max(2, n_lat))
    return _grid_faces_rect_cached(n_s, n_l)


@lru_cache(maxsize=128)
def _road_longitudinal_line_pairs(
    n_long: int,
    n_lat: int,
    lateral_stride: int,
    include_outer_edges: bool = True,
) -> np.ndarray:
    n_s = int(max(2, n_long))
    n_l = int(max(2, n_lat))
    lat_stride = int(max(1, lateral_stride))
    rails = set(range(0, n_l, lat_stride))
    if bool(include_outer_edges):
        rails |= {0, n_l - 1}
    else:
        rails = set(int(i) for i in rails if 0 < int(i) < (n_l - 1))
        if not rails and n_l > 2:
            rails = {int(n_l // 2)}
    rails = sorted(rails)
    if n_s <= 1 or not rails:
        return np.zeros((0, 2), dtype=np.int32)
    row_base = (np.arange(n_s - 1, dtype=np.int32) * n_l).reshape(-1, 1)
    rail_cols = np.asarray(rails, dtype=np.int32).reshape(1, -1)
    start = row_base + rail_cols
    pairs = np.empty((start.size, 2), dtype=np.int32)
    pairs[:, 0] = start.reshape(-1)
    pairs[:, 1] = (start + n_l).reshape(-1)
    try:
        pairs.setflags(write=False)
    except Exception:
        pass
    return pairs


@lru_cache(maxsize=256)
def _road_crossbar_line_pairs(
    n_long: int,
    n_lat: int,
    rows_key: tuple[int, ...],
) -> np.ndarray:
    n_s = int(max(2, n_long))
    n_l = int(max(2, n_lat))
    rows = np.asarray(sorted(set(int(i) for i in rows_key if 0 <= int(i) < n_s)), dtype=np.int32)
    if rows.size == 0 or n_l <= 1:
        return np.zeros((0, 2), dtype=np.int32)
    col_offsets = np.arange(n_l - 1, dtype=np.int32).reshape(1, -1)
    start = (rows.reshape(-1, 1) * n_l) + col_offsets
    pairs = np.empty((start.size, 2), dtype=np.int32)
    pairs[:, 0] = start.reshape(-1)
    pairs[:, 1] = (start + 1).reshape(-1)
    try:
        pairs.setflags(write=False)
    except Exception:
        pass
    return pairs


def regular_grid_submesh(
    *,
    vertices_xyz: np.ndarray,
    n_long: int,
    n_lat: int,
    row_start: int,
    row_stop: int,
    col_start: int,
    col_stop: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a contiguous subgrid of a regular road surface mesh.

    The returned vertices keep the original coordinates, but faces are re-indexed
    to the compact subgrid. This lets the animator evaluate contact only near the
    wheel instead of re-testing the full visible road mesh every frame.
    """
    verts = np.asarray(vertices_xyz, dtype=float).reshape(-1, 3)
    n_s = int(max(2, n_long))
    n_l = int(max(2, n_lat))
    if verts.shape[0] != n_s * n_l:
        raise ValueError('regular_grid_submesh: vertex count does not match grid shape')
    rs = int(max(0, row_start))
    re = int(min(n_s, row_stop))
    cs = int(max(0, col_start))
    ce = int(min(n_l, col_stop))
    if re - rs < 2 or ce - cs < 2:
        return np.zeros((0, 3), dtype=float), np.zeros((0, 3), dtype=np.int32)
    grid = verts.reshape(n_s, n_l, 3)
    sub = np.asarray(grid[rs:re, cs:ce, :], dtype=float).reshape(-1, 3)
    faces = grid_faces_rect(re - rs, ce - cs)
    return sub, faces



def road_display_counts_from_view(
    *,
    visible_length_m: float,
    raw_point_count: int,
    viewport_width_px: int,
    viewport_height_px: int,
    min_long: int = 180,
    max_long: int = 600,
    min_lat: int = 7,
    max_lat: int = 15,
) -> tuple[int, int, int, int]:
    """Choose road surface and visible-grid density from view size and source detail.

    Design intent:
    - the *surface mesh* should follow the available road profile data up to the useful
      on-screen resolution, but should not oversample far beyond what the current view can show;
    - the *wire grid* may be sparser than the surface so the user sees road relief
      without paying for a full edge overlay on every triangle.
    """
    vis_len = max(1.0, float(visible_length_m))
    raw_n = int(max(0, raw_point_count))
    vp_w = int(max(320, viewport_width_px))
    vp_h = int(max(240, viewport_height_px))
    min_long = int(max(32, min_long))
    max_long = int(max(min_long, max_long))
    min_lat = int(max(3, min_lat))
    max_lat = int(max(min_lat, max_lat))

    # Surface mesh: keep it dense enough that visible curvature is carried by the
    # geometry itself rather than by sparse flat facets. We still cap by viewport
    # resolution so we do not push multiple samples into one screen pixel.
    target_long = int(max(min_long, min(max_long, round(vp_w / 1.4))))
    if raw_n > 0:
        n_long = int(max(min_long, min(target_long, raw_n)))
    else:
        n_long = target_long
    n_long = _quantize_display_count(n_long, quantum=32, min_count=min_long, max_count=max_long)

    target_lat = int(round(vp_h / 42.0))
    n_lat = int(max(min_lat, min(max_lat, target_lat)))
    if n_lat % 2 == 0:
        if n_lat < max_lat:
            n_lat += 1
        else:
            n_lat = max(min_lat, n_lat - 1)

    # Target visible wire density separately from surface density.
    # User requirement: dense *surface* mesh and a visible wire grid that still shows
    # road relief. The previous 5–12 m stripe spacing made the road look flat.
    target_cross = int(max(36, min(220, round(vp_w / 18.0))))
    cross_stride = int(max(1, math.ceil(n_long / max(1, target_cross))))
    target_rails = int(max(9, min(23, round(vp_h / 56.0))))
    lateral_stride = int(max(1, math.ceil(n_lat / max(1, target_rails))))
    if vis_len > 90.0:
        # Mild coarsening for very long look-ahead windows, while keeping the wire
        # visibly attached to the moving road rather than to a static world grid.
        cross_stride = int(max(cross_stride, math.ceil(vis_len / 28.0)))
    return int(n_long), int(n_lat), int(cross_stride), int(lateral_stride)



def stable_road_grid_cross_spacing_from_view(
    *,
    nominal_visible_length_m: float,
    viewport_width_px: int,
    min_spacing_m: float = 0.25,
    max_spacing_m: float = 4.0,
    quant_step_m: float = 0.05,
) -> float:
    """Return a stable world-space spacing for visible road cross-bars.

    Why this helper exists:
    - world-anchoring the row *phase* is not enough if the bar spacing itself is
      recomputed from the current playback window on every frame;
    - when visible length changes with speed/look-ahead, that policy makes the wire
      grid appear to stretch/shrink relative to the same road relief;
    - the spacing therefore has to come from a *bundle/view* scale (nominal visible
      length + viewport width), not from the instantaneous playback frame.

    The result is intentionally quantized to a small metric step so the grid density
    stays perceptually stable and only changes when the user really changes the view.
    """
    vis_len = max(1.0, float(nominal_visible_length_m))
    vp_w = int(max(320, viewport_width_px))
    target_cross = int(max(36, min(220, round(vp_w / 18.0))))
    spacing = vis_len / float(max(1, target_cross))
    quant = max(0.01, float(quant_step_m))
    spacing = round(spacing / quant) * quant
    spacing = max(float(min_spacing_m), min(float(max_spacing_m), spacing))
    return float(spacing)


def stable_road_surface_spacing_from_view(
    *,
    nominal_visible_length_m: float,
    viewport_width_px: int,
    min_long: int,
    max_long: int,
    quant_step_m: float = 0.005,
) -> float:
    """Return a stable world-space spacing for dense road *surface* rows.

    Why this helper exists:
    - fixing only the visible wire-grid is not enough when the shaded road surface
      itself is resampled from a fresh local linspace on every playback frame;
    - that policy makes the dense triangle rows slide over the same road relief,
      which users perceive as the *road mesh drifting* even if the road physics is
      otherwise correct;
    - therefore the longitudinal rows of the shaded surface also need a bundle/view-
      stable world spacing, not a per-frame spacing derived from the instantaneous
      playback window.

    The spacing is quantized so it changes only when the user meaningfully changes
    the view/perf tier.
    """
    vis_len = max(1.0, float(nominal_visible_length_m))
    vp_w = int(max(320, viewport_width_px))
    lo = int(max(2, min_long))
    hi = int(max(lo, max_long))
    target_long = int(max(lo, min(hi, round(vp_w / 1.4))))
    spacing = vis_len / float(max(1, target_long - 1))
    quant = max(0.001, float(quant_step_m))
    spacing = round(spacing / quant) * quant
    # Respect the requested row-count envelope for the nominal visible length.
    max_spacing = vis_len / float(max(1, lo - 1))
    min_spacing = vis_len / float(max(1, hi - 1))
    spacing = max(float(min_spacing), min(float(max_spacing), float(spacing)))
    return float(max(1e-6, spacing))


def road_grid_target_s_values_from_range(
    *,
    s_min_m: float,
    s_max_m: float,
    cross_spacing_m: float,
    anchor_s_m: float = 0.0,
    include_last: bool = False,
) -> np.ndarray:
    """Return world-anchored target ``s`` positions for visible road cross-bars.

    Why this helper exists:
    - a forced "last visible row" cross-bar is tied to the current viewport edge rather than
      to the road/world itself, so it appears to swim or pop at the far edge during playback;
    - callers therefore need an explicit way to ask for *only* world-anchored stripe targets
      and to opt-in to an extra terminal bar only when that is visually desired.
    """
    spacing = float(max(1e-6, cross_spacing_m))
    s_lo = float(min(s_min_m, s_max_m))
    s_hi = float(max(s_min_m, s_max_m))
    if not (np.isfinite(s_lo) and np.isfinite(s_hi)) or s_hi <= s_lo + 1e-12:
        return np.zeros((0,), dtype=float)
    start_k = int(math.ceil((s_lo - float(anchor_s_m)) / spacing))
    end_k = int(math.floor((s_hi - float(anchor_s_m)) / spacing))
    if end_k < start_k:
        targets = np.zeros((0,), dtype=float)
    else:
        targets = float(anchor_s_m) + np.arange(start_k, end_k + 1, dtype=float) * spacing
    if include_last:
        if targets.size == 0 or abs(float(targets[-1]) - s_hi) > 1e-9:
            targets = np.concatenate([targets, np.asarray([s_hi], dtype=float)], axis=0)
    return np.asarray(targets, dtype=float)


def road_native_support_s_values_from_axis(
    *,
    support_s_m: np.ndarray,
    s_min_m: float,
    s_max_m: float,
    stride_rows: int = 1,
    extra_rows_each_side: int = 1,
) -> np.ndarray:
    """Return bundle-stable native support rows for the visible road window.

    Why this helper exists:
    - even world-anchored ``linspace`` / quantized target grids still rebuild a *fresh*
      set of longitudinal rows for every playback frame;
    - when the visible window moves or the viewport changes, that policy keeps the road
      approximately correct but can still make the dense shaded surface and longitudinal
      rails appear to drift over the same relief;
    - the road surface therefore needs to come from the dataset's own support rows, with
      a stable stride selected per bundle/perf tier, instead of from per-frame resampling.

    The returned rows are anchored to the *global dataset row 0* and then sliced to the
    requested window with a small guard on each side, so resizing / playback does not
    change the longitudinal phase of the rendered support lattice.
    """
    s = np.asarray(support_s_m, dtype=float).reshape(-1)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return np.zeros((0,), dtype=float)
    order = np.argsort(s, kind="mergesort")
    s = np.asarray(s[order], dtype=float)
    if s.size >= 2:
        keep = np.ones_like(s, dtype=bool)
        keep[1:] = np.diff(s) > 1e-9
        s = np.asarray(s[keep], dtype=float)
    if s.size == 0:
        return np.zeros((0,), dtype=float)
    stride = int(max(1, stride_rows))
    extra = int(max(0, extra_rows_each_side))
    base_idx = np.arange(0, int(s.size), stride, dtype=np.int32)
    base_s = np.asarray(s[base_idx], dtype=float)
    s_lo = float(min(s_min_m, s_max_m))
    s_hi = float(max(s_min_m, s_max_m))
    if not (np.isfinite(s_lo) and np.isfinite(s_hi)) or s_hi <= s_lo + 1e-12:
        return np.zeros((0,), dtype=float)
    i0 = int(np.searchsorted(base_s, s_lo, side="left"))
    i1 = int(np.searchsorted(base_s, s_hi, side="right"))
    i0 = max(0, i0 - extra)
    i1 = min(int(base_s.size), i1 + extra)
    out = np.asarray(base_s[i0:i1], dtype=float)
    if out.size >= 2:
        return out
    # Conservative fallback: include raw nearest support rows so callers can still render.
    j0 = int(np.searchsorted(s, s_lo, side="left"))
    j1 = int(np.searchsorted(s, s_hi, side="right"))
    j0 = max(0, j0 - max(1, extra))
    j1 = min(int(s.size), j1 + max(1, extra))
    return np.asarray(s[j0:j1], dtype=float)


def road_grid_rows_from_s_nodes(
    *,
    s_nodes: np.ndarray,
    cross_spacing_m: float,
    anchor_s_m: float = 0.0,
    include_last: bool = True,
) -> np.ndarray:
    """Pick visible cross-bar rows anchored to world ``s`` coordinates.

    Why this helper exists:
    - the visible road *surface* may be rebuilt every frame over the current viewport window;
    - if cross-bars are chosen as every N-th local row starting from row 0, the wire grid
      appears to slide relative to the road relief because row 0 itself moves with the window;
    - selecting rows from a world-anchored spacing keeps the wire/grid visually attached to
      the road while preserving a decimated overlay.
    """
    s = np.asarray(s_nodes, dtype=float).reshape(-1)
    if s.size <= 1:
        rows = [0] if s.size else []
        return np.asarray(rows, dtype=np.int32)
    spacing = float(max(1e-6, cross_spacing_m))
    finite = np.asarray(s[np.isfinite(s)], dtype=float)
    if finite.size <= 1:
        rows = [0]
        if include_last and int(s.size - 1) not in rows:
            rows.append(int(s.size - 1))
        return np.asarray(sorted(set(rows)), dtype=np.int32)
    s_lo = float(finite[0])
    s_hi = float(finite[-1])
    start_k = int(math.ceil((s_lo - float(anchor_s_m)) / spacing))
    end_k = int(math.floor((s_hi - float(anchor_s_m)) / spacing))
    rows: list[int] = []
    if end_k >= start_k:
        targets = float(anchor_s_m) + np.arange(start_k, end_k + 1, dtype=float) * spacing
        idx = np.searchsorted(s, targets, side="left")
        idx = np.clip(idx, 0, int(s.size - 1))
        for pos, target in zip(idx.tolist(), targets.tolist()):
            j = int(pos)
            if j > 0 and abs(float(s[j - 1]) - float(target)) <= abs(float(s[j]) - float(target)):
                j -= 1
            rows.append(int(j))
    if include_last:
        rows.append(int(s.size - 1))
    rows = sorted(set(int(r) for r in rows if 0 <= int(r) < int(s.size)))
    return np.asarray(rows, dtype=np.int32)


def clamp_window_to_interpolation_support(
    *,
    request_start_m: float,
    request_end_m: float,
    support_axes: tuple[np.ndarray, ...] | list[np.ndarray],
) -> tuple[float, float]:
    """Clamp a requested longitudinal window to the shared interpolation support.

    Why this helper exists:
    - ``np.interp`` clamps samples outside the source axis to the nearest endpoint;
    - for the 3D road mesh that creates repeated longitudinal slices at the dataset
      start/end, which in turn produces degenerate triangles and invalid GL normals;
    - clipping to the common support keeps the visible road honest and avoids wasting
      frame time on zero-area faces.

    The function is intentionally conservative: when valid support is unavailable,
    the original request is returned unchanged so callers may decide how to degrade.
    """
    lo = float(request_start_m)
    hi = float(request_end_m)
    if hi < lo:
        lo, hi = hi, lo

    bounds: list[tuple[float, float]] = []
    for axis in list(support_axes or []):
        arr = np.asarray(axis, dtype=float).reshape(-1)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            continue
        a0 = float(np.min(arr))
        a1 = float(np.max(arr))
        if a1 < a0:
            a0, a1 = a1, a0
        bounds.append((a0, a1))

    if not bounds:
        return lo, hi

    support_lo = max(b[0] for b in bounds)
    support_hi = min(b[1] for b in bounds)
    if not (np.isfinite(support_lo) and np.isfinite(support_hi)):
        return lo, hi

    if support_hi < support_lo:
        anchor = float(np.median([b[0] for b in bounds] + [b[1] for b in bounds]))
        return anchor, anchor

    lo = max(lo, support_lo)
    hi = min(hi, support_hi)
    if hi < lo:
        anchor = float(min(max(0.5 * (request_start_m + request_end_m), support_lo), support_hi))
        return anchor, anchor
    return float(lo), float(hi)


def road_surface_grid_from_profiles(
    *,
    x_center: np.ndarray,
    y_center: np.ndarray,
    z_left: np.ndarray,
    z_center: np.ndarray,
    z_right: np.ndarray,
    normal_x: np.ndarray,
    normal_y: np.ndarray,
    half_width_m: float,
    lateral_count: int,
    build_faces: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a dense road surface grid from center/left/right profiles.

    Geometry contract:
    - long direction follows the active centerline in local car frame;
    - lateral samples span ``[-half_width, +half_width]`` along the local road normal;
    - Z across width is reconstructed *piecewise-linearly* from (right -> center -> left).

    Rationale:
    - the exporter provides explicit right/center/left road profiles, but not a higher-order
      cross-width surface model;
    - quadratic interpolation can invent a bulged crown/valley between those traces;
    - piecewise-linear interpolation preserves the measured/profiled traces without silently
      creating extra curvature.

    This does **not** invent a separate analytic contact figure. It only turns the
    already available profile traces into a visible mesh so that contact can be
    highlighted as a subset of this mesh.

    ``build_faces=False`` is an optimisation path for callers that cache the regular
    grid topology and only need fresh vertex coordinates each frame.
    """
    xc = np.asarray(x_center, dtype=float).reshape(-1)
    yc = np.asarray(y_center, dtype=float).reshape(-1)
    zl = np.asarray(z_left, dtype=float).reshape(-1)
    zc = np.asarray(z_center, dtype=float).reshape(-1)
    zr = np.asarray(z_right, dtype=float).reshape(-1)
    nx = np.asarray(normal_x, dtype=float).reshape(-1)
    ny = np.asarray(normal_y, dtype=float).reshape(-1)
    n_s = int(xc.shape[0])
    if not (yc.shape[0] == zl.shape[0] == zc.shape[0] == zr.shape[0] == nx.shape[0] == ny.shape[0] == n_s):
        raise ValueError('road_surface_grid_from_profiles: inconsistent profile lengths')
    n_lat = int(max(3, lateral_count))
    half = max(0.0, float(half_width_m))
    if n_s <= 1 or half <= 0.0:
        return np.zeros((0, 3), dtype=float), np.zeros((0, 3), dtype=np.int32), np.zeros((0, 3), dtype=float)

    t = np.linspace(-1.0, 1.0, n_lat, dtype=float)  # -1 right, 0 center, +1 left
    off = t * half
    # Piecewise-linear cross-width interpolation through (right, center, left).
    z_grid = np.empty((n_s, n_lat), dtype=float)
    mask_right = t <= 0.0
    mask_left = ~mask_right
    if np.any(mask_right):
        # t=-1 -> right, t=0 -> center
        alpha_r = t[mask_right] + 1.0
        z_grid[:, mask_right] = zr[:, None] * (1.0 - alpha_r[None, :]) + zc[:, None] * alpha_r[None, :]
    if np.any(mask_left):
        # t=0 -> center, t=+1 -> left
        alpha_l = t[mask_left]
        z_grid[:, mask_left] = zc[:, None] * (1.0 - alpha_l[None, :]) + zl[:, None] * alpha_l[None, :]
    x_grid = xc[:, None] + nx[:, None] * off[None, :]
    y_grid = yc[:, None] + ny[:, None] * off[None, :]
    verts = np.stack([x_grid, y_grid, z_grid], axis=2).reshape(n_s * n_lat, 3)
    if build_faces:
        faces = grid_faces_rect(n_s, n_lat)
    else:
        faces = np.zeros((0, 3), dtype=np.int32)
    return np.asarray(verts, dtype=float), np.asarray(faces, dtype=np.int32), np.asarray(t, dtype=float)


def road_grid_line_segments(
    *,
    vertices_xyz: np.ndarray,
    n_long: int,
    n_lat: int,
    cross_stride: int = 8,
    lateral_stride: int = 1,
    row_indices: np.ndarray | None = None,
    include_longitudinal: bool = True,
    include_crossbars: bool = True,
    force_last_crossbar: bool = True,
    include_outer_longitudinal: bool = True,
) -> np.ndarray:
    """Build visible grid lines for the road mesh.

    The road *surface* may be dense while the overlaid wire/grid is decimated both
    longitudinally and laterally for readability/performance.

    ``include_crossbars=False`` is useful when callers want to render longitudinal rails
    from the dense mesh but build cross-bars from exact world-anchored targets instead of
    snapping them to the nearest longitudinal mesh row.
    """
    verts = np.asarray(vertices_xyz, dtype=float).reshape(-1, 3)
    n_s = int(max(2, n_long))
    n_l = int(max(2, n_lat))
    if verts.shape[0] != n_s * n_l:
        raise ValueError('road_grid_line_segments: vertex count does not match grid shape')
    pair_blocks: list[np.ndarray] = []
    if include_longitudinal:
        pair_blocks.append(
            _road_longitudinal_line_pairs(
                n_s,
                n_l,
                int(max(1, lateral_stride)),
                bool(include_outer_longitudinal),
            )
        )
    if include_crossbars:
        # Cross-bars: prefer explicitly supplied rows; otherwise fall back to every N-th
        # local longitudinal row. ``force_last_crossbar`` keeps the old behaviour, but
        # callers that want purely world-anchored stripes can disable the viewport-edge bar.
        if row_indices is not None:
            rows = set(int(i) for i in np.asarray(row_indices, dtype=np.int32).reshape(-1).tolist())
            rows = set(i for i in rows if 0 <= i < n_s)
            if force_last_crossbar:
                rows.add(n_s - 1)
        else:
            stride = int(max(1, cross_stride))
            rows = set(range(0, n_s, stride))
            if force_last_crossbar:
                rows.add(n_s - 1)
        pair_blocks.append(_road_crossbar_line_pairs(n_s, n_l, tuple(sorted(rows))))
    if not pair_blocks:
        return np.zeros((0, 3), dtype=float)
    if len(pair_blocks) == 1:
        pairs = pair_blocks[0]
    else:
        pairs = np.concatenate(pair_blocks, axis=0)
    if pairs.size == 0:
        return np.zeros((0, 3), dtype=float)
    return np.ascontiguousarray(verts[pairs.reshape(-1)], dtype=float)


def polyline_line_segments(points_xyz: np.ndarray) -> np.ndarray:
    """Return independent line segments for a polyline without closing joins."""
    pts = np.asarray(points_xyz, dtype=float).reshape(-1, 3)
    if pts.shape[0] <= 1:
        return np.zeros((0, 3), dtype=float)
    segs = np.empty(((pts.shape[0] - 1) * 2, 3), dtype=float)
    segs[0::2] = pts[:-1]
    segs[1::2] = pts[1:]
    return np.ascontiguousarray(segs, dtype=float)


def road_edge_line_segments(left_edge_xyz: np.ndarray, right_edge_xyz: np.ndarray) -> np.ndarray:
    """Return independent left/right road edge segments without a closing cross-connection."""
    left = np.asarray(left_edge_xyz, dtype=float).reshape(-1, 3)
    right = np.asarray(right_edge_xyz, dtype=float).reshape(-1, 3)
    if left.shape[0] <= 1 and right.shape[0] <= 1:
        return np.zeros((0, 3), dtype=float)
    left_segs = polyline_line_segments(left)
    right_segs = polyline_line_segments(right)
    if left_segs.size == 0:
        return right_segs
    if right_segs.size == 0:
        return left_segs
    return np.ascontiguousarray(np.vstack([left_segs, right_segs]), dtype=float)


def road_crossbar_line_segments_from_profiles(
    *,
    s_targets_m: np.ndarray,
    s_nodes_m: np.ndarray,
    x_center: np.ndarray,
    y_center: np.ndarray,
    z_left: np.ndarray,
    z_center: np.ndarray,
    z_right: np.ndarray,
    normal_x: np.ndarray,
    normal_y: np.ndarray,
    half_width_m: float,
    lateral_count: int,
) -> np.ndarray:
    """Build cross-bars at exact world-anchored ``s`` positions.

    Why this helper exists:
    - snapping visible stripes to the nearest road mesh row introduces frame-to-frame
      jitter as the viewport slides over the same road relief;
    - an extra "last visible row" stripe is viewport-anchored, not world-anchored;
    - exact profile interpolation lets the dense surface mesh stay decoupled from the
      visible stripe placement, so cross-bars remain visually glued to the road.
    """
    targets = np.asarray(s_targets_m, dtype=float).reshape(-1)
    s = np.asarray(s_nodes_m, dtype=float).reshape(-1)
    xc = np.asarray(x_center, dtype=float).reshape(-1)
    yc = np.asarray(y_center, dtype=float).reshape(-1)
    zl = np.asarray(z_left, dtype=float).reshape(-1)
    zc = np.asarray(z_center, dtype=float).reshape(-1)
    zr = np.asarray(z_right, dtype=float).reshape(-1)
    nx = np.asarray(normal_x, dtype=float).reshape(-1)
    ny = np.asarray(normal_y, dtype=float).reshape(-1)
    n_lat = int(max(3, lateral_count))
    half = float(max(0.0, half_width_m))
    n_s = int(s.shape[0])
    if n_s <= 1 or targets.size == 0 or half <= 0.0:
        return np.zeros((0, 3), dtype=float)
    if not (xc.shape[0] == yc.shape[0] == zl.shape[0] == zc.shape[0] == zr.shape[0] == nx.shape[0] == ny.shape[0] == n_s):
        raise ValueError('road_crossbar_line_segments_from_profiles: inconsistent profile lengths')
    finite_targets = np.asarray(targets[np.isfinite(targets)], dtype=float)
    if finite_targets.size == 0:
        return np.zeros((0, 3), dtype=float)
    s_lo = float(s[0])
    s_hi = float(s[-1])
    finite_targets = finite_targets[(finite_targets >= s_lo) & (finite_targets <= s_hi)]
    if finite_targets.size == 0:
        return np.zeros((0, 3), dtype=float)

    x_t = np.interp(finite_targets, s, xc)
    y_t = np.interp(finite_targets, s, yc)
    zl_t = np.interp(finite_targets, s, zl)
    zc_t = np.interp(finite_targets, s, zc)
    zr_t = np.interp(finite_targets, s, zr)
    nx_t = np.interp(finite_targets, s, nx)
    ny_t = np.interp(finite_targets, s, ny)
    nn = np.sqrt(nx_t * nx_t + ny_t * ny_t)
    nn = np.where(nn > 1e-12, nn, 1.0)
    nx_t = nx_t / nn
    ny_t = ny_t / nn

    t = np.linspace(-1.0, 1.0, n_lat, dtype=float)
    off = t * half
    z_grid = np.empty((finite_targets.shape[0], n_lat), dtype=float)
    mask_right = t <= 0.0
    mask_left = ~mask_right
    if np.any(mask_right):
        alpha_r = t[mask_right] + 1.0
        z_grid[:, mask_right] = zr_t[:, None] * (1.0 - alpha_r[None, :]) + zc_t[:, None] * alpha_r[None, :]
    if np.any(mask_left):
        alpha_l = t[mask_left]
        z_grid[:, mask_left] = zc_t[:, None] * (1.0 - alpha_l[None, :]) + zl_t[:, None] * alpha_l[None, :]

    x_grid = x_t[:, None] + nx_t[:, None] * off[None, :]
    y_grid = y_t[:, None] + ny_t[:, None] * off[None, :]
    verts = np.stack([x_grid, y_grid, z_grid], axis=2)
    if verts.shape[0] == 0 or n_lat <= 1:
        return np.zeros((0, 3), dtype=float)
    segs = np.empty((verts.shape[0], n_lat - 1, 2, 3), dtype=float)
    segs[:, :, 0, :] = verts[:, :-1, :]
    segs[:, :, 1, :] = verts[:, 1:, :]
    return np.ascontiguousarray(segs.reshape(-1, 3), dtype=float)


def _points_inside_wheel_cylinder_mask(
    *,
    points_xyz: np.ndarray,
    wheel_center_xyz: np.ndarray,
    wheel_axle_xyz: np.ndarray,
    wheel_up_xyz: np.ndarray,
    wheel_radius_m: float,
    wheel_width_m: float,
) -> np.ndarray:
    pts = np.asarray(points_xyz, dtype=float).reshape(-1, 3)
    center = np.asarray(wheel_center_xyz, dtype=float).reshape(3)
    axle = _safe_normalize(wheel_axle_xyz, fallback_xyz=np.array([0.0, 1.0, 0.0], dtype=float))
    up = _safe_normalize(wheel_up_xyz, fallback_xyz=np.array([0.0, 0.0, 1.0], dtype=float))
    radius = max(0.0, float(wheel_radius_m))
    half_width = 0.5 * max(0.0, float(wheel_width_m))
    if pts.size == 0 or radius <= 0.0 or half_width <= 0.0:
        return np.zeros((pts.shape[0],), dtype=bool)
    rel = pts - center.reshape(1, 3)
    axial = rel @ axle
    radial = rel - axial[:, None] * axle.reshape(1, 3)
    radial2 = np.einsum('ij,ij->i', radial, radial)
    below = (rel @ up) <= 1e-9
    return (np.abs(axial) <= (half_width + 1e-9)) & (radial2 <= (radius * radius + 1e-9)) & below


def _subdivide_triangle_once(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    ab = 0.5 * (a + b)
    bc = 0.5 * (b + c)
    ca = 0.5 * (c + a)
    return [
        (a, ab, ca),
        (ab, b, bc),
        (ca, bc, c),
        (ab, bc, ca),
    ]


def road_patch_mesh_inside_wheel_cylinder(
    *,
    vertices_xyz: np.ndarray,
    faces: np.ndarray,
    wheel_center_xyz: np.ndarray,
    wheel_axle_xyz: np.ndarray,
    wheel_up_xyz: np.ndarray,
    wheel_radius_m: float,
    wheel_width_m: float,
    refine_steps: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a refined road-mesh subset that lies inside the wheel volume.

    This is still a *subset of the road mesh*, not an analytic ellipse/rectangle.
    Boundary faces are recursively split into smaller triangles so the visible patch
    follows the actual road surface more closely than a whole-face inclusion test.
    """
    verts = np.asarray(vertices_xyz, dtype=float).reshape(-1, 3)
    tri = np.asarray(faces, dtype=np.int32).reshape(-1, 3)
    if verts.size == 0 or tri.size == 0:
        return np.zeros((0, 3), dtype=float), np.zeros((0, 3), dtype=np.int32)

    out_verts: list[np.ndarray] = []
    out_faces: list[list[int]] = []
    refine_steps = int(max(0, refine_steps))

    def _inside_centroid(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> bool:
        cent = (a + b + c) / 3.0
        return bool(_points_inside_wheel_cylinder_mask(
            points_xyz=cent.reshape(1, 3),
            wheel_center_xyz=wheel_center_xyz,
            wheel_axle_xyz=wheel_axle_xyz,
            wheel_up_xyz=wheel_up_xyz,
            wheel_radius_m=wheel_radius_m,
            wheel_width_m=wheel_width_m,
        )[0])

    def _tri_state(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> tuple[int, int]:
        samples = np.vstack([
            a, b, c,
            0.5 * (a + b),
            0.5 * (b + c),
            0.5 * (c + a),
            (a + b + c) / 3.0,
        ])
        mask = _points_inside_wheel_cylinder_mask(
            points_xyz=samples,
            wheel_center_xyz=wheel_center_xyz,
            wheel_axle_xyz=wheel_axle_xyz,
            wheel_up_xyz=wheel_up_xyz,
            wheel_radius_m=wheel_radius_m,
            wheel_width_m=wheel_width_m,
        )
        return int(np.count_nonzero(mask)), int(mask[-1])

    for face in tri:
        a, b, c = (np.asarray(verts[int(face[k])], dtype=float) for k in range(3))
        n_in, centroid_in = _tri_state(a, b, c)
        if n_in <= 0:
            continue
        subtris = [(a, b, c)]
        if n_in < 7 and refine_steps > 0:
            for _ in range(refine_steps):
                next_sub: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
                for ta, tb, tc in subtris:
                    n_sub, c_sub = _tri_state(ta, tb, tc)
                    if n_sub <= 0:
                        continue
                    if n_sub >= 7 or c_sub:
                        next_sub.append((ta, tb, tc))
                    else:
                        next_sub.extend(_subdivide_triangle_once(ta, tb, tc))
                subtris = next_sub
        for ta, tb, tc in subtris:
            if not _inside_centroid(ta, tb, tc):
                continue
            base = len(out_verts)
            out_verts.extend([ta, tb, tc])
            out_faces.append([base, base + 1, base + 2])

    if not out_faces:
        return np.zeros((0, 3), dtype=float), np.zeros((0, 3), dtype=np.int32)
    return np.asarray(out_verts, dtype=float), np.asarray(out_faces, dtype=np.int32)


def road_patch_faces_inside_wheel_cylinder(
    *,
    vertices_xyz: np.ndarray,
    faces: np.ndarray,
    wheel_center_xyz: np.ndarray,
    wheel_axle_xyz: np.ndarray,
    wheel_up_xyz: np.ndarray,
    wheel_radius_m: float,
    wheel_width_m: float,
) -> np.ndarray:
    """Return road-mesh faces that plausibly intersect the wheel volume.

    This keeps the legacy face-subset API for older callers, but uses a stricter
    sampling rule than "any vertex inside" to avoid oversized blocks in the
    contact patch. Newer callers should prefer ``road_patch_mesh_inside_wheel_cylinder``.
    """
    verts = np.asarray(vertices_xyz, dtype=float).reshape(-1, 3)
    tri = np.asarray(faces, dtype=np.int32).reshape(-1, 3)
    if verts.size == 0 or tri.size == 0:
        return np.zeros((0, 3), dtype=np.int32)
    pts = verts[tri]
    samples = np.concatenate([
        pts,
        0.5 * (pts[:, [0], :] + pts[:, [1], :]),
        0.5 * (pts[:, [1], :] + pts[:, [2], :]),
        0.5 * (pts[:, [2], :] + pts[:, [0], :]),
        pts.mean(axis=1, keepdims=True),
    ], axis=1)
    mask = _points_inside_wheel_cylinder_mask(
        points_xyz=samples.reshape(-1, 3),
        wheel_center_xyz=wheel_center_xyz,
        wheel_axle_xyz=wheel_axle_xyz,
        wheel_up_xyz=wheel_up_xyz,
        wheel_radius_m=wheel_radius_m,
        wheel_width_m=wheel_width_m,
    ).reshape(samples.shape[0], samples.shape[1])
    inside = (np.count_nonzero(mask, axis=1) >= 3) | mask[:, -1]
    if not np.any(inside):
        return np.zeros((0, 3), dtype=np.int32)
    return np.asarray(tri[inside], dtype=np.int32)


def contact_point_from_patch_faces(
    *,
    vertices_xyz: np.ndarray,
    faces: np.ndarray,
    wheel_center_xyz: np.ndarray,
    wheel_up_xyz: np.ndarray,
) -> np.ndarray | None:
    """Pick the highest physical road point on the selected patch under the wheel.

    Previous centroid-only selection was too coarse: on strongly curved roads it could
    drift away from the real mesh contact and visually detach the marker from the patch.
    We now choose from the actual patch vertices/faces, preferring the point that lies
    closest to the wheel along ``+up`` while remaining finite.
    """
    verts = np.asarray(vertices_xyz, dtype=float).reshape(-1, 3)
    tri = np.asarray(faces, dtype=np.int32).reshape(-1, 3)
    if verts.size == 0 or tri.size == 0:
        return None
    center = np.asarray(wheel_center_xyz, dtype=float).reshape(3)
    up = _safe_normalize(wheel_up_xyz, fallback_xyz=np.array([0.0, 0.0, 1.0], dtype=float))

    pts = np.vstack([verts[np.unique(tri.reshape(-1))], verts[tri].mean(axis=1)])
    pts = np.asarray(pts, dtype=float)
    if pts.size == 0:
        return None
    rel = pts - center.reshape(1, 3)
    score = rel @ up
    finite = np.isfinite(score)
    if not np.any(finite):
        return None
    idx = int(np.argmax(score[finite]))
    cand = pts[finite][idx]
    return np.asarray(cand, dtype=float)


def cylinder_dead_lengths_from_contract(
    *,
    bore_d_m: float,
    rod_d_m: float,
    dead_vol_m3: float,
) -> tuple[float | None, float | None]:
    """Return exact cap/rod dead lengths from canonical geometry contract."""
    bore = max(0.0, float(bore_d_m))
    rod = max(0.0, float(rod_d_m))
    dead = max(0.0, float(dead_vol_m3))
    if bore <= 0.0 or rod <= 0.0 or rod >= bore:
        return None, None
    a_cap = math.pi * (0.5 * bore) ** 2
    a_rod = a_cap - math.pi * (0.5 * rod) ** 2
    if not (np.isfinite(a_cap) and a_cap > 1e-12 and np.isfinite(a_rod) and a_rod > 1e-12):
        return None, None
    return float(dead / a_cap), float(dead / a_rod)


def _cylinder_piston_center_from_packaging(
    *,
    top_xyz: np.ndarray,
    bot_xyz: np.ndarray,
    stroke_pos_m: float,
    stroke_len_m: float,
    dead_cap_len_m: float,
    dead_rod_len_m: float,
    body_len_m: float | None = None,
    dead_height_m: float | None = None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Return the contract-derived piston plane center and axis.

    Canonical convention for the current project:
    - ``top`` is the frame/body side mount;
    - ``bot`` is the arm/rod side mount;
    - ``stroke_pos_m`` is rod extension in ``[0..S]``; larger values therefore move
      the piston toward the rod/arm side, not toward the cap/frame side.

    When the extended packaging contract is available, ``body_len_m`` is the fixed
    external cylinder body length and ``dead_height_m`` is the symmetric dead-space
    height derived from the chamber volume and piston area. Piston thickness is
    intentionally neglected.

    Fallback for old bundles: if ``body_len_m`` / ``dead_height_m`` are unavailable,
    use the historical dead-cap/dead-rod split along the current pin-to-pin axis.
    """
    top = np.asarray(top_xyz, dtype=float).reshape(3)
    bot = np.asarray(bot_xyz, dtype=float).reshape(3)
    axis = bot - top
    total_len = float(np.linalg.norm(axis))
    if not np.isfinite(total_len) or total_len <= 1e-9:
        return None, None
    stroke_len = max(0.0, float(stroke_len_m))
    if stroke_len <= 0.0:
        return None, None
    u = axis / total_len
    s = float(np.clip(stroke_pos_m, 0.0, stroke_len))

    body_len = None if body_len_m is None else float(max(0.0, float(body_len_m)))
    dead_h = None if dead_height_m is None else float(max(0.0, float(dead_height_m)))
    if body_len is not None and dead_h is not None and body_len > 1e-9:
        body_len_vis = float(min(max(body_len, 1e-9), total_len))
        wall = max(0.0, 0.5 * (body_len - stroke_len - 2.0 * dead_h))
        inner_start = min(body_len_vis, max(0.0, wall + dead_h))
        inner_end_nom = max(inner_start, body_len - wall - dead_h)
        inner_end = float(min(body_len_vis, inner_end_nom))
        travel = max(0.0, inner_end - inner_start)
        if stroke_len > 1e-12 and travel > 1e-12:
            piston_from_top = inner_start + (s / stroke_len) * travel
        else:
            piston_from_top = inner_start
        piston_from_top = float(np.clip(piston_from_top, 0.0, body_len_vis))
        piston_center = top + u * piston_from_top
        return np.asarray(piston_center, dtype=float), np.asarray(u, dtype=float)

    dead_cap = max(0.0, float(dead_cap_len_m))
    dead_rod = max(0.0, float(dead_rod_len_m))
    nom_total = dead_cap + stroke_len + dead_rod
    if nom_total > 1e-12:
        piston_u = float(np.clip((dead_cap + s) / nom_total, 0.0, 1.0))
    else:
        piston_u = float(np.clip(s / max(stroke_len, 1e-12), 0.0, 1.0))
    piston_from_top = float(np.clip(piston_u * total_len, 0.0, total_len))
    piston_center = top + u * piston_from_top
    return np.asarray(piston_center, dtype=float), np.asarray(u, dtype=float)


def cylinder_visual_state_from_packaging(
    *,
    top_xyz: np.ndarray,
    bot_xyz: np.ndarray,
    stroke_pos_m: float,
    stroke_len_m: float,
    bore_d_m: float,
    rod_d_m: float,
    outer_d_m: float,
    dead_cap_len_m: float,
    dead_rod_len_m: float,
    body_len_m: float | None = None,
    dead_height_m: float | None = None,
) -> dict[str, object] | None:
    """Return contract-first visual state for cylinder housing / rod / piston.

    Contract assumptions:
    - axis is exported explicitly by solver points (`top` -> `bot`);
    - bore / rod / stroke / outer diameter / dead lengths come from canonical bundle geometry;
    - no piston thickness is invented: the piston is represented as a disc at the exact
      contract-derived axial position.

    Current contract note:
    - when ``body_len_m`` / ``dead_height_m`` are provided, the renderer has enough data
      to draw a fixed external body shell, a piston plane moving toward the rod side as
      stroke grows, and a separate exposed rod segment;
    - when they are absent (old bundles), we fall back to the earlier pin-to-pin envelope
      interpretation instead of inventing geometry.
    """
    top = np.asarray(top_xyz, dtype=float).reshape(3)
    bot = np.asarray(bot_xyz, dtype=float).reshape(3)
    bore = max(0.0, float(bore_d_m))
    rod = max(0.0, float(rod_d_m))
    outer = max(0.0, float(outer_d_m))
    if bore <= 0.0 or rod <= 0.0 or outer <= 0.0 or rod >= bore or outer < bore:
        return None
    piston_center, axis_unit = _cylinder_piston_center_from_packaging(
        top_xyz=top,
        bot_xyz=bot,
        stroke_pos_m=stroke_pos_m,
        stroke_len_m=stroke_len_m,
        dead_cap_len_m=dead_cap_len_m,
        dead_rod_len_m=dead_rod_len_m,
        body_len_m=body_len_m,
        dead_height_m=dead_height_m,
    )
    if piston_center is None or axis_unit is None:
        return None
    piston_center = np.asarray(piston_center, dtype=float)
    axis_unit = np.asarray(axis_unit, dtype=float)

    housing_seg: tuple[np.ndarray, np.ndarray]
    rod_seg: tuple[np.ndarray, np.ndarray]
    if body_len_m is not None and dead_height_m is not None:
        total_len = float(np.linalg.norm(bot - top))
        body_len_vis = float(min(max(float(body_len_m), 1e-9), total_len))
        gland_point = top + axis_unit * body_len_vis
        housing_seg = (top, gland_point)
        # The opaque rod mesh represents only the exposed external rod. The internal
        # part is rendered separately by an overlay helper so it stays readable through
        # the translucent shell without falsely thickening the outer rod mesh.
        piston_proj = float(np.dot(piston_center - top, axis_unit))
        rod_start = gland_point if piston_proj <= body_len_vis + 1e-9 else piston_center
        rod_seg = (np.asarray(rod_start, dtype=float), bot)
    else:
        housing_seg = (top, bot)
        rod_seg = (piston_center, bot)

    return {
        "body_seg": (top, piston_center),
        "rod_seg": rod_seg,
        "housing_seg": housing_seg,
        "piston_center": piston_center,
        "axis_unit": axis_unit,
        "body_outer_radius_m": 0.5 * outer,
        "rod_radius_m": 0.5 * rod,
        "piston_radius_m": 0.5 * bore,
    }


def rod_centerline_vertices_from_packaging_state(state: dict[str, object] | None) -> np.ndarray | None:
    """Return a simple two-point rod centerline for renderer-side visibility overlays.

    The line is derived strictly from the already contract-derived ``rod_seg`` and
    therefore does not invent any geometry.  It exists only to help the renderer
    keep the rod readable through the translucent housing when mesh depth sorting
    makes the inner solid hard to perceive.
    """
    if not isinstance(state, dict):
        return None
    rod_seg = state.get("rod_seg")
    if not isinstance(rod_seg, (tuple, list)) or len(rod_seg) != 2:
        return None
    try:
        p0 = np.asarray(rod_seg[0], dtype=float).reshape(3)
        p1 = np.asarray(rod_seg[1], dtype=float).reshape(3)
    except Exception:
        return None
    if not (np.all(np.isfinite(p0)) and np.all(np.isfinite(p1))):
        return None
    return np.vstack([p0, p1]).astype(float, copy=False)


def rod_internal_centerline_vertices_from_packaging_state(state: dict[str, object] | None) -> np.ndarray | None:
    """Return only the rod segment that lies inside the transparent cylinder housing.

    This is a renderer readability overlay, not new geometry.  The segment starts at
    the already contract-derived piston center and ends at the housing/gland exit when
    that point is available.  Showing this inner core separately keeps the rod readable
    through translucent shells on Windows/OpenGL stacks that otherwise sort the meshes
    conservatively.
    """
    if not isinstance(state, dict):
        return None
    try:
        piston_center = state.get("piston_center")
        housing_seg = state.get("housing_seg")
        if piston_center is None:
            return None
        if not isinstance(housing_seg, (tuple, list)) or len(housing_seg) != 2:
            return None
        p0 = np.asarray(piston_center, dtype=float).reshape(3)
        p1 = np.asarray(housing_seg[1], dtype=float).reshape(3)
    except Exception:
        return None
    if not (np.all(np.isfinite(p0)) and np.all(np.isfinite(p1))):
        return None
    if float(np.linalg.norm(p1 - p0)) <= 1e-9:
        return None
    return np.vstack([p0, p1]).astype(float, copy=False)


def cylinder_visual_segments_from_state(
    *,
    top_xyz: np.ndarray,
    bot_xyz: np.ndarray,
    stroke_pos_m: float,
    stroke_len_m: float,
    bore_d_m: float,
    rod_d_m: float,
    dead_vol_m3: float,
) -> tuple[tuple[np.ndarray, np.ndarray] | None, tuple[np.ndarray, np.ndarray] | None, tuple[np.ndarray, np.ndarray] | None]:
    """Return honest body / rod / piston line geometry from canonical state.

    Unlike the old helper, this function does **not** invent piston thickness.
    The returned ``piston_seg`` is a zero-length segment at the exact piston plane
    center; callers may render it as a marker or as a disc mesh.
    """
    top = np.asarray(top_xyz, dtype=float).reshape(3)
    bot = np.asarray(bot_xyz, dtype=float).reshape(3)
    bore = max(0.0, float(bore_d_m))
    rod = max(0.0, float(rod_d_m))
    stroke_len = max(0.0, float(stroke_len_m))
    if bore <= 0.0 or rod <= 0.0 or stroke_len <= 0.0 or rod >= bore:
        return None, None, None
    dead_cap_len, dead_rod_len = cylinder_dead_lengths_from_contract(
        bore_d_m=bore,
        rod_d_m=rod,
        dead_vol_m3=float(dead_vol_m3),
    )
    if dead_cap_len is None or dead_rod_len is None:
        return None, None, None
    piston_center, _axis_unit = _cylinder_piston_center_from_packaging(
        top_xyz=top,
        bot_xyz=bot,
        stroke_pos_m=stroke_pos_m,
        stroke_len_m=stroke_len,
        dead_cap_len_m=dead_cap_len,
        dead_rod_len_m=dead_rod_len,
    )
    if piston_center is None:
        return None, None, None
    piston_center = np.asarray(piston_center, dtype=float)
    body_seg = (top, piston_center)
    rod_seg = (piston_center, bot)
    piston_seg = (piston_center, piston_center)
    return body_seg, rod_seg, piston_seg
