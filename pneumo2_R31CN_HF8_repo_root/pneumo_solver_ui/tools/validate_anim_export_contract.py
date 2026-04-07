#!/usr/bin/env python3
from __future__ import annotations

"""Validate explicit anim export contract from anim_latest pointer or NPZ."""

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from pneumo_solver_ui.anim_export_contract import (
    render_anim_export_contract_validation_md,
    validate_anim_export_contract_meta,
)


def _load_meta(path: Path) -> Mapping[str, Any]:
    if path.suffix.lower() == ".json":
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, dict):
            meta = obj.get("meta")
            if isinstance(meta, dict):
                return meta
        raise ValueError(f"JSON does not contain top-level meta dict: {path}")
    if path.suffix.lower() == ".npz":
        with np.load(path, allow_pickle=True) as npz:
            if "meta_json" not in npz:
                raise ValueError(f"NPZ does not contain meta_json: {path}")
            raw = npz["meta_json"].tolist()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            if not isinstance(raw, str):
                raw = str(raw)
            meta = json.loads(raw)
            if not isinstance(meta, dict):
                raise ValueError(f"meta_json is not a dict: {path}")
            return meta
    raise ValueError(f"Unsupported input format: {path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="anim_latest.json or anim_latest.npz")
    ap.add_argument("--report-json")
    ap.add_argument("--report-md")
    args = ap.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    meta = _load_meta(input_path)
    report = validate_anim_export_contract_meta(meta)
    if args.report_json:
        Path(args.report_json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.report_md:
        Path(args.report_md).write_text(render_anim_export_contract_validation_md(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if str(report.get("level") or "") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
