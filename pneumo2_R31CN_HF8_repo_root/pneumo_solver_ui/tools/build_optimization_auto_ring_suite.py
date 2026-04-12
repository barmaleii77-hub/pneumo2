# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"

from pneumo_solver_ui.optimization_auto_ring_suite import materialize_optimization_auto_ring_suite_json


def _ui_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_arg_parser() -> argparse.ArgumentParser:
    ui_root = _ui_root()
    ap = argparse.ArgumentParser(
        description="Materialize an automatic staged optimization suite from a user ring scenario",
    )
    ap.add_argument("--workspace-dir", required=True, help="Workspace directory where ui_state/optimization_auto_ring_suite will be written")
    ap.add_argument("--suite-source-json", default=str(ui_root / "default_suite.json"))
    ap.add_argument("--road-csv", required=True)
    ap.add_argument("--axay-csv", required=True)
    ap.add_argument("--scenario-json", required=True)
    ap.add_argument("--window-s", type=float, default=4.0, help="Heuristic fragment window length in seconds")
    return ap


def main() -> int:
    args = build_arg_parser().parse_args()
    suite_path = materialize_optimization_auto_ring_suite_json(
        args.workspace_dir,
        suite_source_path=args.suite_source_json,
        road_csv=args.road_csv,
        axay_csv=args.axay_csv,
        scenario_json=args.scenario_json,
        window_s=float(args.window_s),
    )
    print(f"suite_json={suite_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
