"""scenario_ring.py

Кольцевой генератор сценариев/тестов.

Зачем отдельный модуль:
- генератор сценариев в UI должен быть *предсказуемым* и *воспроизводимым*;
- манёвры описываются инженерными параметрами (радиус/скорость/время),
  а внутренняя реализация преобразует их в ax/ay(t);
- профиль дороги задаётся по смыслу (ISO 8608 или синус + события «яма/препятствие»)
  и затем превращается в road_csv (4 колеса).

Форматы файлов:
- road_csv: t_s, z0_m, z1_m, z2_m, z3_m (ЛП, ПП, ЛЗ, ПЗ)
- axay_csv: t_s, ax_mps2, ay_mps2

Модуль старается быть «без сюрпризов»:
- тяжёлые операции выполняются только по явному действию пользователя (кнопка/гейт в UI);
- все вычисления детерминированы при фиксированном seed.
"""

from __future__ import annotations

import json
import math
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.interpolate import CubicSpline

# re-use existing helpers for ISO-profile and csv writers
from .scenario_generator import ISO8608Spec, generate_iso8608_profile, write_axay_csv, write_road_csv

log = logging.getLogger(__name__)


def _segment_has_explicit_motion_fields(seg: Dict[str, Any]) -> bool:
    return any(k in seg for k in ("turn_direction", "speed_start_kph", "speed_end_kph"))


def _segment_turn_direction(seg: Dict[str, Any]) -> str:
    raw_turn = str(seg.get("turn_direction", "") or "").strip().upper()
    if raw_turn in {"STRAIGHT", "LEFT", "RIGHT"}:
        return raw_turn
    legacy_mode = str(seg.get("drive_mode", "STRAIGHT") or "STRAIGHT").strip().upper()
    if legacy_mode == "TURN_LEFT":
        return "LEFT"
    if legacy_mode == "TURN_RIGHT":
        return "RIGHT"
    return "STRAIGHT"


def _segment_motion_contract(seg: Dict[str, Any], v_start_kph: float) -> Dict[str, Any]:
    """Return normalized motion semantics for both canonical and legacy ring specs.

    Canonical UI intent:
    - user picks turn direction separately from speed change;
    - the first segment gets ring-level initial speed;
    - each segment owns only its end speed;
    - legacy ``drive_mode`` is preserved only as a compatibility/service field.
    """
    legacy_mode = str(seg.get("drive_mode", "STRAIGHT") or "STRAIGHT").strip().upper()
    turn_direction = _segment_turn_direction(seg)
    explicit_motion = _segment_has_explicit_motion_fields(seg)

    if explicit_motion:
        try:
            speed_start_kph = float(seg.get("speed_start_kph", v_start_kph) or v_start_kph)
        except Exception:
            speed_start_kph = float(v_start_kph)
        if "speed_end_kph" in seg:
            try:
                speed_end_kph = float(seg.get("speed_end_kph", speed_start_kph) or speed_start_kph)
            except Exception:
                speed_end_kph = float(speed_start_kph)
        elif "v_end_kph" in seg:
            try:
                speed_end_kph = float(seg.get("v_end_kph", speed_start_kph) or speed_start_kph)
            except Exception:
                speed_end_kph = float(speed_start_kph)
        elif "speed_kph" in seg:
            try:
                speed_end_kph = float(seg.get("speed_kph", speed_start_kph) or speed_start_kph)
            except Exception:
                speed_end_kph = float(speed_start_kph)
        else:
            speed_end_kph = float(speed_start_kph)
    else:
        if legacy_mode in ("ACCEL", "BRAKE"):
            speed_start_kph = float(v_start_kph)
            try:
                speed_end_kph = float(seg.get("v_end_kph", v_start_kph) or v_start_kph)
            except Exception:
                speed_end_kph = float(v_start_kph)
        else:
            try:
                speed_end_kph = float(seg.get("speed_kph", v_start_kph) or v_start_kph)
            except Exception:
                speed_end_kph = float(v_start_kph)
            speed_start_kph = float(speed_end_kph)

    speed_start_kph = max(0.0, float(speed_start_kph))
    speed_end_kph = max(0.0, float(speed_end_kph))

    if turn_direction == "STRAIGHT":
        if abs(speed_end_kph - speed_start_kph) <= 1e-9:
            derived_legacy_mode = "STRAIGHT"
        else:
            derived_legacy_mode = "ACCEL" if speed_end_kph > speed_start_kph else "BRAKE"
    else:
        derived_legacy_mode = "TURN_LEFT" if turn_direction == "LEFT" else "TURN_RIGHT"

    try:
        turn_radius_m = float(seg.get("turn_radius_m", 0.0) or 0.0)
    except Exception:
        turn_radius_m = 0.0

    return {
        "explicit_motion": bool(explicit_motion),
        "turn_direction": turn_direction,
        "speed_start_kph": speed_start_kph,
        "speed_end_kph": speed_end_kph,
        "vary_speed": bool(abs(speed_end_kph - speed_start_kph) > 1e-9),
        "turn_radius_m": max(0.0, turn_radius_m),
        "legacy_mode": derived_legacy_mode if explicit_motion else legacy_mode,
        "display_mode": derived_legacy_mode,
    }


def _resolve_track_m(spec: Dict[str, Any]) -> float:
    try:
        track_m = float(spec.get("track_m", 1.0) or 1.0)
    except Exception:
        track_m = 1.0
    return float(max(1e-6, track_m))


def _road_state_contract_enabled(spec: Dict[str, Any]) -> bool:
    keys = {
        "center_height_start_mm",
        "center_height_end_mm",
        "cross_slope_start_pct",
        "cross_slope_end_pct",
    }
    for seg in list(spec.get("segments", []) or []):
        road = dict(seg.get("road", {}) or {})
        if any(k in road for k in keys):
            return True
    return False


def _segment_road_state_mm(
    spec: Dict[str, Any],
    segments: List[Dict[str, Any]],
    idx: int,
    prev_end_center_mm: float,
    prev_end_cross_pct: float,
    first_start_center_mm: float,
    first_start_cross_pct: float,
) -> Dict[str, float]:
    road = dict((segments[idx] or {}).get("road", {}) or {})
    if idx == 0:
        try:
            start_center_mm = float(road.get("center_height_start_mm", 0.0) or 0.0)
        except Exception:
            start_center_mm = 0.0
        try:
            start_cross_pct = float(road.get("cross_slope_start_pct", 0.0) or 0.0)
        except Exception:
            start_cross_pct = 0.0
    else:
        start_center_mm = float(prev_end_center_mm)
        start_cross_pct = float(prev_end_cross_pct)

    is_last = idx >= len(segments) - 1
    end_center_default = first_start_center_mm if is_last else start_center_mm
    end_cross_default = first_start_cross_pct if is_last else start_cross_pct
    try:
        end_center_mm = float(road.get("center_height_end_mm", end_center_default) or end_center_default)
    except Exception:
        end_center_mm = float(end_center_default)
    try:
        end_cross_pct = float(road.get("cross_slope_end_pct", end_cross_default) or end_cross_default)
    except Exception:
        end_cross_pct = float(end_cross_default)

    if is_last:
        end_center_mm = float(first_start_center_mm)
        end_cross_pct = float(first_start_cross_pct)

    return {
        "start_center_mm": float(start_center_mm),
        "end_center_mm": float(end_center_mm),
        "start_cross_pct": float(start_cross_pct),
        "end_cross_pct": float(end_cross_pct),
    }


def _apply_segment_boundary_targets(
    x_local: np.ndarray,
    left: np.ndarray,
    right: np.ndarray,
    *,
    track_m: float,
    start_center_mm: float,
    end_center_mm: float,
    start_cross_pct: float,
    end_cross_pct: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Tilt/shift segment so its boundary heights match explicit road-state targets."""
    if x_local.size == 0:
        return np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if x_local.size == 1:
        alpha = np.array([0.0], dtype=float)
    else:
        length_m = float(max(x_local[-1] - x_local[0], 1e-9))
        alpha = (np.asarray(x_local, dtype=float) - float(x_local[0])) / length_m

    center_start_m = float(start_center_mm) / 1000.0
    center_end_m = float(end_center_mm) / 1000.0
    cross_start = float(start_cross_pct) / 100.0
    cross_end = float(end_cross_pct) / 100.0

    start_left_target = center_start_m - 0.5 * float(track_m) * cross_start
    end_left_target = center_end_m - 0.5 * float(track_m) * cross_end
    start_right_target = center_start_m + 0.5 * float(track_m) * cross_start
    end_right_target = center_end_m + 0.5 * float(track_m) * cross_end

    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    corr_left = (start_left_target - float(left[0])) + alpha * ((end_left_target - float(left[-1])) - (start_left_target - float(left[0])))
    corr_right = (start_right_target - float(right[0])) + alpha * ((end_right_target - float(right[-1])) - (start_right_target - float(right[0])))
    return left + corr_left, right + corr_right


def _segment_length_canonical_m(v_start_kph: float, seg: Dict[str, Any], *, fallback_dt_s: float = 0.01, dx_m: float = 0.02) -> float:
    """Canonical segment length used by preview/summary/export.

    Priority:
    1) explicit length_m;
    2) derive from duration and canonical speed fields exactly as ring generator does.

    No aliases are accepted. Returned value is always >= dx_m.
    """
    try:
        explicit = float(seg.get("length_m", 0.0) or 0.0)
    except Exception:
        explicit = 0.0
    if explicit > 0.0:
        return float(explicit)

    try:
        dur_s = float(seg.get("duration_s", 0.0) or 0.0)
    except Exception:
        dur_s = 0.0
    dur_s = max(float(fallback_dt_s), dur_s)
    dx_m = max(1e-6, float(dx_m))

    motion = _segment_motion_contract(seg, v_start_kph)
    v0 = max(0.0, float(motion["speed_start_kph"]) / 3.6)
    v1 = max(0.0, float(motion["speed_end_kph"]) / 3.6)
    if motion["vary_speed"]:
        return float(max(dx_m, 0.5 * (v0 + v1) * dur_s))
    return float(max(dx_m, v1 * dur_s))


def _resolve_initial_speed_kph(spec: Dict[str, Any]) -> float:
    """Return canonical initial speed for ring workflow.

    Priority:
    1) explicit positive spec.v0_kph;
    2) speed_kph of the first constant-speed segment.

    This prevents the common UX failure where a ring spec keeps ``v0_kph=0`` while
    the first authored segment already declares ``speed_kph=40`` and the rest of the
    pipeline then exports/visualises a fake zero initial speed.
    """
    try:
        v0 = float(spec.get("v0_kph", 0.0) or 0.0)
    except Exception:
        v0 = 0.0
    if np.isfinite(v0) and v0 > 0.0:
        return float(v0)

    segs = list(spec.get("segments", []) or [])
    if segs:
        s0 = dict(segs[0] or {})
        if "speed_start_kph" in s0:
            try:
                v1 = float(s0.get("speed_start_kph", 0.0) or 0.0)
            except Exception:
                v1 = 0.0
            if np.isfinite(v1) and v1 > 0.0:
                log.warning(
                    "scenario_ring: spec.v0_kph missing/zero; using first segment speed_start_kph=%.3f as canonical initial ring speed",
                    v1,
                )
                return float(v1)
        motion0 = _segment_motion_contract(s0, 0.0)
        v1 = float(motion0["speed_start_kph"] if motion0["explicit_motion"] else motion0["speed_end_kph"])
        if np.isfinite(v1) and v1 > 0.0:
            log.warning(
                "scenario_ring: spec.v0_kph missing/zero; using first segment authored speed=%.3f as canonical initial ring speed",
                v1,
            )
            return float(v1)
    return 0.0


def _resolve_closure_policy(spec: Dict[str, Any]) -> str:
    """Return explicit ring closure policy.

    Supported canonical policies:
    - ``closed_c1_periodic``: the generated ring is smoothly closed in value and
      first derivative across the seam; export/preview use a periodic spline.
    - ``strict_exact``: keep the authored profile exactly as-is and expose the seam.
    """
    raw = str(spec.get("closure_policy", "closed_c1_periodic") or "closed_c1_periodic").strip().lower()
    if raw not in {"closed_c1_periodic", "strict_exact"}:
        raise ValueError(
            f"Unsupported closure_policy={raw!r}. Allowed: 'closed_c1_periodic', 'strict_exact'."
        )
    return raw


def _close_track_c1_periodic(x: np.ndarray, z: np.ndarray) -> Tuple[np.ndarray, Dict[str, float]]:
    """Smoothly close an authored track to a periodic C1 ring.

    Important: the correction is applied *only in a local seam window near the end of
    the lap*. This keeps the authored middle of the ring intact and avoids the old
    whole-lap hidden ramp that badly distorted local amplitudes in unrelated segments.

    We fit a quintic ``c(u)`` on the last seam window so that for ``z_closed = z - c``:
      - z_closed(0) == z_closed(L)
      - z_closed'(0) == z_closed'(L)
      - c and its first two derivatives are zero at the inner boundary of the seam
        window, so the correction enters/exits smoothly.
    """
    x = np.asarray(x, dtype=float).reshape(-1)
    z = np.asarray(z, dtype=float).reshape(-1)
    if x.size != z.size or x.size < 6:
        return z.copy(), {
            "raw_jump_m": 0.0,
            "raw_slope_jump": 0.0,
            "correction_max_m": 0.0,
            "correction_rms_m": 0.0,
            "post_jump_m": 0.0,
            "blend_window_m": 0.0,
        }

    L = float(x[-1] - x[0])
    if not np.isfinite(L) or L <= 0.0:
        return z.copy(), {
            "raw_jump_m": 0.0,
            "raw_slope_jump": 0.0,
            "correction_max_m": 0.0,
            "correction_rms_m": 0.0,
            "post_jump_m": 0.0,
            "blend_window_m": 0.0,
        }

    s = np.asarray(x - x[0], dtype=float)
    d = float(z[-1] - z[0])
    # Use a higher-order edge estimate for the seam slope jump.
    #
    # Why this matters:
    # - for a perfectly periodic authored sine with a non-zero phase, one-sided
    #   ``edge_order=1`` finite differences at the first/last sample can report a
    #   fake slope mismatch even when the sampled signal already closes exactly;
    # - that fake mismatch then injects an unnecessary local seam correction,
    #   which slightly inflates the apparent amplitude near the end of the lap.
    #
    # ``edge_order=2`` is stable here because we already require at least 6 points
    # above; if that assumption ever changes, we gracefully fall back.
    try:
        dzdx = np.gradient(z, x, edge_order=2)
    except Exception:
        dzdx = np.gradient(z, x, edge_order=1)
    m = float(dzdx[-1] - dzdx[0])

    # Use a local seam blend instead of a whole-lap ramp.
    w = float(min(max(8.0, 0.05 * L), 0.45 * L))
    s0 = float(L - w)
    corr = np.zeros_like(z, dtype=float)
    mask = s >= s0 - 1e-12
    slope_tol = max(1e-9, 1e-6 / max(float(L), 1.0))
    if abs(d) <= 1e-12 and abs(m) <= slope_tol:
        zc = np.asarray(z, dtype=float).copy()
        if zc.size:
            zc[-1] = float(zc[0])
        return zc, {
            "raw_jump_m": d,
            "raw_slope_jump": m,
            "correction_max_m": 0.0,
            "correction_rms_m": 0.0,
            "post_jump_m": float(zc[-1] - zc[0]) if zc.size else 0.0,
            "blend_window_m": 0.0,
        }

    if np.count_nonzero(mask) >= 3:
        u = np.asarray((s[mask] - s0) / max(w, 1e-9), dtype=float)
        # Quintic with a0=a1=a2=0 and constraints at u=1:
        #   c(1)=d, dc/ds(1)=m, d2c/ds2(1)=0
        # In normalized coordinates: dc/du(1)=m*w.
        A = np.array([[1.0, 1.0, 1.0], [3.0, 4.0, 5.0], [6.0, 12.0, 20.0]], dtype=float)
        b = np.array([d, m * w, 0.0], dtype=float)
        a3, a4, a5 = np.linalg.solve(A, b)
        corr[mask] = a3 * u**3 + a4 * u**4 + a5 * u**5

    zc = np.asarray(z - corr, dtype=float)
    if zc.size:
        zc[-1] = float(zc[0])
    return zc, {
        "raw_jump_m": d,
        "raw_slope_jump": m,
        "correction_max_m": float(np.nanmax(np.abs(corr))) if corr.size else 0.0,
        "correction_rms_m": float(np.sqrt(np.nanmean(np.square(corr)))) if corr.size else 0.0,
        "post_jump_m": float(zc[-1] - zc[0]) if zc.size else 0.0,
        "blend_window_m": w,
    }



def _smoothstep01(x: np.ndarray) -> np.ndarray:
    """Плавная S‑кривая (0..1) с нулевым наклоном на концах."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _s_curve_profile(n: int) -> np.ndarray:
    """Готовый профиль 0..1 длиной n."""
    if n <= 1:
        return np.array([1.0], dtype=float)
    x = np.linspace(0.0, 1.0, n)
    return _smoothstep01(x)


def _pick_randomized(
    rng: np.random.Generator,
    base: float,
    *,
    enabled: bool,
    p: float,
    lo: float,
    hi: float,
) -> float:
    """Выбор параметра с вероятностью p (иначе base)."""
    if not enabled:
        return float(base)
    p = float(np.clip(p, 0.0, 1.0))
    if rng.random() > p:
        return float(base)
    lo, hi = float(lo), float(hi)
    if hi < lo:
        lo, hi = hi, lo
    return float(rng.uniform(lo, hi))


def _phase_random_cfg_rad(road: Dict[str, Any], *, side: str) -> Dict[str, float | bool]:
    side = str(side).upper()
    if side not in {"L", "R"}:
        raise ValueError(f"Unsupported phase-random side={side!r}")
    return {
        "enabled": bool(road.get(f"rand_p{side}", False)),
        "p": float(road.get(f"rand_p{side}_p", 0.5)),
        "lo": float(road.get(f"rand_p{side}_lo_deg", 0.0)) * np.pi / 180.0,
        "hi": float(road.get(f"rand_p{side}_hi_deg", 0.0)) * np.pi / 180.0,
    }


def _phase_random_cfg_is_symmetric(cfg_l: Dict[str, float | bool], cfg_r: Dict[str, float | bool], *, tol: float = 1e-12) -> bool:
    return (
        bool(cfg_l.get("enabled", False))
        and bool(cfg_r.get("enabled", False))
        and abs(float(cfg_l.get("p", 0.0)) - float(cfg_r.get("p", 0.0))) <= tol
        and abs(float(cfg_l.get("lo", 0.0)) - float(cfg_r.get("lo", 0.0))) <= tol
        and abs(float(cfg_l.get("hi", 0.0)) - float(cfg_r.get("hi", 0.0))) <= tol
    )


def _resolve_sine_phase_pair_rad(
    rng: np.random.Generator,
    road: Dict[str, Any],
    *,
    base_left_rad: float,
    base_right_rad: float,
) -> tuple[float, float]:
    """Resolve left/right sine phases without silently destroying the requested delta.

    Why this exists:
    - the authored ring spec often expresses a meaningful explicit phase relation
      between left/right tracks (for example 0° / 180°);
    - older releases randomized left/right phases independently when both
      ``rand_pL`` and ``rand_pR`` were enabled, which could replace an explicit
      180° anti-phase pair by an arbitrary mismatched delta from the RNG;
    - for symmetric left/right phase-random settings the intuitive meaning is a
      *common* phase shift of the whole road pattern while preserving the
      authored inter-track delta.

    Canonical rule implemented here:
    - if both sides request symmetric phase randomization (same probability and
      same range), preserve ``base_right - base_left`` exactly and randomize only
      the common phase origin;
    - otherwise keep the historical independent-side semantics.
    """
    cfg_l = _phase_random_cfg_rad(road, side="L")
    cfg_r = _phase_random_cfg_rad(road, side="R")
    phase_mode = str(road.get("rand_phase_mode", "") or "").strip().lower()

    preserve_delta = False
    if phase_mode in {"common", "linked", "preserve_delta"}:
        preserve_delta = bool(cfg_l.get("enabled", False) or cfg_r.get("enabled", False))
    elif not phase_mode and _phase_random_cfg_is_symmetric(cfg_l, cfg_r):
        preserve_delta = True

    if preserve_delta:
        enabled_common = bool(cfg_l.get("enabled", False) or cfg_r.get("enabled", False))
        ref_cfg = cfg_l if bool(cfg_l.get("enabled", False)) else cfg_r
        delta = float(base_right_rad) - float(base_left_rad)
        phase_left = _pick_randomized(
            rng,
            float(base_left_rad),
            enabled=enabled_common,
            p=float(ref_cfg.get("p", 0.5)),
            lo=float(ref_cfg.get("lo", float(base_left_rad))),
            hi=float(ref_cfg.get("hi", float(base_left_rad))),
        )
        return float(phase_left), float(phase_left + delta)

    phase_left = _pick_randomized(
        rng,
        float(base_left_rad),
        enabled=bool(cfg_l.get("enabled", False)),
        p=float(cfg_l.get("p", 0.5)),
        lo=float(cfg_l.get("lo", float(base_left_rad))),
        hi=float(cfg_l.get("hi", float(base_left_rad))),
    )
    phase_right = _pick_randomized(
        rng,
        float(base_right_rad),
        enabled=bool(cfg_r.get("enabled", False)),
        p=float(cfg_r.get("p", 0.5)),
        lo=float(cfg_r.get("lo", float(base_right_rad))),
        hi=float(cfg_r.get("hi", float(base_right_rad))),
    )
    return float(phase_left), float(phase_right)


def _sine_track(
    x: np.ndarray,
    *,
    amplitude_m: float,
    wavelength_m: float,
    phase_rad: float,
) -> np.ndarray:
    wavelength_m = float(max(1e-6, wavelength_m))
    return float(amplitude_m) * np.sin(2.0 * np.pi * x / wavelength_m + float(phase_rad))


def _apply_event_shape(
    x: np.ndarray,
    *,
    x0_m: float,
    length_m: float,
    depth_m: float,
    ramp_m: Optional[float] = None,
) -> np.ndarray:
    """Плавный «ступенчатый» профиль: яма/препятствие без острых углов.

    shape(x) ∈ [0..1], далее умножается на depth_m (может быть отрицательной).

    Используем smoothstep на входе/выходе => C1‑гладкость на границах.
    """
    x0_m = float(x0_m)
    length_m = float(max(0.0, length_m))
    if length_m <= 0.0:
        return np.zeros_like(x)

    if ramp_m is None:
        ramp_m = min(0.25 * length_m, 0.2)  # разумная «фаска» по умолчанию
    ramp_m = float(max(0.0, min(ramp_m, 0.5 * length_m)))

    x1 = x0_m
    x2 = x0_m + ramp_m
    x3 = x0_m + length_m - ramp_m
    x4 = x0_m + length_m

    y = np.zeros_like(x, dtype=float)

    # Вход
    if ramp_m > 0:
        mask_in = (x >= x1) & (x < x2)
        s = (x[mask_in] - x1) / ramp_m
        y[mask_in] = _smoothstep01(s)
    # Плато
    mask_mid = (x >= x2) & (x <= x3)
    y[mask_mid] = 1.0
    # Выход
    if ramp_m > 0:
        mask_out = (x > x3) & (x <= x4)
        s = (x4 - x[mask_out]) / ramp_m
        y[mask_out] = _smoothstep01(s)

    return float(depth_m) * y


def _ensure_increasing_x(x: np.ndarray) -> np.ndarray:
    if not np.all(np.diff(x) > 0):
        # Это должно быть крайне редким, но безопаснее восстановить.
        x = np.maximum.accumulate(x)
        eps = 1e-9
        for i in range(1, len(x)):
            if x[i] <= x[i - 1]:
                x[i] = x[i - 1] + eps
    return x


def _circular_distance_track(t: np.ndarray, v_mps: np.ndarray) -> np.ndarray:
    """Интегрируем скорость => пройденная дистанция (м) для каждой точки t."""
    t = np.asarray(t, dtype=float)
    v_mps = np.asarray(v_mps, dtype=float)
    if len(t) != len(v_mps):
        raise ValueError("t и v_mps должны быть одинаковой длины")
    if len(t) == 0:
        return np.array([], dtype=float)
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError("t должен быть строго возрастающим")
    s = np.zeros_like(t)
    s[1:] = np.cumsum(0.5 * (v_mps[:-1] + v_mps[1:]) * dt)
    return s


def _build_segment_time_series(seg: Dict[str, Any], dt_s: float, v_start_mps: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Build time-series for one segment.

    ABSOLUTE LAW (see 00_READ_FIRST__ABSOLUTE_LAW.md):
      * No invented/duplicated parameters.
      * No alias keys (e.g. speed_kmh). Only canonical keys are accepted.
      * Missing/invalid inputs MUST NOT crash the app; we warn and fall back to the
        closest physically-safe behavior.

    Canonical keys for segment dict:
      - drive_mode: STRAIGHT | TURN_LEFT | TURN_RIGHT | ACCEL | BRAKE
      - duration_s: float >= 0
      - speed_kph: for STRAIGHT / TURN_*
      - v_end_kph: for ACCEL / BRAKE
      - turn_radius_m: for TURN_*

    Notes:
      * If speed_kph / v_end_kph is missing, we keep v_start (and log warning).
      * Lateral acceleration ay is produced only for TURN_*.
    """

    motion = _segment_motion_contract(seg, float(v_start_mps) * 3.6)
    mode = str(motion["legacy_mode"]).upper()
    dur_s = float(seg.get("duration_s", 0.0))
    dur_s = max(0.0, dur_s)

    if dur_s <= 0.0:
        t = np.array([0.0, dt_s])
        v_static = max(0.0, float(motion["speed_start_kph"]) / 3.6)
        v = np.array([v_static, v_static])
        ay = np.zeros_like(t)
        return t, v, ay, float(v[-1])

    n = int(math.floor(dur_s / dt_s)) + 1
    t = np.linspace(0.0, dur_s, n)

    v0 = max(0.0, float(motion["speed_start_kph"]) / 3.6)
    v1 = max(0.0, float(motion["speed_end_kph"]) / 3.6)
    if motion["vary_speed"]:
        v = np.linspace(v0, v1, len(t))
    else:
        v = np.full_like(t, v1 if mode in ("STRAIGHT", "CRUISE", "TURN_LEFT", "TURN_RIGHT") else v0)

    turn_direction = str(motion["turn_direction"]).upper()
    radius_m = float(motion["turn_radius_m"])
    if turn_direction in ("LEFT", "RIGHT"):
        if np.isfinite(radius_m) and radius_m > 0.0:
            ay = (v * v) / radius_m
            if turn_direction == "RIGHT":
                ay = -ay
        else:
            log.warning("scenario_ring: turn segment missing/invalid turn_radius_m; ay will be 0")
            ay = np.zeros_like(t)
    else:
        ay = np.zeros_like(t)
    return t, v, ay, float(v[-1])


def generate_ring_drive_profile(
    spec: Dict[str, Any],
    *,
    dt_s: float,
    n_laps: int,
) -> Dict[str, np.ndarray]:
    """Создаёт профиль движения кольца: t, v, ax, ay и distance_m."""
    dt_s = float(max(1e-6, dt_s))
    n_laps = int(max(1, n_laps))

    segments = list(spec.get("segments", []))
    if not segments:
        raise ValueError("spec.segments пуст")

    v0_kph = _resolve_initial_speed_kph(spec)
    if not ("v0_kph" in spec and float(spec.get("v0_kph", 0.0) or 0.0) > 0.0):
        log.warning("scenario_ring: using effective initial speed v0_kph=%.3f for drive profile", v0_kph)
    v_cur = float(max(0.0, v0_kph / 3.6))

    t_all: List[np.ndarray] = []
    v_all: List[np.ndarray] = []
    ay_all: List[np.ndarray] = []

    t_offset = 0.0
    for _lap in range(n_laps):
        for seg in segments:
            t_seg, v_seg, ay_seg, v_end = _build_segment_time_series(seg, dt_s=dt_s, v_start_mps=v_cur)
            if t_all:
                t_seg = t_seg[1:]
                v_seg = v_seg[1:]
                ay_seg = ay_seg[1:]
            t_all.append(t_seg + t_offset)
            v_all.append(v_seg)
            ay_all.append(ay_seg)
            t_offset = float((t_seg + t_offset)[-1])
            v_cur = v_end

    t = np.concatenate(t_all)
    v = np.concatenate(v_all)
    ay = np.concatenate(ay_all)
    ax = np.gradient(v, t, edge_order=1)
    dist = _circular_distance_track(t, v)
    return {"t_s": t, "v_mps": v, "ax_mps2": ax, "ay_mps2": ay, "distance_m": dist}


def generate_ring_tracks(
    spec: Dict[str, Any],
    *,
    dx_m: float = 0.02,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Генерация кольцевого профиля дороги (левая/правая колея) в координате x."""
    dx_m = float(max(1e-4, dx_m))
    rng = np.random.default_rng(seed)

    segments = list(spec.get("segments", []))
    if not segments:
        raise ValueError("spec.segments пуст")

    x_parts: List[np.ndarray] = []
    zL_parts: List[np.ndarray] = []
    zR_parts: List[np.ndarray] = []

    x_offset = 0.0
    prev_end_L = 0.0
    prev_end_R = 0.0
    track_m = _resolve_track_m(spec)
    use_road_state_contract = _road_state_contract_enabled(spec)
    first_start_center_mm = 0.0
    first_start_cross_pct = 0.0
    prev_end_center_mm = 0.0
    prev_end_cross_pct = 0.0

    # Track length estimation must be consistent with the drive profile generator.
    # If a segment length is not specified explicitly, we estimate it from duration and the
    # current speed state (v_cur_kph), using average speed for accel/brake segments.
    v_cur_kph = _resolve_initial_speed_kph(spec)
    if not ("v0_kph" in spec and float(spec.get("v0_kph", 0.0) or 0.0) > 0.0):
        log.warning("scenario_ring: using effective initial speed v0_kph=%.3f for track geometry", v_cur_kph)

    for i, seg in enumerate(segments):
        motion = _segment_motion_contract(seg, v_cur_kph)
        seg_type = str(motion["legacy_mode"]).upper()
        seg_len_m = float(seg.get("length_m", 0.0))
        v_next_kph = float(motion["speed_end_kph"])
        if seg_len_m <= 0.0:
            dur_s = float(seg.get("duration_s", 0.0))
            # Keep geometry stable even if duration is missing
            dur_s = max(dur_s, float(spec.get("dt_s", 0.01)))

            v_avg_kph = 0.5 * (float(motion["speed_start_kph"]) + float(motion["speed_end_kph"]))
            if not np.isfinite(v_avg_kph) or v_avg_kph <= 0.0:
                v_avg_kph = max(float(v_cur_kph), float(motion["speed_end_kph"]))
            v = max(0.1, v_avg_kph / 3.6)
            seg_len_m = max(dx_m, dur_s * v)
        else:
            v_next_kph = float(motion["speed_end_kph"])

        n = int(math.floor(seg_len_m / dx_m)) + 1
        x_local = np.linspace(0.0, seg_len_m, n)

        road = dict(seg.get("road", {}))
        road_mode = str(road.get("mode", "ISO8608")).upper()
        if "mode" not in road:
            log.warning("scenario_ring: segment road missing mode; defaulting ISO8608")

        if road_mode in ("ISO", "ISO8608", "ISO_8608"):
            iso_class = str(road.get("iso_class", "C")).upper()
            if "iso_class" not in road:
                log.warning("scenario_ring: ISO8608 road missing iso_class; defaulting 'C'")
            waviness_w = float(road.get("waviness_w", 2.0))
            if "waviness_w" not in road:
                log.warning("scenario_ring: ISO8608 road missing waviness_w; default=2.0")
            gd_pick = str(road.get("gd_pick", "mid"))
            if "gd_pick" not in road:
                log.warning("scenario_ring: ISO8608 road missing gd_pick; default='mid'")
            gd_scale = float(road.get("gd_n0_scale", 1.0))
            if "gd_n0_scale" not in road:
                log.warning("scenario_ring: ISO8608 road missing gd_n0_scale; default=1.0")
            coh = float(road.get("left_right_coherence", 0.5))
            if "left_right_coherence" not in road:
                log.warning("scenario_ring: ISO8608 road missing left_right_coherence; default=0.5")
            coh = float(np.clip(coh, 0.0, 1.0))

            spec_iso = ISO8608Spec(
                road_class=iso_class,
                waviness_w=waviness_w,
                gd_pick=gd_pick,
                gd_n0_scale=gd_scale,
            )
            seg_seed = road.get("seed", None)
            if seg_seed is None:
                seg_seed = int(rng.integers(0, 2**31 - 1))

            x_local, left, _metaL = generate_iso8608_profile(
                length_m=seg_len_m,
                dx_m=dx_m,
                spec=spec_iso,
                seed=int(seg_seed),
                enforce_z0_zero=True,
                enforce_mean_zero=True,
            )
            _x2, right, _metaR = generate_iso8608_profile(
                length_m=seg_len_m,
                dx_m=dx_m,
                spec=spec_iso,
                seed=int(seg_seed) + 17,
                enforce_z0_zero=True,
                enforce_mean_zero=True,
            )
            right = coh * left + math.sqrt(max(0.0, 1.0 - coh * coh)) * right

        elif road_mode in ("SIN", "SINE", "SINUS", "SINUSOID"):
            # Canonical keys only (no aliases): aL_mm, aR_mm, lambdaL_m, lambdaR_m, phaseL_deg, phaseR_deg
            aL = float(road.get("aL_mm", 5.0)) / 1000.0
            if "aL_mm" not in road:
                log.warning("scenario_ring: SINE road missing aL_mm; default=5mm")
            lL = float(road.get("lambdaL_m", 2.0))
            if "lambdaL_m" not in road:
                log.warning("scenario_ring: SINE road missing lambdaL_m; default=2m")
            pL = float(road.get("phaseL_deg", 0.0)) * np.pi / 180.0
            if "phaseL_deg" not in road:
                log.warning("scenario_ring: SINE road missing phaseL_deg; default=0")

            aR = float(road.get("aR_mm", 5.0)) / 1000.0
            if "aR_mm" not in road:
                log.warning("scenario_ring: SINE road missing aR_mm; default=5mm")
            lR = float(road.get("lambdaR_m", 2.0))
            if "lambdaR_m" not in road:
                log.warning("scenario_ring: SINE road missing lambdaR_m; default=2m")
            pR = float(road.get("phaseR_deg", 0.0)) * np.pi / 180.0
            if "phaseR_deg" not in road:
                log.warning("scenario_ring: SINE road missing phaseR_deg; default=0")


            aL = _pick_randomized(
                rng,
                aL,
                enabled=bool(road.get("rand_aL", False)),
                p=float(road.get("rand_aL_p", 0.5)),
                lo=float(road.get("rand_aL_lo_mm", aL * 1000.0)) / 1000.0,
                hi=float(road.get("rand_aL_hi_mm", aL * 1000.0)) / 1000.0,
            )
            aR = _pick_randomized(
                rng,
                aR,
                enabled=bool(road.get("rand_aR", False)),
                p=float(road.get("rand_aR_p", 0.5)),
                lo=float(road.get("rand_aR_lo_mm", aR * 1000.0)) / 1000.0,
                hi=float(road.get("rand_aR_hi_mm", aR * 1000.0)) / 1000.0,
            )
            lL = _pick_randomized(
                rng,
                lL,
                enabled=bool(road.get("rand_lL", False)),
                p=float(road.get("rand_lL_p", 0.5)),
                lo=float(road.get("rand_lL_lo_m", lL)),
                hi=float(road.get("rand_lL_hi_m", lL)),
            )
            lR = _pick_randomized(
                rng,
                lR,
                enabled=bool(road.get("rand_lR", False)),
                p=float(road.get("rand_lR_p", 0.5)),
                lo=float(road.get("rand_lR_lo_m", lR)),
                hi=float(road.get("rand_lR_hi_m", lR)),
            )
            pL, pR = _resolve_sine_phase_pair_rad(
                rng,
                road,
                base_left_rad=pL,
                base_right_rad=pR,
            )

            left = _sine_track(x_local, amplitude_m=aL, wavelength_m=lL, phase_rad=pL)
            right = _sine_track(x_local, amplitude_m=aR, wavelength_m=lR, phase_rad=pR)
            # Keep deterministic SINE exactly as requested.
            # Silent per-segment recentering changes the absolute phase/offset and can
            # visibly distort preview/export for non-integer wavelengths.

        else:
            left = np.zeros_like(x_local)
            right = np.zeros_like(x_local)
        for ev in list(seg.get("events", [])):
            try:
                side = str(ev.get("side", "both")).lower()
                x0 = float(ev.get("start_m", 0.0))
                L = float(ev.get("length_m", 0.0))

                # ABSOLUTE LAW: canonical key is depth_mm (millimeters).
                if "depth_mm" in ev:
                    depth_m = float(ev["depth_mm"]) / 1000.0
                else:
                    if "depth_m" in ev:
                        log.warning("scenario_ring: event has legacy depth_m; expected depth_mm. depth_m ignored.")
                    depth_m = 0.0

                ramp_m = ev.get("ramp_m", None)
                if ramp_m is not None:
                    ramp_m = float(ramp_m)

                shape = _apply_event_shape(x_local, x0_m=x0, length_m=L, depth_m=depth_m, ramp_m=ramp_m)

                if side in ("left", "l", "левая", "л"):
                    left = left + shape
                elif side in ("right", "r", "правая", "п"):
                    right = right + shape
                else:
                    left = left + shape
                    right = right + shape
            except Exception:
                continue

        if use_road_state_contract:
            road_state = _segment_road_state_mm(
                spec,
                segments,
                i,
                prev_end_center_mm=prev_end_center_mm,
                prev_end_cross_pct=prev_end_cross_pct,
                first_start_center_mm=first_start_center_mm,
                first_start_cross_pct=first_start_cross_pct,
            )
            if i == 0:
                first_start_center_mm = float(road_state["start_center_mm"])
                first_start_cross_pct = float(road_state["start_cross_pct"])
                road_state = _segment_road_state_mm(
                    spec,
                    segments,
                    i,
                    prev_end_center_mm=prev_end_center_mm,
                    prev_end_cross_pct=prev_end_cross_pct,
                    first_start_center_mm=first_start_center_mm,
                    first_start_cross_pct=first_start_cross_pct,
                )
            left, right = _apply_segment_boundary_targets(
                x_local,
                left,
                right,
                track_m=track_m,
                start_center_mm=float(road_state["start_center_mm"]),
                end_center_mm=float(road_state["end_center_mm"]),
                start_cross_pct=float(road_state["start_cross_pct"]),
                end_cross_pct=float(road_state["end_cross_pct"]),
            )
            prev_end_center_mm = float(road_state["end_center_mm"])
            prev_end_cross_pct = float(road_state["end_cross_pct"])
        elif i == 0:
            # Preserve the requested absolute phase/offset of the very first segment.
            # Forcing z(0)=0 here distorts SINE amplitude whenever phase != 0 and was the
            # source of the apparent "A×2" bug in the ring preview/generator.
            dL = 0.0
            dR = 0.0
        else:
            dL = prev_end_L - float(left[0])
            dR = prev_end_R - float(right[0])
        if not use_road_state_contract:
            left = left + dL
            right = right + dR

        x_global = x_local + x_offset
        if i > 0:
            x_global = x_global[1:]
            left = left[1:]
            right = right[1:]

        x_parts.append(x_global)
        zL_parts.append(left)
        zR_parts.append(right)
        x_offset = float(x_global[-1])
        v_cur_kph = float(v_next_kph)
        prev_end_L = float(left[-1])
        prev_end_R = float(right[-1])

    x = np.concatenate(x_parts)
    zL = np.concatenate(zL_parts)
    zR = np.concatenate(zR_parts)

    # Preserve the authored raw profile samples for diagnostics/preview.
    #
    # This is important for two reasons:
    # 1) raw ``zL_m`` / ``zR_m`` are the most truthful place to inspect whether a
    #    deterministic SINE kept the requested amplitude without any hidden global
    #    bending;
    # 2) the ring may still choose to build a closed periodic spline for export, but
    #    that must not overwrite the raw authored samples and create the illusion that
    #    the seam never existed in the source profile.
    zL_raw = np.asarray(zL, dtype=float).copy()
    zR_raw = np.asarray(zR, dtype=float).copy()

    # Do not silently "close" the ring by bending the whole road with a linear ramp.
    # That changes the requested deterministic profile (phase/amplitude/depth) and was
    # the root cause of false metre-scale drifts and inflated SINE amplitudes.
    # We keep the generated road exactly as specified and only warn if the seam does
    # not close; the caller may decide whether that is acceptable for multi-lap tests.

    L_total = float(x[-1] - x[0])
    if L_total <= 0:
        raise ValueError("Кольцо имеет нулевую длину")
    closure_policy = _resolve_closure_policy(spec)
    raw_jump_L = float(zL_raw[-1] - zL_raw[0])
    raw_jump_R = float(zR_raw[-1] - zR_raw[0])
    seam_thr = 0.002  # 2 mm

    close_info_L = {
        "raw_jump_m": raw_jump_L,
        "raw_slope_jump": 0.0,
        "correction_max_m": 0.0,
        "correction_rms_m": 0.0,
        "post_jump_m": raw_jump_L,
    }
    close_info_R = {
        "raw_jump_m": raw_jump_R,
        "raw_slope_jump": 0.0,
        "correction_max_m": 0.0,
        "correction_rms_m": 0.0,
        "post_jump_m": raw_jump_R,
    }
    zL_closed = np.asarray(zL_raw, dtype=float).copy()
    zR_closed = np.asarray(zR_raw, dtype=float).copy()
    closure_applied = False
    if closure_policy == "closed_c1_periodic":
        zL_closed, close_info_L = _close_track_c1_periodic(x, zL_raw)
        zR_closed, close_info_R = _close_track_c1_periodic(x, zR_raw)
        closure_applied = True

    seam_jump_L = float(zL_closed[-1] - zL_closed[0])
    seam_jump_R = float(zR_closed[-1] - zR_closed[0])
    seam_max = float(max(abs(seam_jump_L), abs(seam_jump_R)))
    raw_seam_max = float(max(abs(raw_jump_L), abs(raw_jump_R)))
    seam_open = bool(seam_max > seam_thr)
    if closure_policy == "strict_exact" and raw_seam_max > seam_thr:
        log.warning(
            "scenario_ring: closure_policy=%s, road seam is not closed (left=%.1f mm, right=%.1f mm). "
            "No hidden closure correction is applied.",
            closure_policy,
            1000.0 * raw_jump_L,
            1000.0 * raw_jump_R,
        )
    elif closure_applied:
        log.info(
            "scenario_ring: closure_policy=%s applied smooth C1 ring closure: raw seam L/R = %.1f / %.1f mm, correction max L/R = %.1f / %.1f mm",
            closure_policy,
            1000.0 * raw_jump_L,
            1000.0 * raw_jump_R,
            1000.0 * float(close_info_L.get("correction_max_m", 0.0) or 0.0),
            1000.0 * float(close_info_R.get("correction_max_m", 0.0) or 0.0),
        )

    x = _ensure_increasing_x(x)
    spline_bc = "periodic" if closure_policy == "closed_c1_periodic" else "natural"
    left_spline = CubicSpline(x, zL_closed, bc_type=spline_bc)
    right_spline = CubicSpline(x, zR_closed, bc_type=spline_bc)

    return {
        "x_m": x,
        "zL_m": zL_raw,
        "zR_m": zR_raw,
        "zL_closed_m": zL_closed,
        "zR_closed_m": zR_closed,
        "left_spline": left_spline,
        "right_spline": right_spline,
        "meta": {
            "dx_m": dx_m,
            "track_m": track_m,
            "road_state_contract": bool(use_road_state_contract),
            "L_total_m": L_total,
            "n_pts": int(len(x)),
            "closure_policy": closure_policy,
            "closure_applied": bool(closure_applied),
            "closure_bc_type": spline_bc,
            "raw_seam_jump_left_m": raw_jump_L,
            "raw_seam_jump_right_m": raw_jump_R,
            "raw_seam_max_jump_m": raw_seam_max,
            "seam_jump_left_m": seam_jump_L,
            "seam_jump_right_m": seam_jump_R,
            "seam_max_jump_m": seam_max,
            "seam_threshold_m": seam_thr,
            "seam_open": seam_open,
            "closure_correction_left_max_m": float(close_info_L.get("correction_max_m", 0.0) or 0.0),
            "closure_correction_right_max_m": float(close_info_R.get("correction_max_m", 0.0) or 0.0),
            "closure_correction_left_rms_m": float(close_info_L.get("correction_rms_m", 0.0) or 0.0),
            "closure_correction_right_rms_m": float(close_info_R.get("correction_rms_m", 0.0) or 0.0),
            "raw_slope_jump_left": float(close_info_L.get("raw_slope_jump", 0.0) or 0.0),
            "raw_slope_jump_right": float(close_info_R.get("raw_slope_jump", 0.0) or 0.0),
        },
    }


def summarize_ring_track_segments(spec: Dict[str, Any], tracks: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Summarise generated road by segment without changing the generated profile.

    Why this exists:
    - users often read ``max-min`` as "amplitude", while for a sine the canonical
      amplitude ``A`` is *half* of peak-to-peak;
    - absolute road Z can drift between segments because the ring keeps continuity and
      does not hide seam drift with a fake closure ramp;
    - the editor therefore needs per-segment *local* diagnostics (x-range, start/end,
      peak-to-peak, actual amplitude) instead of one coarse full-ring number.

    Returns a list of dict rows, one row per segment. All values are derived from the
    already generated canonical tracks and are therefore service diagnostics only.
    """
    segs = list(spec.get("segments", []) or [])
    x = np.asarray(tracks.get("x_m", []), dtype=float).reshape(-1)
    z_l = np.asarray(tracks.get("zL_m", []), dtype=float).reshape(-1)
    z_r = np.asarray(tracks.get("zR_m", []), dtype=float).reshape(-1)
    out: List[Dict[str, Any]] = []
    if x.size == 0 or z_l.size != x.size or z_r.size != x.size:
        return out

    x_cursor = float(x[0])
    tol = 1e-9
    v_cur_kph = float(spec.get("v0_kph", 0.0) or 0.0)
    use_road_state_contract = _road_state_contract_enabled(spec)
    first_start_center_mm = 0.0
    first_start_cross_pct = 0.0
    prev_end_center_mm = 0.0
    prev_end_cross_pct = 0.0
    for i, seg in enumerate(segs):
        motion = _segment_motion_contract(seg, v_cur_kph)
        length_m = _segment_length_canonical_m(
            v_cur_kph,
            seg,
            fallback_dt_s=float(spec.get("dt_s", 0.01) or 0.01),
            dx_m=float(tracks.get("meta", {}).get("dx_m", spec.get("dx_m", 0.02)) or 0.02),
        )
        x0 = float(x_cursor)
        x1 = float(x0 + max(0.0, length_m))
        # Last segment includes the right edge; others are half-open to avoid duplicates.
        if i >= len(segs) - 1:
            mask = (x >= x0 - tol) & (x <= x1 + tol)
        else:
            mask = (x >= x0 - tol) & (x < x1 - tol)
            if not np.any(mask):
                mask = (x >= x0 - tol) & (x <= x1 + tol)
        xx = np.asarray(x[mask], dtype=float)
        zl = np.asarray(z_l[mask], dtype=float)
        zr = np.asarray(z_r[mask], dtype=float)
        road = dict(seg.get("road", {}) or {})
        road_mode = str(road.get("mode", "ISO8608") or "ISO8608").upper()

        def _stats(arr: np.ndarray) -> Dict[str, float]:
            if arr.size == 0:
                return {
                    "z_min_mm": float("nan"),
                    "z_max_mm": float("nan"),
                    "p2p_mm": float("nan"),
                    "amp_mm": float("nan"),
                    "z_start_mm": float("nan"),
                    "z_end_mm": float("nan"),
                    "x_local_end_m": float("nan"),
                }
            zmin = float(np.nanmin(arr))
            zmax = float(np.nanmax(arr))
            p2p_mm = 1000.0 * (zmax - zmin)
            zmed = float(np.nanmedian(arr))
            amp_mm = 1000.0 * float(np.nanmax(np.abs(arr - zmed)))
            return {
                "z_min_mm": 1000.0 * zmin,
                "z_max_mm": 1000.0 * zmax,
                "p2p_mm": p2p_mm,
                "amp_mm": amp_mm,
                "z_start_mm": 1000.0 * float(arr[0]),
                "z_end_mm": 1000.0 * float(arr[-1]),
                "x_local_end_m": float(xx[-1] - xx[0]) if xx.size >= 2 else 0.0,
            }

        st_l = _stats(zl)
        st_r = _stats(zr)
        road_state = {
            "start_center_mm": float("nan"),
            "end_center_mm": float("nan"),
            "start_cross_pct": float("nan"),
            "end_cross_pct": float("nan"),
        }
        if use_road_state_contract:
            road_state = _segment_road_state_mm(
                spec,
                segs,
                i,
                prev_end_center_mm=prev_end_center_mm,
                prev_end_cross_pct=prev_end_cross_pct,
                first_start_center_mm=first_start_center_mm,
                first_start_cross_pct=first_start_cross_pct,
            )
            if i == 0:
                first_start_center_mm = float(road_state["start_center_mm"])
                first_start_cross_pct = float(road_state["start_cross_pct"])
                road_state = _segment_road_state_mm(
                    spec,
                    segs,
                    i,
                    prev_end_center_mm=prev_end_center_mm,
                    prev_end_cross_pct=prev_end_cross_pct,
                    first_start_center_mm=first_start_center_mm,
                    first_start_cross_pct=first_start_cross_pct,
                )
            prev_end_center_mm = float(road_state["end_center_mm"])
            prev_end_cross_pct = float(road_state["end_cross_pct"])

        v_cur_kph = float(motion["speed_end_kph"])

        out.append({
            "seg_idx": int(i + 1),
            "name": str(seg.get("name", f"S{i+1}")),
            "drive_mode": str(motion["legacy_mode"]).upper(),
            "turn_direction": str(motion["turn_direction"]).upper(),
            "speed_start_kph": float(motion["speed_start_kph"]),
            "speed_end_kph": float(motion["speed_end_kph"]),
            "turn_radius_m": float(motion["turn_radius_m"]),
            "road_mode": road_mode,
            "x_start_m": x0,
            "x_end_m": x1,
            "length_m": float(max(0.0, length_m)),
            "generated_x_local_end_m": float(max(0.0, xx[-1] - xx[0])) if xx.size >= 2 else 0.0,
            "aL_req_mm": float(road.get("aL_mm", float("nan"))) if road_mode == "SINE" else float("nan"),
            "aR_req_mm": float(road.get("aR_mm", float("nan"))) if road_mode == "SINE" else float("nan"),
            "lambdaL_m": float(road.get("lambdaL_m", float("nan"))) if road_mode == "SINE" else float("nan"),
            "lambdaR_m": float(road.get("lambdaR_m", float("nan"))) if road_mode == "SINE" else float("nan"),
            "center_height_start_mm": float(road_state["start_center_mm"]),
            "center_height_end_mm": float(road_state["end_center_mm"]),
            "cross_slope_start_pct": float(road_state["start_cross_pct"]),
            "cross_slope_end_pct": float(road_state["end_cross_pct"]),
            **{f"L_{k}": v for k, v in st_l.items()},
            **{f"R_{k}": v for k, v in st_r.items()},
        })
        x_cursor = x1
    return out


def generate_ring_scenario_bundle(
    spec: Dict[str, Any],
    *,
    out_dir: Path,
    dt_s: float,
    n_laps: int,
    wheelbase_m: float,
    dx_m: float = 0.02,
    seed: Optional[int] = None,
    tag: str = "ring",
) -> Dict[str, Any]:
    """Полный генератор: кольцо -> road_csv + axay_csv + scenario_json."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dt_s = float(max(1e-6, dt_s))
    n_laps = int(max(1, n_laps))
    dx_m = float(max(1e-4, spec.get("dx_m", dx_m)))
    if seed is None and ("seed" in spec):
        try:
            seed = int(spec.get("seed"))
        except Exception:
            log.warning("scenario_ring: spec contains invalid seed=%r; ignoring", spec.get("seed"))
            seed = None
    wheelbase_m = float(max(0.0, wheelbase_m))
    if wheelbase_m <= 0.0:
        raise ValueError("wheelbase_m должен быть > 0")

    drive = generate_ring_drive_profile(spec, dt_s=dt_s, n_laps=n_laps)
    tracks = generate_ring_tracks(spec, dx_m=dx_m, seed=seed)
    L_total = float(tracks["meta"]["L_total_m"])
    left_spline: CubicSpline = tracks["left_spline"]
    right_spline: CubicSpline = tracks["right_spline"]

    t = drive["t_s"]
    dist_front = drive["distance_m"]
    xF = np.mod(dist_front, L_total)
    xR = np.mod(dist_front - wheelbase_m, L_total)

    z_fl = left_spline(xF)
    z_fr = right_spline(xF)
    z_rl = left_spline(xR)
    z_rr = right_spline(xR)

    stem = f"scenario_{tag}"
    road_csv = out_dir / f"{stem}_road.csv"
    axay_csv = out_dir / f"{stem}_axay.csv"
    scenario_json = out_dir / f"{stem}_spec.json"

    z4 = np.column_stack([z_fl, z_fr, z_rl, z_rr])
    write_road_csv(road_csv, t, z4)
    write_axay_csv(axay_csv, t, drive["ax_mps2"], drive["ay_mps2"])

    meta = {
        "dt_s": dt_s,
        "n_laps": n_laps,
        "dx_m": dx_m,
        "seed": None if seed is None else int(seed),
        "v0_kph": float(_resolve_initial_speed_kph(spec)),
        "wheelbase_m": wheelbase_m,
        "track_m": float(_resolve_track_m(spec)),
        "ring_length_m": L_total,
        "lap_time_s": float(drive["t_s"][-1]) / float(n_laps) if n_laps > 0 else float(drive["t_s"][-1]),
        "n_samples": int(len(t)),
        "closure_policy": str(tracks.get("meta", {}).get("closure_policy", "strict_exact") or "strict_exact"),
        "seam_jump_left_m": float(tracks.get("meta", {}).get("seam_jump_left_m", 0.0) or 0.0),
        "seam_jump_right_m": float(tracks.get("meta", {}).get("seam_jump_right_m", 0.0) or 0.0),
        "seam_max_jump_m": float(tracks.get("meta", {}).get("seam_max_jump_m", 0.0) or 0.0),
        "seam_open": bool(tracks.get("meta", {}).get("seam_open", False)),
    }

    spec_to_save = dict(spec)
    spec_to_save["schema_version"] = "ring_v2"
    spec_to_save["closure_policy"] = str(_resolve_closure_policy(spec))
    spec_to_save["v0_kph"] = float(_resolve_initial_speed_kph(spec))
    spec_to_save["track_m"] = float(_resolve_track_m(spec))
    segs_to_save = []
    v_cur_save_kph = float(_resolve_initial_speed_kph(spec))
    for seg in list(spec.get("segments", []) or []):
        seg_saved = dict(seg)
        motion_saved = _segment_motion_contract(seg_saved, v_cur_save_kph)
        seg_saved["length_m"] = _segment_length_canonical_m(
            v_cur_save_kph,
            seg_saved,
            fallback_dt_s=float(dt_s),
            dx_m=float(dx_m),
        )
        seg_saved["drive_mode"] = str(motion_saved["legacy_mode"]).upper()
        seg_saved["turn_direction"] = str(motion_saved["turn_direction"]).upper()
        seg_saved["speed_start_kph"] = float(motion_saved["speed_start_kph"])
        seg_saved["speed_end_kph"] = float(motion_saved["speed_end_kph"])
        if seg_saved["drive_mode"] in ("TURN_LEFT", "TURN_RIGHT"):
            seg_saved["speed_kph"] = float(motion_saved["speed_end_kph"])
        elif seg_saved["drive_mode"] in ("ACCEL", "BRAKE"):
            seg_saved["v_end_kph"] = float(motion_saved["speed_end_kph"])
        else:
            seg_saved["speed_kph"] = float(motion_saved["speed_end_kph"])
        v_cur_save_kph = float(motion_saved["speed_end_kph"])
        segs_to_save.append(seg_saved)
    spec_to_save["segments"] = segs_to_save
    spec_to_save["dt_s"] = float(dt_s)
    spec_to_save["n_laps"] = int(n_laps)
    spec_to_save["wheelbase_m"] = float(wheelbase_m)
    spec_to_save["dx_m"] = float(dx_m)
    if seed is not None:
        spec_to_save["seed"] = int(seed)
    spec_to_save["_generated_meta"] = meta
    spec_to_save["_generated_outputs"] = {"road_csv": road_csv.name, "axay_csv": axay_csv.name}

    scenario_json.write_text(
        json.dumps(spec_to_save, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "road_csv": str(road_csv),
        "axay_csv": str(axay_csv),
        "scenario_json": str(scenario_json),
        "meta": meta,
    }


def validate_ring_spec(spec: Dict[str, Any]) -> Dict[str, List[str]]:
    """Мягкая валидация спецификации.

    Возвращает {"errors": [...], "warnings": [...]}
    """
    errors: List[str] = []
    warns: List[str] = []

    segs = list(spec.get("segments", []))
    if not segs:
        errors.append("Не задан ни один сегмент кольца.")
        return {"errors": errors, "warnings": warns}

    closure_policy = str(spec.get("closure_policy", "closed_c1_periodic") or "closed_c1_periodic").strip().lower()
    if closure_policy not in ("closed_c1_periodic", "strict_exact"):
        errors.append("closure_policy должен быть одним из 'closed_c1_periodic' или 'strict_exact'.")
    if "track_m" in spec:
        try:
            track_m = float(spec.get("track_m", 1.0) or 1.0)
        except Exception:
            track_m = -1.0
        if track_m <= 0.0:
            errors.append("track_m должен быть > 0.")

    v0_eff_kph = _resolve_initial_speed_kph(spec)
    if not (float(spec.get("v0_kph", 0.0) or 0.0) > 0.0):
        warns.append(f"Начальная скорость кольца не задана явно или равна 0 — будет использована эффективная v0_kph={v0_eff_kph:.3f} км/ч.")

    for i, seg in enumerate(segs, start=1):
        dur = float(seg.get("duration_s", 0.0))
        if dur <= 0:
            errors.append(f"Сегмент {i}: длительность должна быть > 0.")
        motion = _segment_motion_contract(seg, v0_eff_kph if i == 1 else 0.0)
        mode = str(seg.get("drive_mode", "STRAIGHT")).upper()
        if mode not in ("STRAIGHT", "TURN_LEFT", "TURN_RIGHT", "ACCEL", "BRAKE"):
            errors.append(
                f"Сегмент {i}: неизвестный drive_mode={mode!r}. Допустимо: STRAIGHT, TURN_LEFT, TURN_RIGHT, ACCEL, BRAKE."
            )
            continue
        if "turn_direction" in seg and str(seg.get("turn_direction", "") or "").upper() not in ("STRAIGHT", "LEFT", "RIGHT"):
            errors.append(f"Сегмент {i}: turn_direction должен быть STRAIGHT, LEFT или RIGHT.")
        if motion["turn_direction"] in ("LEFT", "RIGHT"):
            r = float(seg.get("turn_radius_m", 0.0))
            if r <= 0:
                errors.append(f"Сегмент {i}: радиус поворота должен быть > 0.")
        if mode in ("STRAIGHT", "TURN_LEFT", "TURN_RIGHT"):
            sp = float(seg.get("speed_kph", 0.0))
            if "speed_kph" not in seg:
                warns.append(f"Сегмент {i}: нет поля speed_kph (алиасы запрещены).")
            if sp <= 0:
                warns.append(f"Сегмент {i}: скорость не задана/нулевая — проверьте режим движения.")
        if mode in ("ACCEL", "BRAKE"):
            ve = float(seg.get("v_end_kph", 0.0))
            if "v_end_kph" not in seg:
                warns.append(f"Сегмент {i}: нет поля v_end_kph (алиасы запрещены).")
            if ve < 0:
                errors.append(f"Сегмент {i}: конечная скорость не может быть отрицательной.")

        road = dict(seg.get("road", {}))
        road_mode = str(road.get("mode", "ISO8608")).upper()
        for state_key in ("center_height_start_mm", "center_height_end_mm"):
            if state_key in road:
                try:
                    state_mm = float(road.get(state_key, 0.0))
                except Exception:
                    errors.append(f"Сегмент {i}: {state_key} должен быть числом.")
                    continue
                if abs(state_mm) > 2000.0:
                    warns.append(f"Сегмент {i}: {state_key}={state_mm:.1f} мм выглядит подозрительно большим.")
        for state_key in ("cross_slope_start_pct", "cross_slope_end_pct"):
            if state_key in road:
                try:
                    slope_pct = float(road.get(state_key, 0.0))
                except Exception:
                    errors.append(f"Сегмент {i}: {state_key} должен быть числом.")
                    continue
                if abs(slope_pct) > 50.0:
                    warns.append(f"Сегмент {i}: {state_key}={slope_pct:.2f}% выглядит подозрительно большим.")
        if road_mode == "SINE":
            for side_key in ("aL_mm", "aR_mm"):
                if side_key in road:
                    a_mm = abs(float(road.get(side_key, 0.0)))
                    if a_mm > 300.0:
                        warns.append(
                            f"Сегмент {i}: {side_key}={a_mm:.1f} мм выглядит подозрительно большим. Проверьте единицы — канон ожидает миллиметры, не метры."
                        )
            for lam_key in ("lambdaL_m", "lambdaR_m"):
                if lam_key in road and float(road.get(lam_key, 0.0)) <= 0.0:
                    errors.append(f"Сегмент {i}: {lam_key} должен быть > 0.")

        if road_mode in ("ISO", "ISO8608", "ISO_8608"):
            iso_class = str(road.get("iso_class", "C")).upper()
            if iso_class not in tuple("ABCDEFGH"):
                errors.append(f"Сегмент {i}: iso_class должен быть в диапазоне A..H.")

            gd_pick = str(road.get("gd_pick", "mid")).lower()
            if gd_pick not in ("lower", "mid", "upper"):
                errors.append(f"Сегмент {i}: gd_pick должен быть одним из lower/mid/upper.")

            waviness_w = float(road.get("waviness_w", 2.0))
            if waviness_w <= 0.0:
                errors.append(f"Сегмент {i}: waviness_w должен быть > 0.")

            coh = float(road.get("left_right_coherence", 0.5))
            if not (0.0 <= coh <= 1.0):
                warns.append(f"Сегмент {i}: left_right_coherence вне [0,1] — будет зажат в допустимый диапазон.")

        for ev in list(seg.get("events", [])):
            x0 = float(ev.get("start_m", 0.0))
            L = float(ev.get("length_m", 0.0))
            if L <= 0:
                warns.append(f"Сегмент {i}: событие профиля с нулевой длиной будет проигнорировано.")
            if x0 < 0:
                warns.append(f"Сегмент {i}: событие начинается до 0 м — будет обрезано.")
            if "depth_mm" in ev:
                depth_mm = abs(float(ev.get("depth_mm", 0.0)))
                if depth_mm > 300.0:
                    warns.append(
                        f"Сегмент {i}: событие depth_mm={depth_mm:.1f} мм выглядит подозрительно большим. Проверьте единицы: канон ожидает миллиметры."
                    )

    try:
        v_end_kph = float(v0_eff_kph)
        for seg in segs:
            motion = _segment_motion_contract(seg, v_end_kph)
            v_end_kph = float(motion["speed_end_kph"])
        if abs(float(v_end_kph) - float(v0_eff_kph)) > 0.5:
            warns.append(
                f"Стык скорости кольца не замкнут: start={float(v0_eff_kph):.2f} км/ч, end={float(v_end_kph):.2f} км/ч. Для замкнутого кольца скорости начала и конца должны совпадать."
            )
    except Exception:
        pass

    if _road_state_contract_enabled(spec):
        try:
            road0 = dict((segs[0] or {}).get("road", {}) or {})
            start_center = float(road0.get("center_height_start_mm", 0.0) or 0.0)
            start_cross = float(road0.get("cross_slope_start_pct", 0.0) or 0.0)
            road_last = dict((segs[-1] or {}).get("road", {}) or {})
            if "center_height_end_mm" in road_last and abs(float(road_last.get("center_height_end_mm", 0.0) or 0.0) - start_center) > 1e-9:
                warns.append("Последний сегмент: center_height_end_mm отличается от начала первого сегмента; UI/генератор всё равно замкнёт кольцо по начальному состоянию.")
            if "cross_slope_end_pct" in road_last and abs(float(road_last.get("cross_slope_end_pct", 0.0) or 0.0) - start_cross) > 1e-9:
                warns.append("Последний сегмент: cross_slope_end_pct отличается от начала первого сегмента; UI/генератор всё равно замкнёт кольцо по начальному состоянию.")
        except Exception:
            pass

    has_pothole = False
    has_bump = False
    for seg in segs:
        for ev in list(seg.get("events", [])):
            kind = str(ev.get("kind", "")).lower()
            if "яма" in kind or "pothole" in kind:
                has_pothole = True
            if "препят" in kind or "bump" in kind or "ступ" in kind:
                has_bump = True
    if not has_pothole:
        warns.append("В кольце нет события «яма». По требованиям сценариев оно должно присутствовать.")
    if not has_bump:
        warns.append(
            "В кольце нет события «препятствие». По требованиям сценариев оно должно присутствовать."
        )

    return {"errors": errors, "warnings": warns}
