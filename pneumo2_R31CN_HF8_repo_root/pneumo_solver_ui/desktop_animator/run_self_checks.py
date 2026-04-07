"""CLI helper: run lightweight self-checks for Desktop Animator input data.

Why this exists:
- Engineers need a quick, reproducible sanity-check before trusting the animation.
- The checks are designed to be fast (no heavy plotting) and to fail with a human-readable
  message when the dataset is incomplete or inconsistent.

Usage examples (Windows / PowerShell):
  python -m pneumo_solver_ui.desktop_animator.run_self_checks --npz "pneumo_solver_ui/anim_latest/latest_anim.npz"
  python -m pneumo_solver_ui.desktop_animator.run_self_checks --wheelbase 3.0

If --npz is not provided, the script tries to pick the newest *.npz from:
  pneumo_solver_ui/anim_latest/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np

from .data_bundle import load_npz
from .self_checks import run_self_checks


def _pick_newest_npz(anim_latest_dir: Path) -> Path:
    npzs = sorted(anim_latest_dir.glob("*.npz"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not npzs:
        raise FileNotFoundError(
            f"Не найден ни один *.npz в {anim_latest_dir}. "
            "Сначала выполните расчёт и экспорт данных для анимации."
        )
    return npzs[0]


def _road_profile_quick_check(report: Dict[str, Any], b, wheelbase_m: float) -> None:
    # Adds diagnostics to report (does not raise unless the input is broken).
    out: Dict[str, Any] = {}

    road_src = {corner: b.road_series(corner, allow_sidecar=True) for corner in ("ЛП", "ПП", "ЛЗ", "ПЗ")}
    missing = [f"дорога_{corner}_м" for corner, arr in road_src.items() if arr is None]
    if missing:
        out["ok"] = False
        out["reason"] = "missing_road_signals"
        out["missing"] = missing
        report["road_profile"] = out
        return

    try:
        ss, zz = b.ensure_road_profile(wheelbase_m=float(wheelbase_m), mode="center")
        sw = b.ensure_s_world()
        zc = np.interp(sw, ss, zz)

        out["ok"] = True
        out["wheelbase_m"] = float(wheelbase_m)
        out["profile_points"] = int(ss.size)
        out["z_min_m"] = float(np.nanmin(zz))
        out["z_max_m"] = float(np.nanmax(zz))
        out["z_center_interp_min_m"] = float(np.nanmin(zc))
        out["z_center_interp_max_m"] = float(np.nanmax(zc))

        # Spot-check that the reconstructed profile passes through axle center samples.
        # This should be ~0 (numerical eps), otherwise the merge/interp logic is wrong.
        zF = 0.5 * (
            np.asarray(road_src["ЛП"], dtype=float)
            + np.asarray(road_src["ПП"], dtype=float)
        )
        zR = 0.5 * (
            np.asarray(road_src["ЛЗ"], dtype=float)
            + np.asarray(road_src["ПЗ"], dtype=float)
        )
        sF = sw + 0.5 * float(wheelbase_m)
        sR = sw - 0.5 * float(wheelbase_m)

        # sample a limited number of points for speed
        n = sw.size
        if n > 0:
            idx = np.unique(np.linspace(0, n - 1, num=min(200, n), dtype=int))
            zF_i = np.interp(sF[idx], ss, zz)
            zR_i = np.interp(sR[idx], ss, zz)
            out["axle_fit_max_abs_err_m"] = float(
                max(np.nanmax(np.abs(zF_i - zF[idx])), np.nanmax(np.abs(zR_i - zR[idx])))
            )

    except Exception as e:
        out["ok"] = False
        out["reason"] = "exception"
        out["error"] = str(e)

    report["road_profile"] = out


def main() -> int:
    ap = argparse.ArgumentParser(description="Desktop Animator: быстрые самопроверки данных")
    ap.add_argument(
        "--npz",
        type=str,
        default="",
        help="Путь к *.npz для анимации. Если не указан — берётся самый новый из pneumo_solver_ui/anim_latest/",
    )
    ap.add_argument(
        "--wheelbase",
        type=float,
        default=3.0,
        help="Wheelbase (м) для реконструкции профиля дороги в самопроверке (если геометрия не извлекается автоматически).",
    )
    ap.add_argument(
        "--json-out",
        type=str,
        default="",
        help="Если задано — сохранить отчёт в JSON по этому пути.",
    )

    args = ap.parse_args()

    try:
        if args.npz:
            npz_path = Path(args.npz)
        else:
            anim_latest_dir = Path(__file__).resolve().parents[1] / "anim_latest"
            npz_path = _pick_newest_npz(anim_latest_dir)

        b = load_npz(npz_path)
        rep = run_self_checks(b)
        report = rep.to_dict()
        report["ok"] = (report.get("level") != "FAIL")
        report["source_npz"] = str(npz_path)

        _road_profile_quick_check(report, b, wheelbase_m=float(args.wheelbase))

        txt = json.dumps(report, ensure_ascii=False, indent=2)
        print(txt)

        if args.json_out:
            out_path = Path(args.json_out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(txt, encoding="utf-8")

        return 0

    except Exception as e:
        print(f"SELF-CHECK FAILED: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
