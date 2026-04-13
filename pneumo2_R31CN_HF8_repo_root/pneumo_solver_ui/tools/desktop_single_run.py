# -*- coding: utf-8 -*-
"""Desktop-safe single-run tool for one scenario without WEB UI."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd


if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"


from pneumo_solver_ui.module_loading import load_python_module_from_path
from pneumo_solver_ui.ui_simulation_helpers import call_simulate, parse_sim_output
from pneumo_solver_ui.desktop_run_setup_runtime import (
    desktop_single_run_cache_dir,
    desktop_single_run_cache_key,
    mirror_tree,
    remap_saved_files_to_dir,
)


try:
    from pneumo_solver_ui.npz_bundle import export_full_log_to_npz
except Exception:
    export_full_log_to_npz = None  # type: ignore[assignment]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _metric_peak_deg(df: pd.DataFrame | None, column: str) -> float | None:
    if not isinstance(df, pd.DataFrame) or column not in df.columns:
        return None
    try:
        arr = pd.to_numeric(df[column], errors="coerce").dropna().to_numpy(dtype=float)
        if arr.size == 0:
            return None
        return float(numpy_abs_max_deg(arr))
    except Exception:
        return None


def numpy_abs_max_deg(arr_rad: Any) -> float:
    import numpy as np

    return float(np.max(np.abs(np.asarray(arr_rad, dtype=float))) * 180.0 / math.pi)


def _scalar_from_frame(df: pd.DataFrame | None, key: str) -> Any:
    if not isinstance(df, pd.DataFrame) or df.empty or key not in df.columns:
        return None
    try:
        return df.iloc[0][key]
    except Exception:
        return None


def _maybe_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    try:
        if isinstance(value, (int, float)) or hasattr(value, "__int__"):
            return bool(int(value))
    except Exception:
        pass
    if isinstance(value, str):
        s = value.strip().lower()
        if s in {"1", "true", "yes", "on"}:
            return True
        if s in {"0", "false", "no", "off"}:
            return False
    return None


def _save_optional_frame(df: Any, path: Path) -> bool:
    if not isinstance(df, pd.DataFrame):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    return True


def build_desktop_run_summary(
    parsed: dict[str, Any],
    test_row: dict[str, Any],
    *,
    dt: float,
    t_end: float,
    record_full: bool,
    outdir: Path,
    cache_dir: Path | None = None,
    cache_policy: str = "off",
    cache_hit: bool = False,
    export_csv: bool = True,
    export_npz: bool = False,
    run_profile: str = "detail",
) -> dict[str, Any]:
    df_main = parsed.get("df_main")
    df_atm = parsed.get("df_atm")
    df_p = parsed.get("df_p")
    df_mdot = parsed.get("df_mdot")
    df_open = parsed.get("df_open")

    time_start = None
    time_end = None
    if isinstance(df_main, pd.DataFrame) and "время_с" in df_main.columns and not df_main.empty:
        try:
            time_start = float(pd.to_numeric(df_main["время_с"], errors="coerce").iloc[0])
            time_end = float(pd.to_numeric(df_main["время_с"], errors="coerce").iloc[-1])
        except Exception:
            time_start = None
            time_end = None

    mech_ok = _maybe_bool(_scalar_from_frame(df_atm, "mech_selfcheck_ok"))
    mech_msg = _scalar_from_frame(df_atm, "mech_selfcheck_msg")
    if mech_msg is not None:
        mech_msg = str(mech_msg)

    summary = {
        "ok": True,
        "scenario_name": str(test_row.get("имя") or test_row.get("name") or "desktop_run"),
        "scenario_type": str(test_row.get("тип") or test_row.get("type") or ""),
        "dt_s": float(dt),
        "t_end_s": float(t_end),
        "record_full": bool(record_full),
        "run_profile": str(run_profile or "").strip() or "detail",
        "cache_policy": str(cache_policy or "").strip() or "off",
        "cache_hit": bool(cache_hit),
        "export_csv": bool(export_csv),
        "export_npz": bool(export_npz),
        "outdir": str(outdir),
        "cache_dir": str(cache_dir) if cache_dir is not None else None,
        "df_main_rows": int(len(df_main)) if isinstance(df_main, pd.DataFrame) else 0,
        "df_atm_rows": int(len(df_atm)) if isinstance(df_atm, pd.DataFrame) else 0,
        "df_p_rows": int(len(df_p)) if isinstance(df_p, pd.DataFrame) else 0,
        "df_mdot_rows": int(len(df_mdot)) if isinstance(df_mdot, pd.DataFrame) else 0,
        "df_open_rows": int(len(df_open)) if isinstance(df_open, pd.DataFrame) else 0,
        "time_start_s": time_start,
        "time_end_s": time_end,
        "roll_peak_deg": _metric_peak_deg(df_main, "крен_phi_рад"),
        "pitch_peak_deg": _metric_peak_deg(df_main, "тангаж_theta_рад"),
        "mech_selfcheck_ok": mech_ok,
        "mech_selfcheck_msg": mech_msg,
        "saved_files": {},
    }

    if isinstance(df_main, pd.DataFrame) and df_main.empty:
        summary["ok"] = False
    if mech_ok is False:
        summary["ok"] = False
    return summary


def _write_run_artifacts(
    parsed: dict[str, Any],
    outdir: Path,
    *,
    export_csv: bool = True,
) -> dict[str, str]:
    outdir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}
    if not bool(export_csv):
        return saved
    file_map = {
        "df_main": outdir / "df_main.csv",
        "df_drossel": outdir / "df_drossel.csv",
        "df_energy_drossel": outdir / "df_energy_drossel.csv",
        "df_Eedges": outdir / "df_energy_edges.csv",
        "df_Egroups": outdir / "df_energy_groups.csv",
        "df_atm": outdir / "df_atm.csv",
        "df_p": outdir / "df_p.csv",
        "df_mdot": outdir / "df_mdot.csv",
        "df_open": outdir / "df_open.csv",
    }
    for key, target in file_map.items():
        if _save_optional_frame(parsed.get(key), target):
            saved[key] = str(target)
    return saved


def _export_npz_bundle(parsed: dict[str, Any], outdir: Path, summary: dict[str, Any]) -> str | None:
    if export_full_log_to_npz is None:
        return None
    df_main = parsed.get("df_main")
    if not isinstance(df_main, pd.DataFrame) or df_main.empty:
        return None
    target = outdir / "full_log_bundle.npz"
    export_full_log_to_npz(
        target,
        df_main,
        df_p=parsed.get("df_p"),
        df_q=parsed.get("df_mdot"),
        df_open=parsed.get("df_open"),
        meta={
            "scenario_name": summary.get("scenario_name"),
            "scenario_type": summary.get("scenario_type"),
            "run_profile": summary.get("run_profile"),
            "cache_hit": summary.get("cache_hit"),
        },
    )
    return str(target)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run one desktop scenario without WEB UI")
    ap.add_argument("--params", required=True, help="Path to base params JSON")
    ap.add_argument("--test", required=True, help="Path to temporary suite JSON")
    ap.add_argument("--test_index", type=int, default=0, help="Scenario index in suite JSON")
    ap.add_argument("--model", default="", help="Optional model .py path; defaults to worldroad model")
    ap.add_argument("--dt", type=float, default=None)
    ap.add_argument("--t_end", type=float, default=None)
    ap.add_argument("--record_full", action="store_true")
    ap.add_argument("--cache_policy", choices=["reuse", "refresh", "off"], default="off")
    ap.add_argument("--run_profile", default="detail")
    ap.add_argument("--export_npz", action="store_true")
    ap.add_argument("--no_export_csv", action="store_true")
    ap.add_argument("--outdir", required=True, help="Output folder for CSV and JSON artifacts")
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    default_model = (root / "model_pneumo_v9_mech_doublewishbone_worldroad.py").resolve()
    model_path = Path(args.model).resolve() if str(args.model or "").strip() else default_model
    params_path = Path(args.params).resolve()
    suite_path = Path(args.test).resolve()
    outdir = Path(args.outdir).resolve()

    params = _load_json(params_path)
    suite = _load_json(suite_path)
    if not isinstance(params, dict):
        raise SystemExit("params JSON must contain an object")
    if not isinstance(suite, list) or not suite:
        raise SystemExit("suite JSON must contain a non-empty list")

    try:
        test_row = dict(suite[int(args.test_index)])
    except Exception as exc:
        raise SystemExit(f"Cannot resolve scenario index: {exc}") from exc

    dt = float(args.dt) if args.dt is not None else _safe_float(test_row.get("dt"), 0.01)
    t_end = float(args.t_end) if args.t_end is not None else _safe_float(
        test_row.get("t_end", test_row.get("t_end_s")),
        1.0,
    )
    export_csv = not bool(args.no_export_csv)
    cache_policy = str(args.cache_policy or "off").strip().lower() or "off"
    run_profile = str(args.run_profile or "detail").strip().lower() or "detail"
    cache_key = desktop_single_run_cache_key(
        params=params,
        test_row=test_row,
        dt=dt,
        t_end=t_end,
        record_full=bool(args.record_full),
        export_csv=bool(export_csv),
        export_npz=bool(args.export_npz),
        run_profile=run_profile,
    )
    cache_dir = desktop_single_run_cache_dir(cache_key)
    cache_summary_path = cache_dir / "run_summary.json"
    summary_path = outdir / "run_summary.json"

    if cache_policy == "reuse" and cache_summary_path.exists():
        mirror_tree(cache_dir, outdir)
        cached_summary = _load_json(summary_path)
        if isinstance(cached_summary, dict):
            cached_summary["outdir"] = str(outdir)
            cached_summary["cache_hit"] = True
            cached_summary["cache_policy"] = cache_policy
            cached_summary["run_profile"] = run_profile
            cached_summary["export_csv"] = bool(export_csv)
            cached_summary["export_npz"] = bool(args.export_npz)
            cached_summary["saved_files"] = remap_saved_files_to_dir(
                cached_summary.get("saved_files"),
                outdir,
            )
            cached_summary["cache_key"] = cache_key
            cached_summary["cache_dir"] = str(cache_dir)
            summary_path.write_text(
                json.dumps(cached_summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(json.dumps(cached_summary, ensure_ascii=False, indent=2))
            return 0 if bool(cached_summary.get("ok", True)) else 2

    model_mod = load_python_module_from_path(model_path, "desktop_single_run_model")
    raw = call_simulate(
        model_mod,
        params,
        test_row,
        dt=dt,
        t_end=t_end,
        record_full=bool(args.record_full),
    )
    parsed = parse_sim_output(raw, want_full=bool(args.record_full))

    saved = _write_run_artifacts(parsed, outdir, export_csv=export_csv)
    summary = build_desktop_run_summary(
        parsed,
        test_row,
        dt=dt,
        t_end=t_end,
        record_full=bool(args.record_full),
        outdir=outdir,
        cache_dir=cache_dir if cache_policy in {"reuse", "refresh"} else None,
        cache_policy=cache_policy,
        cache_hit=False,
        export_csv=bool(export_csv),
        export_npz=bool(args.export_npz),
        run_profile=run_profile,
    )
    if bool(args.export_npz):
        npz_path = _export_npz_bundle(parsed, outdir, summary)
        if npz_path:
            saved["npz_bundle"] = npz_path
    summary["saved_files"] = saved
    summary["cache_key"] = cache_key
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if cache_policy in {"reuse", "refresh"}:
        mirror_tree(outdir, cache_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if bool(summary.get("ok", True)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
