# -*- coding: utf-8 -*-
"""NPZ data loader for Desktop Animator.

The Streamlit UI exports full logs into an NPZ bundle with arrays:

  - main_cols, main_values
  - p_cols, p_values (optional)
  - q_cols, q_values (optional)
  - open_cols, open_values (optional)
  - meta_json (optional JSON string)

This module provides a robust loader and a convenience wrapper used by
`pneumo_solver_ui.desktop_animator`.

Design goals:
- be permissive about missing keys / slightly different formats,
- keep everything in NumPy arrays for animation speed,
- provide helper accessors for common signals (time, corners, world path).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import json
import logging
import math

import numpy as np
import pandas as pd

from pneumo_solver_ui.data_contract import (
    audit_main_columns,
    collect_geometry_contract_issues,
    normalize_npz_meta,
    read_visual_geometry_meta,
)
from pneumo_solver_ui.visual_contract import (
    collect_visual_cache_dependencies,
    collect_visual_contract_status,
    load_visual_road_sidecar,
    visual_cache_dependencies_token,
)
from pneumo_solver_ui.solver_points_contract import (
    POINT_KINDS as SOLVER_POINT_KINDS,
    point_cols as solver_point_cols,
)


logger = logging.getLogger(__name__)


CORNERS: Tuple[str, str, str, str] = ("ЛП", "ПП", "ЛЗ", "ПЗ")


def _coerce_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    if isinstance(x, bytes):
        try:
            return x.decode("utf-8", errors="ignore")
        except Exception:
            return str(x)
    # numpy scalar?
    try:
        if hasattr(x, "shape") and x.shape == ():
            return _coerce_str(x.item())
    except Exception:
        pass
    return str(x)


def _decode_meta(meta_raw: Any) -> Dict[str, Any]:
    s = _coerce_str(meta_raw).strip()
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {"_raw": s}


def _safe_float(x: Any, default: float) -> float:
    """Best-effort float conversion with NaN/inf guard."""
    try:
        v = float(x)
        if not np.isfinite(v):
            return float(default)
        return v
    except Exception:
        return float(default)


def _align_series_length(arr: Any, n: int, *, fill: float = 0.0) -> np.ndarray:
    """Align a 1D numeric series to length ``n`` without cyclic wraparound."""
    n = int(max(0, n))
    if n <= 0:
        return np.zeros((0,), dtype=float)
    vec = np.asarray(arr, dtype=float).reshape(-1)
    if vec.size >= n:
        return np.asarray(vec[:n], dtype=float)
    if vec.size <= 0:
        return np.full((n,), float(fill), dtype=float)
    pad_value = float(vec[-1]) if np.isfinite(float(vec[-1])) else float(fill)
    pad = np.full((n - vec.size,), pad_value, dtype=float)
    return np.concatenate([np.asarray(vec, dtype=float), pad], axis=0)


def _infer_wheelbase_from_meta(meta: Dict[str, Any]) -> Optional[float]:
    """Read wheelbase (meters) for visual consumers strictly from nested geometry.

    Old top-level/base fallbacks are intentionally ignored. Broken bundles must stay
    visibly broken (with warnings), not silently borrow geometry from another source.
    """
    if not isinstance(meta, dict):
        return None

    vis_geom = read_visual_geometry_meta(
        meta,
        context="Desktop Animator road-profile meta_json",
        log=lambda m: logger.warning("[Animator] %s", m),
    )
    wb = vis_geom.get("wheelbase_m")
    if wb is None:
        return None
    wb = _safe_float(wb, float("nan"))
    if np.isfinite(wb) and wb > 0.0:
        return float(wb)
    return None


@dataclass
class NpzTable:
    cols: List[str]
    values: np.ndarray  # shape: (T, C)

    def has(self, name: str) -> bool:
        return name in self.cols

    def index_of(self, name: str) -> Optional[int]:
        try:
            return self.cols.index(name)
        except ValueError:
            return None

    def column(self, name: str, default: Any = 0.0) -> Any:
        """Return a column as a 1D float array.
    
        Important: when *default* is None and the column is missing, return None.
        This is used widely in the Animator as a cheap presence-test for optional signals.
        """
        idx = self.index_of(name)
        if idx is None:
            if default is None:
                return None
            dv = _safe_float(default, 0.0)
            return np.full((self.values.shape[0],), dv, dtype=float)
        col = self.values[:, idx]
        # values are expected to be float already (loader coerces), but keep it robust
        try:
            return np.asarray(col, dtype=float)
        except Exception:
            try:
                s = pd.to_numeric(pd.Series(col), errors='coerce')
                return np.asarray(s.to_numpy(copy=True), dtype=float)
            except Exception:
                return np.full((self.values.shape[0],), np.nan, dtype=float)
    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.values, columns=self.cols)


@dataclass
class DataBundle:
    npz_path: Path
    main: NpzTable
    p: Optional[NpzTable] = None
    q: Optional[NpzTable] = None
    open: Optional[NpzTable] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    contract_issues: List[str] = field(default_factory=list)
    # === LAW (ABSOLUTE-ONLY ANIMATION) ===
    # Desktop Animator must render **exactly** the signals exported by the
    # mathematical model.
    #
    # This means:
    #   - No "special drawing bases" (no hidden offsets, no implicit zero-pose).
    #   - Basis MUST be explicit: ABS vs *_rel0.
    #   - If prefer_rel0=True we *prefer* `*_rel0` channels.
    #   - We never reconstruct ABS geometry from rel0.
    #   - Deriving rel0 from ABS is allowed as SERVICE/DERIVED.
    #
    # Therefore, prefer_rel0 is a real runtime choice (not ignored), but any
    # fallback/basis mismatch is considered suspicious and must be logged.
    prefer_rel0: bool = False

    # Derived caches (computed lazily)
    _derived: Dict[str, np.ndarray] = field(default_factory=dict, init=False, repr=False)
    _warned_codes: Set[str] = field(default_factory=set, init=False, repr=False)

    def _warn_once(self, code: str, msg: str, *args: Any) -> None:
        if code in self._warned_codes:
            return
        self._warned_codes.add(code)
        logger.warning(msg, *args)

    @property
    def geometry_contract_ok(self) -> bool:
        return not bool(self.contract_issues)

    @property
    def t(self) -> np.ndarray:
        """Time vector (seconds)."""
        if self.main.has("время_с"):
            return self.main.column("время_с")
        # Fall back: first column looks like time?
        return self.main.values[:, 0].astype(float)

    def get(self, name: str, default: Any = 0.0) -> Any:
        """Return a channel using the preferred basis.

        Contract:
          - No silent alias mapping.
          - No reconstruction of ABS geometry from rel0.
          - Deriving rel0 from ABS is allowed as SERVICE/DERIVED.

        Presence-test mode:
          - If default is None and the column is missing, returns None.
        """

        if name in self._derived:
            return self._derived[name]

        # Explicit rel0 request means "try exactly this".
        if name.endswith("_rel0"):
            return self.main.column(name, default=default)

        if self.prefer_rel0:
            # 1) Prefer explicit rel0 channel.
            rel0 = self.main.column(name + "_rel0", default=None)
            if rel0 is not None:
                return rel0

            # 2) Derive rel0 from ABS (SERVICE/DERIVED).
            abs_col = self.main.column(name, default=None)
            if abs_col is not None:
                self._warn_once(
                    f"derive_rel0::{name}",
                    "Missing '%s_rel0'; deriving rel0 from ABS '%s' as SERVICE/DERIVED.",
                    name,
                    name,
                )
                arr = abs_col.astype(float)
                return arr - float(arr[0])

            # 3) Missing
            return self.main.column(name, default=default)

        # prefer ABS
        abs_col = self.main.column(name, default=None)
        if abs_col is not None:
            return abs_col

        # ABSOLUTE LAW: do not silently substitute *_rel0 into the ABS rendering path.
        rel0_only = self.main.column(name + "_rel0", default=None)
        if rel0_only is not None:
            self._warn_once(
                f"missing_abs::{name}",
                "Missing ABS '%s', but '%s_rel0' exists. No implicit rel0 fallback is performed for animation; using default=%r.",
                name,
                name,
                default,
            )
            return self.main.column(name, default=default)

        return self.main.column(name, default=default)

    def get_abs(self, name: str, default: float = 0.0) -> np.ndarray:
        """Return ABS-basis channel (no `_rel0`).

        NOTE: This is NOT abs(value). It is ABS vs rel0 basis.

        ABSOLUTE LAW:
          - explicit ABS request stays strict; rel0 is never auto-substituted here.
        """
        base = name[:-5] if name.endswith("_rel0") else name
        a = self.main.column(base, default=None)
        if a is not None:
            return a.astype(float)
        rel0 = self.main.column(base + "_rel0", default=None)
        if rel0 is not None:
            self._warn_once(
                f"missing_abs_explicit::{base}",
                "ABS '%s' missing while '%s_rel0' exists. Explicit ABS request stays strict; using default=%r.",
                base,
                base,
                default,
            )
            return np.full((self.main.values.shape[0],), _safe_float(default, 0.0), dtype=float)
        self._warn_once(
            f"missing_abs_default::{base}",
            "Missing ABS '%s'; using default=%r",
            base,
            default,
        )
        return np.full((self.main.values.shape[0],), _safe_float(default, 0.0), dtype=float)

    def get_rel0(self, name: str, default: float = 0.0) -> np.ndarray:
        """Return rel0-basis channel.

        If explicit `*_rel0` exists -> return it.
        Otherwise derive from ABS as SERVICE/DERIVED: x_rel0 = x - x[0].
        """
        base = name[:-5] if name.endswith("_rel0") else name
        rel0 = self.main.column(base + "_rel0", default=None)
        if rel0 is not None:
            return rel0.astype(float)
        a = self.main.column(base, default=None)
        if a is not None:
            arr = a.astype(float)
            self._warn_once(
                f"derive_rel0_explicit::{base}",
                "Missing '%s_rel0'; deriving rel0 from ABS '%s' as SERVICE/DERIVED.",
                base,
                base,
            )
            return arr - float(arr[0])
        self._warn_once(
            f"missing_rel0_and_abs::{base}",
            "Missing rel0 '%s_rel0' and ABS '%s'; using default=%r",
            base,
            base,
            default,
        )
        return np.full((self.main.values.shape[0],), _safe_float(default, 0.0), dtype=float)

    def corner(self, pattern: str, corner: str, default: float = 0.0) -> np.ndarray:
        """Access corner signals by pattern.

        Example:
            corner("перемещение_колеса_{c}_м", "ЛП")
        """
        return self.get(pattern.format(c=corner), default=default)

    @staticmethod
    def frame_corner_key(corner: str, component: str = "z") -> str:
        """Return the single canonical frame-corner key.

        component:
          - "z" -> `рама_угол_{corner}_z_м`
          - "v" -> `рама_угол_{corner}_v_м_с`
          - "a" -> `рама_угол_{corner}_a_м_с2`

        ABSOLUTE LAW:
          - No alias fallback.
          - No legacy runtime bridges.
        """
        suffix_map = {
            "z": "z_м",
            "v": "v_м_с",
            "a": "a_м_с2",
        }
        if component not in suffix_map:
            raise ValueError(f"Unsupported frame-corner component: {component!r}")
        return f"рама_угол_{corner}_{suffix_map[component]}"

    def frame_corner_z(self, corner: str, default: float = 0.0) -> np.ndarray:
        return np.asarray(self.get(self.frame_corner_key(corner, "z"), default=default), dtype=float)

    def frame_corner_v(self, corner: str, default: float = 0.0) -> np.ndarray:
        return np.asarray(self.get(self.frame_corner_key(corner, "v"), default=default), dtype=float)

    def frame_corner_a(self, corner: str, default: float = 0.0) -> np.ndarray:
        return np.asarray(self.get(self.frame_corner_key(corner, "a"), default=default), dtype=float)

    def frame_corner_xyz(self, corner: str) -> Optional[np.ndarray]:
        """Return canonical frame-corner solver-point triplet as (T,3) array or None.

        This is the honest world-space corner point above each wheel/suspension corner.
        No synthetic reconstruction is allowed here; producers must export the triplet.
        """
        return self.point_xyz("frame_corner", corner)

    def wheel_center_xyz(self, corner: str) -> Optional[np.ndarray]:
        """Return canonical wheel-center solver-point triplet as (T,3) array or None."""
        return self.point_xyz("wheel_center", corner)

    def road_contact_xyz(self, corner: str) -> Optional[np.ndarray]:
        """Return canonical road-contact solver-point triplet as (T,3) array or None."""
        return self.point_xyz("road_contact", corner)

    def road_series(self, corner: str, *, allow_sidecar: bool = True) -> Optional[np.ndarray]:
        """Return canonical road trace for a corner or None.

        No synthetic zero road is allowed here. If the trace is missing, callers must
        explicitly handle the missing-data state.
        """
        col = self.main.column(f"дорога_{corner}_м", default=None)
        if col is not None:
            return np.asarray(col, dtype=float)
        if allow_sidecar:
            try:
                wheels_sidecar = self._ensure_road_sidecar_wheels()
            except Exception:
                wheels_sidecar = None
            if isinstance(wheels_sidecar, dict) and corner in wheels_sidecar:
                return np.asarray(wheels_sidecar[corner], dtype=float)
        return None

    def missing_road_corners(self) -> List[str]:
        return [corner for corner in CORNERS if self.road_series(corner) is None]

    def has_full_road_traces(self) -> bool:
        return not bool(self.missing_road_corners())

    def derived(self, name: str) -> Optional[np.ndarray]:
        return self._derived.get(name)

    def point_xyz(self, kind: str, corner: str) -> Optional[np.ndarray]:
        """Return a canonical solver-point triplet as (T,3) array or None.

        No aliases and no synthetic reconstruction are allowed here. If a triplet is
        only partially present, we warn and return None.
        """
        try:
            cx, cy, cz = solver_point_cols(kind, corner)
        except Exception as e:
            logger.warning(
                "[Animator] Unknown solver-point kind '%s' requested for corner %s: %s",
                kind,
                corner,
                e,
            )
            return None
        ax = self.main.column(cx, default=None)
        ay = self.main.column(cy, default=None)
        az = self.main.column(cz, default=None)

        present = [ax is not None, ay is not None, az is not None]
        if not any(present):
            return None
        if not all(present):
            logger.warning(
                "[Animator] Partial solver-point triplet for %s/%s in NPZ. Expected %s, %s, %s together.",
                kind,
                corner,
                cx,
                cy,
                cz,
            )
            return None

        return np.column_stack([
            np.asarray(ax, dtype=float),
            np.asarray(ay, dtype=float),
            np.asarray(az, dtype=float),
        ])

    def has_solver_points(self) -> bool:
        """Whether the full canonical solver-point contract is present."""
        for kind in SOLVER_POINT_KINDS:
            for corner in CORNERS:
                if self.point_xyz(kind, corner) is None:
                    return False
        return True

    # ------------------------------
    # Sidecar helpers (anim_latest)
    # ------------------------------

    def _resolve_sidecar_path(self, p: str | Path) -> Path:
        """Resolve a sidecar path stored in meta.

        In anim_latest we store relative names (portable bundle), so we resolve
        them relative to the NPZ folder.
        """
        pp = Path(str(p)).expanduser()
        if pp.is_absolute():
            return pp
        return (self.npz_path.parent / pp).resolve()

    def _ensure_road_sidecar_wheels(self) -> Optional[Dict[str, np.ndarray]]:
        """Load road_csv sidecar (if any) and expose wheel traces.

        Returns dict with keys: 'ЛП','ПП','ЛЗ','ПЗ'.
        Arrays are aligned to bundle.t (interpolated if necessary).
        """
        key = "_road_sidecar_wheels"
        if key in self._derived:
            return self._derived[key]  # type: ignore[return-value]

        src = (self.meta or {}).get("road_csv")
        if not src:
            self._derived[key] = None  # type: ignore[assignment]
            return None

        csv_path: Optional[Path] = None
        try:
            csv_path = self._resolve_sidecar_path(str(src))
            if not csv_path.exists():
                self._derived[key] = None  # type: ignore[assignment]
                return None

            df = pd.read_csv(csv_path)
            if "t" not in df.columns:
                self._derived[key] = None  # type: ignore[assignment]
                return None

            t_src = np.asarray(df["t"], dtype=float)
            zcols = [c for c in ("z0", "z1", "z2", "z3") if c in df.columns]
            if len(zcols) != 4:
                # fallback: take first 4 columns starting with 'z'
                alt = [c for c in df.columns if str(c).lower().startswith("z")]
                if len(alt) >= 4:
                    zcols = alt[:4]
            if len(zcols) != 4:
                self._derived[key] = None  # type: ignore[assignment]
                return None

            z0 = np.asarray(df[zcols[0]], dtype=float)
            z1 = np.asarray(df[zcols[1]], dtype=float)
            z2 = np.asarray(df[zcols[2]], dtype=float)
            z3 = np.asarray(df[zcols[3]], dtype=float)

            t = np.asarray(self.t, dtype=float)
            if t_src.size >= 2 and (t_src.shape != t.shape or float(np.max(np.abs(t_src - t))) > 1e-9):
                z0 = np.interp(t, t_src, z0, left=float(z0[0]), right=float(z0[-1]))
                z1 = np.interp(t, t_src, z1, left=float(z1[0]), right=float(z1[-1]))
                z2 = np.interp(t, t_src, z2, left=float(z2[0]), right=float(z2[-1]))
                z3 = np.interp(t, t_src, z3, left=float(z3[0]), right=float(z3[-1]))

            wheels = {"ЛП": z0, "ПП": z1, "ЛЗ": z2, "ПЗ": z3}
            self._derived[key] = wheels  # type: ignore[assignment]
            return wheels

        except Exception as e:
            logger.warning(
                "[Animator] Failed to load road sidecar wheels from %s: %s",
                str(csv_path or src),
                e,
                exc_info=True,
            )
            self._derived[key] = None  # type: ignore[assignment]
            return None

    def ensure_world_xy(self) -> Tuple[np.ndarray, np.ndarray]:
        """Compute world-frame path (SERVICE/DERIVED: svc__x_world_м, svc__y_world_м).

        Source priority (no hidden aliases):
          1) explicit canonical path columns: ``путь_x_м`` / ``путь_y_м``;
          2) derived integration of ``скорость_vx_м_с`` and ``yaw_рад``.

        Why this order matters:
        - modern bundles already export the actual world path from the solver;
        - re-integrating ``vx*cos(yaw)``, ``vx*sin(yaw)`` throws away information whenever
          the solver also exports a genuine lateral world motion / drift trajectory.
        """
        key_x = "svc__x_world_м"
        key_y = "svc__y_world_м"
        if key_x in self._derived and key_y in self._derived:
            return self._derived[key_x], self._derived[key_y]

        t = self.t
        n = int(len(t))
        if n <= 0:
            self._derived[key_x] = np.zeros((0,), dtype=float)
            self._derived[key_y] = np.zeros((0,), dtype=float)
            return self._derived[key_x], self._derived[key_y]

        try:
            if self.main.has("путь_x_м") and self.main.has("путь_y_м"):
                xw = np.asarray(self.get("путь_x_м", default=0.0), dtype=float)
                yw = np.asarray(self.get("путь_y_м", default=0.0), dtype=float)
                if xw.size == n and yw.size == n:
                    self._derived[key_x] = xw
                    self._derived[key_y] = yw
                    return xw, yw
        except Exception:
            pass

        self._warn_once(
            "ensure_world_xy::integrated_fallback",
            "[Animator] Missing canonical path columns 'путь_x_м'/'путь_y_м'; deriving world XY from скорость_vx_м_с + скорость_vy_м_с + yaw_рад as SERVICE/DERIVED.",
        )
        vx = _align_series_length(self.get("скорость_vx_м_с", default=0.0), n, fill=0.0)
        vy = _align_series_length(self.get("скорость_vy_м_с", default=0.0), n, fill=0.0)
        yaw = _align_series_length(self.get("yaw_рад", default=0.0), n, fill=0.0)

        dt = np.diff(t, prepend=t[0])
        dt[0] = 0.0
        dx = vx * np.cos(yaw) - vy * np.sin(yaw)
        dy = vx * np.sin(yaw) + vy * np.cos(yaw)

        xw = np.zeros((n,), dtype=float)
        yw = np.zeros((n,), dtype=float)
        for i in range(1, n):
            xw[i] = xw[i - 1] + 0.5 * (dx[i - 1] + dx[i]) * dt[i]
            yw[i] = yw[i - 1] + 0.5 * (dy[i - 1] + dy[i]) * dt[i]

        self._derived[key_x] = xw
        self._derived[key_y] = yw
        return xw, yw

    def ensure_world_velocity_xy(self) -> Tuple[np.ndarray, np.ndarray]:
        """World-frame XY velocity from explicit path if available, else from body vx/vy/yaw."""
        key_x = "svc__vx_world_м_с"
        key_y = "svc__vy_world_м_с"
        if key_x in self._derived and key_y in self._derived:
            return self._derived[key_x], self._derived[key_y]

        t = np.asarray(self.t, dtype=float)
        n = int(len(t))
        if n <= 0:
            self._derived[key_x] = np.zeros((0,), dtype=float)
            self._derived[key_y] = np.zeros((0,), dtype=float)
            return self._derived[key_x], self._derived[key_y]

        xw, yw = self.ensure_world_xy()
        try:
            if n >= 2:
                vxw = np.asarray(np.gradient(xw, t, edge_order=1), dtype=float)
                vyw = np.asarray(np.gradient(yw, t, edge_order=1), dtype=float)
            else:
                vxw = np.zeros((n,), dtype=float)
                vyw = np.zeros((n,), dtype=float)
        except Exception:
            yaw = _align_series_length(self.get("yaw_рад", default=0.0), n, fill=0.0)
            vx = _align_series_length(self.get("скорость_vx_м_с", default=0.0), n, fill=0.0)
            vy = _align_series_length(self.get("скорость_vy_м_с", default=0.0), n, fill=0.0)
            vxw = vx * np.cos(yaw) - vy * np.sin(yaw)
            vyw = vx * np.sin(yaw) + vy * np.cos(yaw)
        self._derived[key_x] = vxw
        self._derived[key_y] = vyw
        return vxw, vyw

    def ensure_body_velocity_xy(self) -> Tuple[np.ndarray, np.ndarray]:
        """Body-frame XY velocity reconstructed from world path + yaw."""
        key_x = "svc__vx_body_м_с"
        key_y = "svc__vy_body_м_с"
        if key_x in self._derived and key_y in self._derived:
            return self._derived[key_x], self._derived[key_y]
        vxw, vyw = self.ensure_world_velocity_xy()
        yaw = _align_series_length(self.get("yaw_рад", default=0.0), int(len(vxw)), fill=0.0)
        c = np.cos(yaw)
        s = np.sin(yaw)
        vxb = c * vxw + s * vyw
        vyb = -s * vxw + c * vyw
        self._derived[key_x] = np.asarray(vxb, dtype=float)
        self._derived[key_y] = np.asarray(vyb, dtype=float)
        return self._derived[key_x], self._derived[key_y]

    def ensure_world_acceleration_xy(self) -> Tuple[np.ndarray, np.ndarray]:
        """World-frame XY acceleration.

        Priority:
          1) derivative of explicit world-path velocity;
          2) rotation of canonical body-frame ``ax/ay`` into world frame.
        """
        key_x = "svc__ax_world_м_с2"
        key_y = "svc__ay_world_м_с2"
        if key_x in self._derived and key_y in self._derived:
            return self._derived[key_x], self._derived[key_y]

        t = np.asarray(self.t, dtype=float)
        n = int(len(t))
        if n <= 0:
            self._derived[key_x] = np.zeros((0,), dtype=float)
            self._derived[key_y] = np.zeros((0,), dtype=float)
            return self._derived[key_x], self._derived[key_y]

        try:
            if self.main.has("путь_x_м") and self.main.has("путь_y_м") and n >= 2:
                vxw, vyw = self.ensure_world_velocity_xy()
                axw = np.asarray(np.gradient(vxw, t, edge_order=1), dtype=float)
                ayw = np.asarray(np.gradient(vyw, t, edge_order=1), dtype=float)
                self._derived[key_x] = axw
                self._derived[key_y] = ayw
                return axw, ayw
        except Exception:
            pass

        yaw = _align_series_length(self.get("yaw_рад", default=0.0), n, fill=0.0)
        axb = _align_series_length(self.get("ускорение_продольное_ax_м_с2", default=0.0), n, fill=0.0)
        ayb = _align_series_length(self.get("ускорение_поперечное_ay_м_с2", default=0.0), n, fill=0.0)
        c = np.cos(yaw)
        s = np.sin(yaw)
        axw = c * axb - s * ayb
        ayw = s * axb + c * ayb
        self._derived[key_x] = np.asarray(axw, dtype=float)
        self._derived[key_y] = np.asarray(ayw, dtype=float)
        return self._derived[key_x], self._derived[key_y]

    def ensure_body_acceleration_xy(self) -> Tuple[np.ndarray, np.ndarray]:
        """Canonical body-frame acceleration ``ax/ay`` when present, else rotate from world."""
        key_x = "svc__ax_body_м_с2"
        key_y = "svc__ay_body_м_с2"
        if key_x in self._derived and key_y in self._derived:
            return self._derived[key_x], self._derived[key_y]

        try:
            if self.main.has("ускорение_продольное_ax_м_с2") and self.main.has("ускорение_поперечное_ay_м_с2"):
                n = int(len(self.t))
                axb = _align_series_length(self.get("ускорение_продольное_ax_м_с2", default=0.0), n, fill=0.0)
                ayb = _align_series_length(self.get("ускорение_поперечное_ay_м_с2", default=0.0), n, fill=0.0)
                self._derived[key_x] = axb
                self._derived[key_y] = ayb
                return axb, ayb
        except Exception:
            pass

        axw, ayw = self.ensure_world_acceleration_xy()
        yaw = _align_series_length(self.get("yaw_рад", default=0.0), int(len(axw)), fill=0.0)
        c = np.cos(yaw)
        s = np.sin(yaw)
        axb = c * axw + s * ayw
        ayb = -s * axw + c * ayw
        self._derived[key_x] = np.asarray(axb, dtype=float)
        self._derived[key_y] = np.asarray(ayb, dtype=float)
        return self._derived[key_x], self._derived[key_y]

    def ensure_road_profile(self, wheelbase_m: Optional[float] = None, mode: str = "center") -> Tuple[np.ndarray, np.ndarray]:
        """Reconstruct a 1D road profile z(s) from per-wheel road traces.

        The solver typically stores road height under each wheel ("дорога_ЛП_м" etc.)
        at each time step i. Because wheels are longitudinally offset by ±wheelbase/2
        relative to the vehicle reference point, those traces are effectively samples of
        z(s) at shifted s positions. This helper merges front/rear traces into a single
        monotonic (s, z) table suitable for interpolation (np.interp).

        Parameters
        ----------
        wheelbase_m:
            Vehicle wheelbase in meters.
        mode:
            "left"   -> use ЛП + ЛЗ
            "right"  -> use ПП + ПЗ
            "center" -> average left/right per axle, then merge front+rear
        """
        if wheelbase_m is None:
            wheelbase_m = _infer_wheelbase_from_meta(self.meta)

        # ABSOLUTE LAW: no invented defaults. If wheelbase is missing/invalid we disable
        # the derived road profile instead of guessing.
        if wheelbase_m is None:
            msg = (
                "[Animator] wheelbase_m is missing in meta_json — road profile reconstruction disabled. "
                "Fix exporter to include canonical key 'wheelbase_m'."
            )
            logger.warning(msg)
            raise ValueError(msg)

        wb = _safe_float(wheelbase_m, float("nan"))
        if wb <= 0.0 or not np.isfinite(wb):
            msg = f"[Animator] wheelbase_m must be a positive finite float, got {wheelbase_m!r} — road profile disabled."
            logger.warning(msg)
            raise ValueError(msg)

        mode = str(mode).lower().strip()
        if mode not in ("left", "right", "center"):
            raise ValueError(f"mode must be one of: left/right/center, got {mode!r}")

        wb_key = f"{wb:.6f}"
        key_s = f"svc__road_profile_s_{mode}_{wb_key}"
        key_z = f"svc__road_profile_z_{mode}_{wb_key}"
        if key_s in self._derived and key_z in self._derived:
            return self._derived[key_s], self._derived[key_z]

        s = np.asarray(self.ensure_s_world(), dtype=float)
        off_front = 0.5 * wb
        off_rear = -0.5 * wb

        # If solver did not record per-wheel road traces, try road_csv sidecar (anim_latest).
        wheels_sidecar = None
        try:
            has_any = any(
                self.main.has(c)
                for c in ("дорога_ЛП_м", "дорога_ПП_м", "дорога_ЛЗ_м", "дорога_ПЗ_м")
            )
            if not has_any:
                wheels_sidecar = self._ensure_road_sidecar_wheels()
        except Exception:
            wheels_sidecar = None

        if wheels_sidecar:
            # sidecar provides: ЛП/ПП/ЛЗ/ПЗ
            if mode == "left":
                zF = np.asarray(wheels_sidecar["ЛП"], dtype=float)
                zR = np.asarray(wheels_sidecar["ЛЗ"], dtype=float)
            elif mode == "right":
                zF = np.asarray(wheels_sidecar["ПП"], dtype=float)
                zR = np.asarray(wheels_sidecar["ПЗ"], dtype=float)
            else:  # center
                zF = 0.5 * (np.asarray(wheels_sidecar["ЛП"], dtype=float) + np.asarray(wheels_sidecar["ПП"], dtype=float))
                zR = 0.5 * (np.asarray(wheels_sidecar["ЛЗ"], dtype=float) + np.asarray(wheels_sidecar["ПЗ"], dtype=float))
        else:
            if mode == "left":
                zF = self.road_series("ЛП", allow_sidecar=False)
                zR = self.road_series("ЛЗ", allow_sidecar=False)
                missing = [c for c, arr in (("ЛП", zF), ("ЛЗ", zR)) if arr is None]
            elif mode == "right":
                zF = self.road_series("ПП", allow_sidecar=False)
                zR = self.road_series("ПЗ", allow_sidecar=False)
                missing = [c for c, arr in (("ПП", zF), ("ПЗ", zR)) if arr is None]
            else:  # center
                zFL = self.road_series("ЛП", allow_sidecar=False)
                zFR = self.road_series("ПП", allow_sidecar=False)
                zRL = self.road_series("ЛЗ", allow_sidecar=False)
                zRR = self.road_series("ПЗ", allow_sidecar=False)
                missing = [
                    c
                    for c, arr in (("ЛП", zFL), ("ПП", zFR), ("ЛЗ", zRL), ("ПЗ", zRR))
                    if arr is None
                ]
                zF = None if (zFL is None or zFR is None) else 0.5 * (np.asarray(zFL, dtype=float) + np.asarray(zFR, dtype=float))
                zR = None if (zRL is None or zRR is None) else 0.5 * (np.asarray(zRL, dtype=float) + np.asarray(zRR, dtype=float))
            if missing or zF is None or zR is None:
                msg = (
                    f"[Animator] Missing canonical road traces for mode={mode!r}; road profile disabled. "
                    f"Missing corners: {', '.join(missing) if missing else 'unknown'}"
                )
                logger.warning(msg)
                raise ValueError(msg)
            zF = np.asarray(zF, dtype=float)
            zR = np.asarray(zR, dtype=float)

        sF = s + off_front
        sR = s + off_rear
        s_all = np.concatenate([sF, sR])
        z_all = np.concatenate([zF, zR])

        m = np.isfinite(s_all) & np.isfinite(z_all)
        s_all = s_all[m]
        z_all = z_all[m]
        if s_all.size < 2:
            msg = "[Animator] Road profile reconstruction has fewer than 2 finite samples — NO ROAD DATA."
            logger.warning(msg)
            raise ValueError(msg)

        order = np.argsort(s_all)
        s_sorted = np.asarray(s_all[order], dtype=float)
        z_sorted = np.asarray(z_all[order], dtype=float)

        # Front/rear traces can overlap in s very densely (especially on turns).
        # Keeping those overlaps as separate consecutive points creates an artificial
        # saw-tooth / "accordion" road in 3D. We therefore merge samples inside a
        # service bin tied to the native longitudinal step of the simulation.
        ds_native = np.diff(np.asarray(s, dtype=float))
        ds_native = ds_native[np.isfinite(ds_native) & (ds_native > 1e-6)]
        native_step = float(np.median(ds_native)) if ds_native.size else float("nan")
        if (not np.isfinite(native_step)) or native_step <= 1e-6:
            native_step = float(np.nanmedian(np.diff(s_sorted))) if s_sorted.size >= 2 else 0.05
        if (not np.isfinite(native_step)) or native_step <= 1e-6:
            native_step = 0.05
        # Half-native bins are enough to collapse redundant overlaps while still
        # preserving all meaningful roughness present in the traces.
        bin_dx = float(max(1e-4, 0.5 * native_step))
        s0 = float(s_sorted[0])
        s1 = float(s_sorted[-1])
        n_bins = int(max(2, math.floor((s1 - s0) / bin_dx) + 1))
        centers = s0 + np.arange(n_bins, dtype=float) * bin_dx
        bin_idx = np.rint((s_sorted - s0) / bin_dx).astype(np.int64)
        bin_idx = np.clip(bin_idx, 0, n_bins - 1)

        sums = np.bincount(bin_idx, weights=z_sorted, minlength=n_bins).astype(float)
        cnts = np.bincount(bin_idx, minlength=n_bins).astype(np.int64)
        valid = cnts > 0
        if not np.any(valid):
            msg = "[Animator] Road profile binning produced no valid samples — NO ROAD DATA."
            logger.warning(msg)
            raise ValueError(msg)

        # Diagnostic only: overlapping bins with large internal spread indicate that
        # front/rear traces disagree locally (common on tight turns). We average them
        # instead of keeping the false zig-zag, but we log once because this affects
        # visual fidelity expectations.
        try:
            z_min = np.full((n_bins,), np.inf, dtype=float)
            z_max = np.full((n_bins,), -np.inf, dtype=float)
            np.minimum.at(z_min, bin_idx, z_sorted)
            np.maximum.at(z_max, bin_idx, z_sorted)
            spread = z_max - z_min
            max_spread = float(np.nanmax(spread[valid])) if np.any(valid) else 0.0
            if np.isfinite(max_spread) and max_spread > 0.02:
                self._warn_once(
                    f"road_profile_overlap::{mode}",
                    "[Animator] Overlapping road traces for mode=%s disagree by up to %.1f mm within one longitudinal bin; using bin-averaged service profile to avoid accordion artefacts.",
                    mode,
                    1000.0 * max_spread,
                )
        except Exception:
            pass

        ss = np.asarray(centers[valid], dtype=float)
        zz = np.asarray(sums[valid] / np.maximum(1, cnts[valid]), dtype=float)
        self._derived[key_s] = ss
        self._derived[key_z] = zz
        return ss, zz

    def ensure_s_world(self) -> np.ndarray:
        """Compute traveled distance (meters) as a monotonic function of time.

        Source priority (no hidden aliases):
          1) arc length of explicit canonical path ``путь_x_м``/``путь_y_м``;
          2) trapezoidal integration of canonical body-speed magnitude
             ``hypot(скорость_vx_м_с, скорость_vy_м_с)``.
        """
        key = "svc__s_world_м"
        if key in self._derived:
            return self._derived[key]

        t = self.t
        n = int(len(t))
        if n <= 0:
            self._derived[key] = np.zeros((0,), dtype=float)
            return self._derived[key]

        try:
            if self.main.has("путь_x_м") and self.main.has("путь_y_м"):
                xw, yw = self.ensure_world_xy()
                ds = np.hypot(np.diff(xw, prepend=xw[0]), np.diff(yw, prepend=yw[0]))
                s = np.cumsum(ds, dtype=float)
                if s.size:
                    s[0] = 0.0
                self._derived[key] = np.asarray(s, dtype=float)
                return self._derived[key]
        except Exception:
            pass

        vx = None
        vy = None
        try:
            if self.main.has("скорость_vx_м_с"):
                vx = _align_series_length(self.get("скорость_vx_м_с", default=0.0), n, fill=0.0)
            if self.main.has("скорость_vy_м_с"):
                vy = _align_series_length(self.get("скорость_vy_м_с", default=0.0), n, fill=0.0)
        except Exception:
            vx = None
            vy = None

        if vx is None:
            logger.warning(
                "[Animator] Missing signal 'скорость_vx_м_с' in NPZ. s_world axis will be zero (no inferred speed)."
            )
            vx = np.zeros((n,), dtype=float)
        if vy is None:
            vy = np.zeros((n,), dtype=float)

        v = np.asarray(np.hypot(vx, vy), dtype=float)
        dt = np.diff(t, prepend=t[0])
        dt[0] = 0.0
        s = np.zeros((n,), dtype=float)
        for i in range(1, n):
            s[i] = s[i - 1] + 0.5 * (v[i - 1] + v[i]) * dt[i]

        self._derived[key] = s
        return s


def _load_table(npz: np.lib.npyio.NpzFile, prefix: str) -> Optional[NpzTable]:
    cols_key = f"{prefix}_cols"
    vals_key = f"{prefix}_values"
    if cols_key not in npz or vals_key not in npz:
        return None

    cols_raw = npz[cols_key]
    # cols are stored as dtype=object; convert to list[str]
    cols: List[str] = []
    try:
        for c in cols_raw.tolist():
            cols.append(_coerce_str(c))
    except Exception:
        cols = [str(c) for c in cols_raw]

    values = np.asarray(npz[vals_key], dtype=float)
    if values.ndim != 2:
        values = np.atleast_2d(values)

    return NpzTable(cols=cols, values=values)


def load_npz(path: str | Path) -> DataBundle:
    """Load an NPZ export produced by the UI."""
    pth = Path(path).expanduser().resolve()
    with np.load(pth, allow_pickle=True) as z:
        main = _load_table(z, "main")
        if main is None:
            raise ValueError(f"NPZ missing main_cols/main_values: {pth}")
        p_tbl = _load_table(z, "p")
        q_tbl = _load_table(z, "q")
        open_tbl = _load_table(z, "open")
        meta = _decode_meta(z.get("meta_json")) if hasattr(z, "get") else {}

        # ABSOLUTE LAW: do NOT rename or infer meta keys here. We only audit and log legacy keys.
        try:
            meta = normalize_npz_meta(meta, log=lambda m: logger.warning("[Animator] %s", m))
        except Exception:
            pass

        try:
            audit_main_columns(main.cols, log=lambda m: logger.warning("[Animator] %s", m))
        except Exception:
            pass

        geometry_contract_issues: List[str] = []
        try:
            geometry_contract_issues = collect_geometry_contract_issues(
                meta,
                require_nested=True,
                require_required=True,
                context="Desktop Animator NPZ meta_json",
                log=lambda m: logger.warning("[Animator] %s", m),
            )
        except Exception as e:
            logger.warning("[Animator] Failed to audit meta_json.geometry contract: %s", e)
        if geometry_contract_issues:
            meta["_geometry_contract_issues"] = list(geometry_contract_issues)
            meta["_geometry_contract_ok"] = False
        else:
            meta["_geometry_contract_issues"] = []
            meta["_geometry_contract_ok"] = True

        t_main = main.column("время_с", default=None) if main.has("время_с") else None
        road_sidecar = load_visual_road_sidecar(
            pth,
            meta,
            time_vector=t_main,
            context="Desktop Animator NPZ",
            log=lambda m: logger.warning("[Animator] %s", m),
        )
        cache_deps = collect_visual_cache_dependencies(
            pth,
            meta=meta,
            context="Desktop Animator NPZ cache",
            log=lambda m: logger.warning("[Animator] %s", m),
        )
        meta["_visual_cache_dependencies"] = dict(cache_deps)
        meta["_visual_cache_token"] = visual_cache_dependencies_token(cache_deps)
        meta["_visual_contract"] = collect_visual_contract_status(
            main.cols,
            meta=meta,
            npz_path=pth,
            time_vector=t_main,
            road_sidecar=road_sidecar,
            context="Desktop Animator NPZ",
            log=lambda m: logger.warning("[Animator] %s", m),
        )

        # === CONTRACT CHECK ===
        # Minimum required channel for any animation is the time axis.
        # Without it, we cannot safely animate.
        if not main.has("время_с"):
            raise ValueError(
                "NPZ contract violation for Desktop Animator: missing required column 'время_с'."
            )

        # Recommended channels for full visualization (warn-only).
        recommended = [
            "перемещение_рамы_z_м",
            "скорость_vx_м_с",
            "yaw_рад",
        ]
        for c in ("ЛП", "ПП", "ЛЗ", "ПЗ"):
            recommended.extend([
                f"дорога_{c}_м",
                f"перемещение_колеса_{c}_м",
                DataBundle.frame_corner_key(c, "z"),
            ])
        missing = [k for k in recommended if not main.has(k)]
        if missing:
            logger.warning(
                "[Animator] NPZ is missing recommended df_main columns: %s (animation will degrade)",
                missing,
            )

        legacy_if_missing = {
            "скорость_vx_м_с": ["vx_м_с", "v_м_с", "speed_m_s"],
            "yaw_рад": ["рыскание_yaw_рад", "yaw_rad", "psi_рад", "курс_рад"],
            "yaw_rate_рад_с": ["рыскание_скорость_r_рад_с", "yaw_rate_r_рад_с", "psi_dot_рад_с"],
        }
        for canonical, legacy_names in legacy_if_missing.items():
            if main.has(canonical):
                continue
            present_legacy = [k for k in legacy_names if main.has(k)]
            if present_legacy:
                logger.warning(
                    "[Animator] Legacy df_main columns %s found but canonical '%s' is missing. No runtime alias mapping is performed; please migrate/re-export the NPZ.",
                    present_legacy,
                    canonical,
                )

    # Basis preference comes from meta if provided (default: ABS).
    prefer_rel0 = bool(meta.get("prefer_rel0", False))
    meta["prefer_rel0"] = prefer_rel0
    b = DataBundle(
        npz_path=pth,
        main=main,
        p=p_tbl,
        q=q_tbl,
        open=open_tbl,
        meta=meta,
        contract_issues=list(meta.get("_geometry_contract_issues") or []),
        prefer_rel0=prefer_rel0,
    )

    return b
