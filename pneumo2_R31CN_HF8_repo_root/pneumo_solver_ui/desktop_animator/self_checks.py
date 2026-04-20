# -*- coding: utf-8 -*-
"""Autonomous self-checks for Desktop Animator.

Why:
- the animator is used as a *verification tool*.
- when logs change (new model, new naming, rel0/abs, etc.) we want quick feedback
  without manual debugging.

These checks are intentionally best-effort and non-fatal:
- they never raise exceptions to the GUI loop
- they produce WARN/FAIL messages you can see in the UI and in a JSON next to the NPZ
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json
import numpy as np

from .data_bundle import CORNERS, DataBundle
from .geometry_acceptance import collect_acceptance_status
from .suspension_geometry_diagnostics import collect_suspension_geometry_status
from .cylinder_truth_gate import (
    evaluate_all_cylinder_truth_gates,
    render_cylinder_truth_gate_message,
)
from pneumo_solver_ui.anim_export_contract import summarize_anim_export_contract, summarize_anim_export_validation


@dataclass
class SelfCheckReport:
    level: str  # "OK" | "WARN" | "FAIL"
    messages: List[str]
    stats: Dict[str, Any]

    @property
    def ok(self) -> bool:
        return str(self.level).upper() != "FAIL"

    @property
    def success(self) -> bool:
        return self.ok

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ok"] = self.ok
        d["success"] = self.success
        # make sure it is JSON serializable
        try:
            json.dumps(d)
            return d
        except Exception:
            return {"level": self.level, "messages": list(self.messages), "stats": {}, "ok": self.ok, "success": self.success}


def _finite(a: np.ndarray) -> np.ndarray:
    try:
        return np.isfinite(np.asarray(a, dtype=float))
    except Exception:
        return np.array([], dtype=bool)


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        if np.isnan(v) or np.isinf(v):
            return float(default)
        return v
    except Exception:
        return float(default)


def run_self_checks(
    b: DataBundle,
    *,
    wheel_radius_m: Optional[float] = None,
    track_m: Optional[float] = None,
    wheelbase_m: Optional[float] = None,
) -> SelfCheckReport:
    msgs: List[str] = []
    stats: Dict[str, Any] = {}

    bundle_contract_issues = list(getattr(b, "contract_issues", []) or [])
    if (not bundle_contract_issues) and isinstance(getattr(b, "meta", None), dict):
        bundle_contract_issues = list((b.meta or {}).get("_geometry_contract_issues") or [])
    if bundle_contract_issues:
        stats["geometry_contract_issue_count"] = int(len(bundle_contract_issues))
        msgs.append("FAIL: данные meta_json.geometry не подходят для пакета анимации.")
        for _msg in bundle_contract_issues[:8]:
            msgs.append(f"FAIL: {_msg}")
        if len(bundle_contract_issues) > 8:
            msgs.append(f"FAIL: ... ещё {len(bundle_contract_issues) - 8} geometry-issues.")

    try:
        _contract_summary = dict(summarize_anim_export_contract(getattr(b, "meta", None)) or {})
        _validation_summary = dict(summarize_anim_export_validation(getattr(b, "meta", None)) or {})
    except Exception:
        _contract_summary = {}
        _validation_summary = {}
    try:
        _cyl_truth_gates = dict(evaluate_all_cylinder_truth_gates(getattr(b, "meta", None)) or {})
    except Exception:
        _cyl_truth_gates = {}
    if _contract_summary:
        stats["anim_export_has_solver_points_block"] = bool(_contract_summary.get("has_solver_points_block"))
        stats["anim_export_has_hardpoints_block"] = bool(_contract_summary.get("has_hardpoints_block"))
        stats["anim_export_has_packaging_block"] = bool(_contract_summary.get("has_packaging_block"))
        stats["anim_export_packaging_status"] = str(_contract_summary.get("packaging_status") or "")
        stats["anim_export_packaging_truth_ready"] = bool(_contract_summary.get("packaging_truth_ready"))
    if _validation_summary:
        stats["anim_export_validation_level"] = str(_validation_summary.get("validation_level") or "")
        stats["anim_export_validation_visible_present_family_count"] = int(_validation_summary.get("validation_visible_present_family_count") or 0)
        stats["anim_export_validation_visible_required_family_count"] = int(_validation_summary.get("validation_visible_required_family_count") or 0)
        stats["anim_export_validation_packaging_status"] = str(_validation_summary.get("validation_packaging_status") or "")
        stats["anim_export_validation_packaging_truth_ready"] = bool(_validation_summary.get("validation_packaging_truth_ready"))
    for _cyl_name, _gate in sorted(_cyl_truth_gates.items()):
        _gate_dict = dict(_gate or {})
        stats[f"{_cyl_name}_truth_mode"] = str(_gate_dict.get("mode") or "")
        stats[f"{_cyl_name}_truth_reason"] = str(_gate_dict.get("reason") or "")
        stats[f"{_cyl_name}_truth_enabled"] = bool(_gate_dict.get("enabled"))
        if not bool(_gate_dict.get("enabled")):
            msgs.append("WARN: " + render_cylinder_truth_gate_message(_gate_dict))

    # -----------------
    # Basic time sanity
    # -----------------
    t = np.asarray(b.t, dtype=float)
    stats["n"] = int(t.size)
    if t.size < 2:
        return SelfCheckReport(level="FAIL", messages=["NPZ: слишком мало кадров (n<2)"], stats=stats)

    dt = np.diff(t)
    finite_dt = dt[np.isfinite(dt)]
    if finite_dt.size == 0:
        return SelfCheckReport(level="FAIL", messages=["time: dt нечисловой (NaN/Inf)"], stats=stats)

    stats["t0"] = float(t[0])
    stats["t_end"] = float(t[-1])
    stats["dt_median"] = float(np.median(finite_dt))
    stats["dt_min"] = float(np.min(finite_dt))
    stats["dt_max"] = float(np.max(finite_dt))

    if np.any(dt <= -1e-12):
        msgs.append("FAIL: time не монотонен (есть отрицательные dt).")
    if stats["dt_min"] <= 0.0:
        msgs.append("WARN: time содержит dt=0 (повторы времени).")
    if stats["dt_max"] > 10.0 * max(1e-9, stats["dt_median"]):
        msgs.append("WARN: time имеет большие скачки dt (проверь dt или экспорт).")

    # -----------------
    # Key channels exist?
    # -----------------
    # LAW: Animator must be driven by **absolute** channels. rel0 is optional
    # for plots/analysis, but cannot replace ABS for animation.
    required_main = ["перемещение_рамы_z_м", "скорость_vx_м_с", "yaw_рад"]
    missing = [k for k in required_main if (not b.main.has(k))]
    if missing:
        msgs.append("WARN: отсутствуют ключевые каналы: " + ", ".join(missing))

    if wheelbase_m is not None and _safe_float(wheelbase_m, 0.0) <= 0.0:
        msgs.append("FAIL: self-check input wheelbase_m <= 0. Проверьте meta_json.geometry.wheelbase_m.")
    if track_m is not None and _safe_float(track_m, 0.0) <= 0.0:
        msgs.append("FAIL: self-check input track_m <= 0. Проверьте meta_json.geometry.track_m.")

    # Corners: road + wheel + body corner z
    # Road is allowed either directly in df_main or through the canonical road_csv sidecar.
    # rel0-only road is NOT accepted here.
    miss_corner: List[str] = []
    for c in CORNERS:
        if b.road_series(c, allow_sidecar=True) is None:
            miss_corner.append(f"дорога_{c}_м")
        for base in (
            f"перемещение_колеса_{c}_м",
            DataBundle.frame_corner_key(c, "z"),
        ):
            # ABS is mandatory for geometry. Having only *_rel0 is a contract violation.
            if not b.main.has(base):
                miss_corner.append(base)
    if miss_corner:
        msgs.append(
            "FAIL: отсутствуют ABS-каналы геометрии по углам для анимации: "
            + ", ".join(miss_corner[:10])
            + (" ..." if len(miss_corner) > 10 else "")
        )

    # -----------------
    # rel0 vs abs sanity
    # -----------------
    # For geometry: abs at t0 shouldn't be forced to 0 unless реально = 0.
    rel0_bad = 0
    checked = 0
    for name in ("перемещение_рамы_z_м",) + tuple(f"перемещение_колеса_{c}_м" for c in CORNERS):
        if b.main.has(name) and b.main.has(name + "_rel0"):
            checked += 1
            abs0 = float(b.get_abs(name, 0.0)[0])
            rel00 = float(b.get_rel0(name, 0.0)[0])
            if abs(rel00) > 1e-9:
                rel0_bad += 1
            # if abs0 is exactly 0 but rel0 exists, it's not necessarily wrong
            # but could mean exporter overwrote abs with rel0. We only warn if
            # abs0 is near 0 AND the series magnitude looks non-trivial.
            a = b.get_abs(name, 0.0)
            if abs(abs0) < 1e-6 and np.nanpercentile(np.abs(a), 90) > 1e-3:
                msgs.append(f"WARN: канал {name} выглядит как rel0, но используется как ABS (t0≈0, амплитуда>0).")
    if checked and rel0_bad:
        msgs.append("WARN: rel0-каналы не обнулены в t0 (ожидалось ~0).")

    # -----------------
    # Wheel/road relationship (very rough sanity)
    # -----------------
    wr = _safe_float(wheel_radius_m, 0.30)
    stats["wheel_radius_m"] = float(wr)

    try:
        deltas: List[float] = []
        for c in CORNERS:
            zw = float(b.get_abs(f"перемещение_колеса_{c}_м", 0.0)[0])
            zr_series = b.road_series(c, allow_sidecar=True)
            if zr_series is None:
                raise ValueError(f"missing road trace for {c}")
            zr = float(np.asarray(zr_series, dtype=float)[0])
            deltas.append(zw - zr)
        stats["wheel_minus_road_t0"] = [float(x) for x in deltas]
        # Expect something in [0.5R .. 1.2R] for a center-coordinate wheel_z
        # (tire compression makes it smaller than R).
        lo = 0.5 * wr
        hi = 1.2 * wr
        if any((d < lo or d > hi) for d in deltas):
            msgs.append(
                "WARN: wheel_z - road_z в t0 вне ожидаемого диапазона "
                f"[{lo:.3f}..{hi:.3f}] м. Возможно wheel_z это контакт, или радиус колеса/единицы неверны."
            )
    except Exception:
        pass

    # -----------------
    # Speed transfer + wheel world-pose sanity
    # -----------------
    try:
        vx = np.asarray(b.get("скорость_vx_м_с", 0.0), dtype=float)
        if vx.size:
            stats["speed_vx_t0_mps"] = float(vx[0])

        meta_v0 = None
        if isinstance(getattr(b, "meta", None), dict) and (b.meta or {}).get("vx0_м_с") is not None:
            meta_v0 = _safe_float((b.meta or {}).get("vx0_м_с"), float("nan"))
        if meta_v0 is not None and np.isfinite(meta_v0) and vx.size:
            v0_err = abs(float(vx[0]) - float(meta_v0))
            stats["speed_meta_vx0_t0_err_mps"] = float(v0_err)
            tol_v0 = max(1e-6, 0.02 * max(1.0, abs(float(meta_v0))))
            if v0_err > tol_v0:
                msgs.append(
                    "FAIL: скорость_vx_м_с в t0 не совпадает с meta.vx0_м_с "
                    f"(err={v0_err:.3f} м/с). Проверьте передачу canonical vx0_м_с в модель/экспорт."
                )

        if b.main.has("путь_x_м") and b.main.has("yaw_рад") and vx.size == t.size:
            x_path = np.asarray(b.get("путь_x_м", 0.0), dtype=float)
            yaw = np.asarray(b.get("yaw_рад", 0.0), dtype=float)
            xdot = np.gradient(x_path, t)
            xdot_exp = vx * np.cos(yaw)
            x_err = float(np.nanmax(np.abs(xdot - xdot_exp))) if xdot.size else 0.0
            stats["speed_path_x_consistency_max_err_mps"] = x_err
            if x_err > 0.25:
                msgs.append(
                    f"WARN: d(путь_x_м)/dt не согласован со скоростью_vx_м_с·cos(yaw) (max err={x_err:.3f} м/с)."
                )

        if (
            wheelbase_m is not None
            and track_m is not None
            and _safe_float(wheelbase_m, 0.0) > 0.0
            and _safe_float(track_m, 0.0) > 0.0
            and b.main.has("путь_x_м")
            and b.main.has("путь_y_м")
            and b.main.has("yaw_рад")
        ):
            x_path = np.asarray(b.get("путь_x_м", 0.0), dtype=float)
            y_path = np.asarray(b.get("путь_y_м", 0.0), dtype=float)
            yaw = np.asarray(b.get("yaw_рад", 0.0), dtype=float)
            wb2 = 0.5 * float(wheelbase_m)
            tr2 = 0.5 * float(track_m)
            local_xy = {
                "ЛП": (+wb2, +tr2),
                "ПП": (+wb2, -tr2),
                "ЛЗ": (-wb2, +tr2),
                "ПЗ": (-wb2, -tr2),
            }
            pose_errs = []
            for c in CORNERS:
                x_key = f"колесо_x_{c}_м"
                y_key = f"колесо_y_{c}_м"
                if not (b.main.has(x_key) and b.main.has(y_key)):
                    continue
                x_local, y_local = local_xy[c]
                cy = np.cos(yaw)
                sy = np.sin(yaw)
                x_pred = x_path + cy * x_local - sy * y_local
                y_pred = y_path + sy * x_local + cy * y_local
                x_act = np.asarray(b.get(x_key, 0.0), dtype=float)
                y_act = np.asarray(b.get(y_key, 0.0), dtype=float)
                pose_err = np.hypot(x_act - x_pred, y_act - y_pred)
                pose_errs.append(float(np.nanmax(np.abs(pose_err))) if pose_err.size else 0.0)
            if pose_errs:
                max_pose_err = float(max(pose_errs))
                stats["wheel_xy_pose_max_err_m"] = max_pose_err
                if max_pose_err > 1e-4:
                    msgs.append(
                        f"FAIL: координаты колёс в мире не согласованы с путь_x/путь_y/yaw и wheelbase/track (max err={max_pose_err:.6f} м)."
                    )
    except Exception:
        pass


    # -----------------
    # World XY / road preview sanity (важно для карты/3D)
    # -----------------
    try:
        s_world = b.ensure_s_world()
        xw, yw = b.ensure_world_xy()

        if (xw.shape != s_world.shape) or (yw.shape != s_world.shape):
            msgs.append(
                f"WARN: world_xy shape mismatch: s_world={s_world.shape}, x={xw.shape}, y={yw.shape} "
                "(карта/3D могут быть некорректны)."
            )
        else:
            ds_xy = float(np.nansum(np.hypot(np.diff(xw), np.diff(yw))))
            ds_s = float(s_world[-1] - s_world[0])
            stats["path_len_xy_m"] = ds_xy
            stats["path_len_s_m"] = ds_s
            if ds_s > 1e-9:
                ratio = ds_xy / ds_s
                stats["path_len_ratio_xy_over_s"] = ratio
                # Допускаем небольшие расхождения (интеграция yaw/vx, дискретизация),
                # но если ушло сильно — это почти всегда ошибка осей/единиц.
                if (ratio < 0.85) or (ratio > 1.20):
                    msgs.append(
                        f"WARN: world_xy length differs from s_world (ratio={ratio:.3f}). "
                        "Проверьте оси x/y и единицы скорости/углов."
                    )

        # Быстрый тест построения «ленты дороги» (без OpenGL), чтобы поймать NaN/разрывы данных.
        if t.size >= 5 and s_world.size >= 5:
            i0 = int(np.clip(t.size // 2, 0, t.size - 1))
            # Canonical channels (no aliases).
            yaw0 = float(b.get("yaw_рад", 0.0)[i0])
            vx0 = float(b.get("скорость_vx_м_с", 0.0)[i0])
            la = float(np.clip(25.0 + 2.5 * abs(vx0), 35.0, 140.0))
            s0 = float(s_world[i0])

            s_min = s0 - 12.0
            s_max = s0 + la
            n = 120
            s_nodes = np.linspace(s_min, s_max, n)
            x_nodes = np.interp(s_nodes, s_world, xw)
            y_nodes = np.interp(s_nodes, s_world, yw)

            dx = x_nodes - float(xw[i0])
            dy = y_nodes - float(yw[i0])
            c = float(np.cos(-yaw0))
            s = float(np.sin(-yaw0))
            xl = c * dx - s * dy
            yl = s * dx + c * dy

            # z-profiles
            # Pass wheelbase when known; DataBundle will infer when None.
            s_c, z_c = b.ensure_road_profile(wheelbase_m=wheelbase_m, mode="center")
            s_l, z_l = b.ensure_road_profile(wheelbase_m=wheelbase_m, mode="left")
            s_r, z_r = b.ensure_road_profile(wheelbase_m=wheelbase_m, mode="right")
            zc = np.interp(s_nodes, s_c, z_c)
            zl = np.interp(s_nodes, s_l, z_l)
            zr = np.interp(s_nodes, s_r, z_r)

            dxl = np.gradient(xl)
            dyl = np.gradient(yl)
            norm = np.sqrt(dxl * dxl + dyl * dyl) + 1e-9
            nx = -dyl / norm
            ny = dxl / norm
            half = 1.5  # 3.0 m road width / 2
            left = np.stack([xl + nx * half, yl + ny * half, zl], axis=1)
            right = np.stack([xl - nx * half, yl - ny * half, zr], axis=1)
            verts = np.empty((2 * n, 3), dtype=float)
            verts[0::2] = left
            verts[1::2] = right

            nan_cnt = int(np.isnan(verts).sum())
            stats["road_ribbon_nan_count"] = nan_cnt
            if nan_cnt > 0:
                msgs.append(
                    f"WARN: road ribbon preview contains NaN (count={nan_cnt}). "
                    "Это может ломать 3D/карту; проверьте входные данные дороги."
                )
    except Exception:
        # Не ломаем приложение из-за диагностик: просто не добавляем этот блок.
        pass
    # -----------------
    # Solver-point geometry acceptance (frame/wheel/road)
    # -----------------
    try:
        acc = collect_acceptance_status(b, tol_m=1e-6)
        missing_triplets = list(acc.get("missing_triplets") or [])
        stats["solver_points_acceptance_ok"] = bool(acc.get("ok", False))
        stats["solver_points_acceptance_missing_triplets"] = int(len(missing_triplets))
        stats["solver_points_acceptance_max_invariant_err_m"] = float(acc.get("max_invariant_err_m", 0.0))
        stats["solver_points_acceptance_max_xy_err_m"] = float(acc.get("max_xy_err_m", 0.0))
        stats["solver_points_acceptance_max_xy_frame_wheel_offset_m"] = float(acc.get("max_xy_frame_wheel_offset_m", 0.0))
        stats["solver_points_acceptance_max_xy_frame_road_offset_m"] = float(acc.get("max_xy_frame_road_offset_m", 0.0))
        stats["solver_points_acceptance_max_scalar_err_frame_road_m"] = float(acc.get("max_scalar_err_frame_road_m", 0.0))
        stats["solver_points_acceptance_max_scalar_err_wheel_road_m"] = float(acc.get("max_scalar_err_wheel_road_m", 0.0))
        stats["solver_points_acceptance_max_scalar_err_wheel_frame_m"] = float(acc.get("max_scalar_err_wheel_frame_m", 0.0))
        if missing_triplets:
            preview = ", ".join(missing_triplets[:4])
            if len(missing_triplets) > 4:
                preview += f", +{len(missing_triplets) - 4} more"
            msgs.append(
                "WARN: geometry acceptance uses canonical frame/wheel/road solver-point triplets, but some are missing: "
                + preview
            )
        else:
            max_inv = float(acc.get("max_invariant_err_m", 0.0))
            max_xy = float(acc.get("max_xy_err_m", 0.0))
            max_fr = float(acc.get("max_scalar_err_frame_road_m", 0.0))
            max_wr = float(acc.get("max_scalar_err_wheel_road_m", 0.0))
            max_wf = float(acc.get("max_scalar_err_wheel_frame_m", 0.0))
            tol_geo = 1e-6
            if max(max_inv, max_fr, max_wr, max_wf) > tol_geo:
                msgs.append(
                    "FAIL: solver-point geometry acceptance mismatch: "
                    f"Σ={max_inv:.3e} m, XY={max_xy:.3e} m, "
                    f"wheel-frame={max_wf:.3e} m, wheel-road={max_wr:.3e} m, frame-road={max_fr:.3e} m."
                )
            elif max_xy > tol_geo:
                msgs.append(
                    "WARN: solver-point wheel-road XY mismatch: "
                    f"max XYwr={max_xy:.3e} m while Z/scalar-invariants remain consistent."
                )
    except Exception:
        pass

    # -----------------
    # Suspension geometry observability (arms / cylinders)
    # -----------------
    try:
        sg = collect_suspension_geometry_status(b, tol_m=1e-9)
        rows = list(sg.get("rows") or [])
        stats["susp_geom_corners"] = int(len(rows))
        stats["susp_geom_coincident_cylinder_corners"] = int(len(sg.get("coincident_cylinder_corners") or []))
        stats["susp_geom_missing_second_arm_corners"] = int(len(sg.get("missing_second_arm_corners") or []))
        stats["susp_geom_coincident_arm_joint_corners"] = int(len(sg.get("coincident_arm_joint_corners") or []))
        stats["susp_geom_frame_drift_corners"] = int(len(sg.get("frame_drift_corners") or []))
        stats["susp_geom_wheel_drift_corners"] = int(len(sg.get("wheel_drift_corners") or []))
        stats["susp_geom_cyl1_detached_corners"] = int(len(sg.get("cyl1_detached_corners") or []))
        stats["susp_geom_cyl2_detached_corners"] = int(len(sg.get("cyl2_detached_corners") or []))
        if sg.get("missing_second_arm_corners"):
            msgs.append(
                "WARN: double-wishbone visual contract is incomplete: only one arm geometry is serialized for corners "
                + ", ".join(sg.get("missing_second_arm_corners") or [])
            )
        if sg.get("coincident_arm_joint_corners"):
            msgs.append(
                "WARN: upper/lower arm joints coincide for corners "
                + ", ".join(sg.get("coincident_arm_joint_corners") or [])
                + "; visually this is not a real double wishbone."
            )
        if sg.get("coincident_cylinder_corners"):
            msgs.append(
                "WARN: cylinder channels C1/C2 are geometrically coincident for corners "
                + ", ".join(sg.get("coincident_cylinder_corners") or [])
                + "; visually this is one axis, not two distinct cylinders."
            )
        if sg.get("frame_drift_corners"):
            msgs.append(
                "FAIL: frame-mounted hardpoints drift relative to the chassis for corners "
                + ", ".join(sg.get("frame_drift_corners") or [])
            )
        if sg.get("wheel_drift_corners"):
            msgs.append(
                "FAIL: hub/wheel hardpoints drift relative to the wheel/upright for corners "
                + ", ".join(sg.get("wheel_drift_corners") or [])
            )
        if sg.get("cyl1_detached_corners"):
            msgs.append(
                "FAIL: cyl1_bot is not attached to an arm branch for corners "
                + ", ".join(sg.get("cyl1_detached_corners") or [])
            )
        if sg.get("cyl2_detached_corners"):
            msgs.append(
                "FAIL: cyl2_bot is not attached to an arm branch for corners "
                + ", ".join(sg.get("cyl2_detached_corners") or [])
            )
    except Exception:
        pass

    # -----------------
    # Pneumatics quick sanity
    # -----------------
    if b.p is not None:
        pvals = np.asarray(b.p.values, dtype=float)
        if pvals.size and np.any(~np.isfinite(pvals)):
            msgs.append("WARN: давления содержат NaN/Inf.")
        # pressures below vacuum are suspicious in this project
        if pvals.size and np.nanmin(pvals) < -1e3:
            msgs.append("WARN: давления имеют очень отрицательные значения (вакуум?), проверь модель/единицы.")
    if b.open is not None:
        o = np.asarray(b.open.values, dtype=float)
        if o.size:
            omin = float(np.nanmin(o))
            omax = float(np.nanmax(o))
            stats["open_minmax"] = [omin, omax]
            if omin < -0.05 or omax > 1.05:
                msgs.append(f"WARN: open_values вне [0..1] (min={omin:.3f}, max={omax:.3f}).")
    # Segment meta_json strict consistency check:
    # Требование: все уникальные ID из segment_id/сегмент_id должны быть описаны в meta_json['road']['segments'].
    # Если нет — это ошибка (FAIL) с перечислением пропусков.
    try:
        seg_vals = None
        if b.main.has("segment_id"):
            seg_vals = b.main.column("segment_id")
        elif b.main.has("сегмент_id"):
            seg_vals = b.main.column("сегмент_id")

        if seg_vals is not None:
            used_ids: list[int] = []
            seen_ids: set[int] = set()
            for v in seg_vals:
                try:
                    if v is None:
                        continue
                    if isinstance(v, (float, np.floating)) and not np.isfinite(v):
                        continue
                    sid = int(v)
                except Exception:
                    continue
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    used_ids.append(sid)

            seg_meta = None
            if isinstance(b.meta, dict):
                seg_meta = dig(b.meta, ["road", "segments"], default=None)

            described: set[int] = set()
            if isinstance(seg_meta, list):
                for s in seg_meta:
                    if not isinstance(s, dict):
                        continue
                    v = s.get("id", s.get("segment_id"))
                    try:
                        if v is None:
                            continue
                        described.add(int(v))
                    except Exception:
                        continue
            elif isinstance(seg_meta, dict):
                for k in seg_meta.keys():
                    try:
                        described.add(int(k))
                    except Exception:
                        continue

            missing = [sid for sid in used_ids if sid not in described]
            if missing:
                msgs.append(
                    (
                        "FAIL",
                        "Segment meta mismatch: segment_id содержит ID, которых нет в meta_json['road']['segments'] -> "
                        + ", ".join(str(x) for x in missing)
                        + ".\n"
                        + "Нужно описать каждый ID в meta_json['road']['segments'] (см. docs/07_meta_json_road_segments.md).",
                    )
                )

            extra = sorted(described - set(used_ids)) if used_ids else []
            if extra:
                msgs.append(
                    (
                        "WARN",
                        "meta_json['road']['segments'] содержит ID, которые не встречаются в segment_id -> "
                        + ", ".join(str(x) for x in extra)
                        + ".",
                    )
                )
    except Exception:
        pass

    # Normalize messages (older code sometimes appends tuples like ("FAIL", "...")).
    norm_msgs: List[str] = []
    for m in msgs:
        if isinstance(m, tuple) and len(m) >= 2:
            prefix = str(m[0]).upper().rstrip(":")
            body = str(m[1])
            norm_msgs.append(body if body.startswith(prefix + ":") else f"{prefix}: {body}")
        else:
            norm_msgs.append(str(m))
    msgs = norm_msgs

    # Final level
    level = "OK"
    if any(str(m).startswith("FAIL:") for m in msgs):
        level = "FAIL"
    elif msgs:
        level = "WARN"

    if not msgs:
        msgs = ["OK: базовые проверки пройдены."]

    # Add a tiny reminder on what ABS/REL0 means (helps when debugging)
    msgs.append("info: ABS используется для геометрии; REL0 — для графиков/дельт.")

    # Optional meta hints
    if isinstance(b.meta, dict) and b.meta:
        for k in ("release", "version", "exporter"):
            if k in b.meta:
                stats[f"meta_{k}"] = b.meta.get(k)

    # Geometry stats if provided
    if track_m is not None:
        stats["track_m"] = float(_safe_float(track_m, 0.0))
    if wheelbase_m is not None:
        stats["wheelbase_m"] = float(_safe_float(wheelbase_m, 0.0))

    return SelfCheckReport(level=level, messages=msgs, stats=stats)


def save_selfcheck_json(npz_path: Path, report: SelfCheckReport) -> Optional[Path]:
    """Write a JSON next to NPZ (best-effort)."""
    try:
        p = Path(npz_path).with_suffix(".selfcheck.json")
        p.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return p
    except Exception:
        return None


def format_selfcheck_html(report: SelfCheckReport, *, max_lines: int = 8) -> str:
    """Small HTML snippet for QLabel."""
    lvl = (report.level or "WARN").upper()
    color = {"OK": "#61D095", "WARN": "#F4C55B", "FAIL": "#FF6B6B"}.get(lvl, "#F4C55B")
    lines = list(report.messages)[: int(max_lines)]
    if len(report.messages) > max_lines:
        lines.append(f"... (+{len(report.messages) - max_lines} more)")
    li = "".join(f"<li>{_escape(s)}</li>" for s in lines)
    return f"<div><b style='color:{color}'>Self-check: {lvl}</b><ul style='margin:4px 0 0 16px;padding:0'>{li}</ul></div>"


def _escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
