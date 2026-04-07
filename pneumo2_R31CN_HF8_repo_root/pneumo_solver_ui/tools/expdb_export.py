#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""expdb_export.py (R57)

Small helper to export ExperimentDB (sqlite/duckdb) to CSV/JSON.

Examples
--------
  python pneumo_solver_ui/tools/expdb_export.py --db runs/dist_runs/DIST_*/experiments.duckdb --run-id <RUN_ID> --out trials.csv

If --run-id is omitted, the script will export the latest run in DB.

"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to experiments.sqlite / .duckdb")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--out", required=True, help="Output CSV file")
    ap.add_argument("--metrics-out", default=None, help="Optional JSON with run_metrics")
    args = ap.parse_args()

    from pneumo_solver_ui.pneumo_dist.expdb import ExperimentDB

    db = ExperimentDB(str(args.db))
    db.connect(); db.init_schema()

    run_id = args.run_id
    if not run_id:
        runs = db.list_runs(limit=5)
        if not runs:
            raise SystemExit("No runs found in DB")
        run_id = str(runs[0].get("run_id"))
        print("Auto-selected run_id:", run_id)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = db.export_trials_csv(run_id, str(out))
    print(f"Exported {n} trials to {out}")

    if args.metrics_out:
        m = db.fetch_metrics(run_id, limit=200000)
        _write_json(Path(args.metrics_out), m)
        print(f"Saved metrics JSON to {args.metrics_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
