# -*- coding: utf-8 -*-
"""build_osc_index.py

CLI tool: build/update NPZ index for traceability CSV ↔ NPZ.

Usage:
  python tools/build_osc_index.py --osc workspace/osc --out workspace/osc_index_full.jsonl

Optional:
  --max 5000  (limit number of newest npz)
  --quick     (do not read meta_json, fastest)
"""

from __future__ import annotations

import argparse
from pathlib import Path

from osc_index import build_or_update_index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--osc", action="append", default=[], help="Folder to scan for *.npz (can repeat). Default: workspace/osc")
    ap.add_argument("--out", default="workspace/osc_index_full.jsonl", help="Output index JSONL path")
    ap.add_argument("--max", type=int, default=3000, help="Max files (newest first)")
    ap.add_argument("--no-recursive", action="store_true", help="Do not scan subfolders")
    ap.add_argument("--quick", action="store_true", help="Skip reading meta_json (fast)")
    args = ap.parse_args()

    roots = [Path(p) for p in (args.osc or [])]
    if not roots:
        roots = [Path("workspace") / "osc"]
    out = Path(args.out)

    df = build_or_update_index(
        roots,
        index_path=out,
        recursive=not args.no_recursive,
        max_files=int(args.max) if args.max else None,
        quick=bool(args.quick),
    )
    print(f"Index saved: {out}  rows={len(df)}")


if __name__ == "__main__":
    main()
