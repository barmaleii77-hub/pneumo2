#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""opt_warmstart_init.py

Small helper to initialize CEM state (mu/cov) for **single-stage** optimization runs.

Why:
- The staged runner already creates warm-start CEM state from the global archive.
- If the user disables staged optimization in the UI, the worker previously started
  from scratch unless a *_cem_state.json was already present.

This script creates that *_cem_state.json once, using the same warm-start logic
as StageRunner (surrogate or archive). If the state file already exists, it does nothing.

It is safe to call every time before launching opt_worker_v3_margins_energy.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _find_workspace_dir(p: Path) -> Path:
    cur = p.resolve()
    for _ in range(8):
        if cur.name.lower() == "workspace":
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    # fallback: sibling workspace
    cand = p.resolve().parent / "workspace"
    return cand


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out_csv", required=True)
    ap.add_argument("--base_json", required=True)
    ap.add_argument("--ranges_json", required=True)
    ap.add_argument("--warmstart_mode", choices=["surrogate", "archive", "none"], default="surrogate")
    ap.add_argument("--surrogate_samples", type=int, default=8000)
    ap.add_argument("--surrogate_top_k", type=int, default=64)
    ap.add_argument("--min_coverage", type=float, default=0.55)

    args = ap.parse_args(argv)

    # Import StageRunner functions (single source of truth)
    try:
        import opt_stage_runner_v1 as runner
    except Exception as e:
        print(f"[warmstart_init] Cannot import opt_stage_runner_v1: {e}", file=sys.stderr)
        return 2

    model_path = Path(args.model)
    out_csv = Path(args.out_csv)
    base_json = Path(args.base_json)
    ranges_json = Path(args.ranges_json)

    cem_state_path = Path(str(out_csv).replace(".csv", "") + "_cem_state.json")
    if cem_state_path.exists() and cem_state_path.stat().st_size > 10:
        # already initialized
        return 0

    try:
        base_params = runner.load_json(base_json)
        ranges_src = runner.load_json(ranges_json)
        if not isinstance(ranges_src, dict):
            raise ValueError("ranges_json must be a dict")
    except Exception as e:
        print(f"[warmstart_init] Cannot read base/ranges json: {e}", file=sys.stderr)
        return 2

    ws_dir = _find_workspace_dir(out_csv)
    archive_path = ws_dir / "opt_archive" / "global_history.jsonl"
    if not archive_path.exists():
        return 0

    # Try warm-start
    mode = str(args.warmstart_mode)
    if mode == "none":
        return 0

    model_sha = runner._file_sha1(model_path)[:12] if model_path.exists() else ""

    ok = False
    if mode == "archive":
        ok = runner.make_initial_cem_state_from_archive(
            cem_state_path,
            archive_path,
            {k: (float(v[0]), float(v[1])) for k, v in ranges_src.items() if isinstance(v, (list, tuple)) and len(v) == 2},
            base_params,
            top_k=int(args.surrogate_top_k),
            min_coverage=float(args.min_coverage),
            prefer_model_sha_prefix=model_sha,
            prefer_problem_hash="",
        )
    elif mode == "surrogate":
        ok = runner.make_initial_cem_state_from_surrogate(
            cem_state_path,
            archive_path,
            {k: (float(v[0]), float(v[1])) for k, v in ranges_src.items() if isinstance(v, (list, tuple)) and len(v) == 2},
            base_params,
            n_samples=int(args.surrogate_samples),
            top_k=int(args.surrogate_top_k),
            min_coverage=float(args.min_coverage),
            model_sha_prefix=model_sha,
            prefer_problem_hash="",
        )

    return 0 if ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
