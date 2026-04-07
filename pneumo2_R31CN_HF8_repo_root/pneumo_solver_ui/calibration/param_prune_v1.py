# -*- coding: utf-8 -*-
"""
param_prune_v1.py

Automatic "active set" parameter pruning for nonlinear least-squares calibration.

Idea (engineering):
- Many-parameter fits on dynamic / hybrid (piecewise) models are often practically non-identifiable:
  some parameters are weakly observable, and others are strongly correlated, which makes NLLS unstable
  and slows down convergence.
- We can use local linear diagnostics from the already computed Jacobian / Gauss-Newton covariance:
    * column norms of J (sensitivity proxy),
    * parameter relative std from cov diag (uncertainty proxy),
    * corr matrix (dependency proxy),
  to select a smaller subset of "identifiable + informative" parameters for the final refinement.
- This is not a proof of identifiability, but a robust automation heuristic.

Inputs:
- fit_report.json from fit_worker_v3_suite_identify.py (must contain keys, x, cov/corr optional,
  and preferably jac_col_rms_unb / jac_col_norm_unb).
- fit_ranges.json with candidate parameter bounds.

Outputs:
- pruned fit_ranges json with selected params only.
- prune_report json with decisions + metrics.
- prune markdown summary for human reading.

Usage:
python calibration/param_prune_v1.py --fit_report_json ... --fit_ranges_json default_ranges.json \
    --out_ranges_json fit_ranges_pruned.json --out_report_json prune_report.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(obj: Any, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _save_text(txt: str, p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(txt)


def _parse_list(s: str) -> List[str]:
    s = (s or "").strip()
    if not s:
        return []
    parts = []
    for chunk in s.replace(";", ",").split(","):
        t = chunk.strip()
        if t:
            parts.append(t)
    return parts


def _safe_float(x: Any, default: float = float("nan")) -> float:
    try:
        v = float(x)
        return v
    except Exception:
        return default


def _format_num(x: float) -> str:
    if not math.isfinite(x):
        return "nan"
    ax = abs(x)
    if ax != 0.0 and (ax < 1e-4 or ax > 1e5):
        return f"{x:.3e}"
    return f"{x:.6g}"


def _markdown_table(rows: List[List[str]], header: List[str]) -> str:
    # simple pipe table
    out = []
    out.append("| " + " | ".join(header) + " |")
    out.append("|" + "|".join(["---"] * len(header)) + "|")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit_report_json", required=True)
    ap.add_argument("--fit_ranges_json", required=True)
    ap.add_argument("--out_ranges_json", required=True)
    ap.add_argument("--out_report_json", required=True)
    ap.add_argument("--out_md", default="")
    ap.add_argument("--max_params", type=int, default=12)
    ap.add_argument("--min_keep", type=int, default=4)
    ap.add_argument("--corr_thr", type=float, default=0.98)
    ap.add_argument("--min_col_norm_frac", type=float, default=0.02,
                    help="Drop if jac_col_norm < frac * max_col_norm (unless forced keep).")
    ap.add_argument("--max_rel_std", type=float, default=10.0,
                    help="Drop if relative std is above this threshold (unless forced keep).")
    ap.add_argument("--keep", default="", help="Comma-separated list of params to always keep.")
    ap.add_argument("--prefer", default="", help="Comma-separated list of params to prefer (tie-break).")

    args = ap.parse_args()

    fit_report_path = Path(args.fit_report_json)
    fit_ranges_path = Path(args.fit_ranges_json)
    out_ranges_path = Path(args.out_ranges_json)
    out_report_path = Path(args.out_report_json)
    out_md_path = Path(args.out_md) if str(args.out_md).strip() else (out_report_path.parent / "param_prune.md")

    report = _load_json(fit_report_path)
    ranges = _load_json(fit_ranges_path)

    keys: List[str] = [str(k) for k in report.get("keys", [])]
    x: List[float] = [float(v) for v in report.get("x", [])]
    n = len(keys)
    if n == 0:
        raise RuntimeError("fit_report has empty keys")

    # jac norms (prefer unbiased RMS)
    jac_rms_unb = report.get("jac_col_rms_unb", None)
    jac_norm_unb = report.get("jac_col_norm_unb", None)

    col = [0.0] * n
    if isinstance(jac_rms_unb, dict):
        for i, k in enumerate(keys):
            col[i] = float(_safe_float(jac_rms_unb.get(k, 0.0), 0.0))
    elif isinstance(jac_norm_unb, dict):
        # fallback: use norms but normalize by sqrt(m) is unknown; still usable for ranking
        for i, k in enumerate(keys):
            col[i] = float(_safe_float(jac_norm_unb.get(k, 0.0), 0.0))

    max_col = max(col) if col else 0.0
    if not math.isfinite(max_col) or max_col <= 0.0:
        # no jac norms available -> keep all
        selected = [k for k in keys if k in ranges]
        out_ranges = {k: ranges[k] for k in selected}
        _save_json(out_ranges, out_ranges_path)
        _save_json({
            "status": "skipped_no_jac_norms",
            "selected": selected,
            "dropped": [],
        }, out_report_path)
        _save_text("# Param prune: skipped (no Jacobian norms in fit_report)\n", out_md_path)
        return

    # cov/corr -> std/rel_std
    cov = report.get("cov", None)
    corr = report.get("corr", None)

    std = [float("nan")] * n
    rel_std = [float("nan")] * n
    if isinstance(cov, list):
        try:
            # diag
            for i in range(n):
                v = float(_safe_float(cov[i][i], float("nan")))
                if math.isfinite(v) and v >= 0.0:
                    std[i] = math.sqrt(max(0.0, v))
        except Exception:
            pass

    # range widths for rel scale
    width = [float("nan")] * n
    for i, k in enumerate(keys):
        if k in ranges and isinstance(ranges[k], list) and len(ranges[k]) == 2:
            lo = float(_safe_float(ranges[k][0], float("nan")))
            hi = float(_safe_float(ranges[k][1], float("nan")))
            if math.isfinite(lo) and math.isfinite(hi):
                width[i] = abs(hi - lo)

    for i in range(n):
        if not math.isfinite(std[i]):
            continue
        denom = abs(x[i]) if i < len(x) else 0.0
        w = width[i]
        if math.isfinite(w) and w > 0.0:
            denom = max(denom, 0.1 * w)
        denom = max(denom, 1e-12)
        rel_std[i] = std[i] / denom

    # corr matrix
    corr_abs: Optional[List[List[float]]] = None
    if isinstance(corr, list) and len(corr) == n:
        try:
            corr_abs = [[0.0] * n for _ in range(n)]
            for i in range(n):
                row = corr[i]
                for j in range(n):
                    corr_abs[i][j] = abs(float(_safe_float(row[j], 0.0)))
        except Exception:
            corr_abs = None

    keep_forced = set([k for k in _parse_list(args.keep) if k in keys])
    prefer = set([k for k in _parse_list(args.prefer) if k in keys])

    # score: high sensitivity, low uncertainty
    score = [0.0] * n
    for i in range(n):
        sens = col[i] / max_col
        rs = rel_std[i]
        if not math.isfinite(rs):
            rs = 0.0
        score[i] = float(sens / (1.0 + rs))

    # tie-break: prefer list
    idx_sorted = sorted(range(n), key=lambda i: (score[i], 1.0 if keys[i] in prefer else 0.0), reverse=True)

    max_params = max(1, int(args.max_params))
    min_keep = max(1, int(args.min_keep))
    corr_thr = float(args.corr_thr)
    min_col_thr = float(args.min_col_norm_frac) * float(max_col)
    max_rel_std = float(args.max_rel_std)

    selected: List[str] = []
    reasons: Dict[str, str] = {}
    metrics: Dict[str, Dict[str, Any]] = {}

    # forced keep first (stable order)
    for k in keys:
        if k in keep_forced and k in ranges:
            selected.append(k)
            reasons[k] = "keep_forced"

    # greedy select
    for i in idx_sorted:
        k = keys[i]
        if k not in ranges:
            reasons[k] = "drop_not_in_ranges"
            continue
        if k in selected:
            continue
        if len(selected) >= max_params:
            reasons[k] = "drop_max_params"
            continue

        # filters (unless forced)
        if col[i] < min_col_thr and k not in keep_forced:
            reasons[k] = f"drop_low_sens(col<{_format_num(min_col_thr)})"
            continue

        rs = rel_std[i]
        if math.isfinite(rs) and rs > max_rel_std and k not in keep_forced:
            reasons[k] = f"drop_high_rel_std(>{_format_num(max_rel_std)})"
            continue

        # correlation filter
        if corr_abs is not None and selected and k not in keep_forced:
            worst = (0.0, "")
            ii = i
            for kk in selected:
                jj = keys.index(kk)
                c = corr_abs[ii][jj]
                if c > worst[0]:
                    worst = (c, kk)
            if worst[0] >= corr_thr:
                reasons[k] = f"drop_high_corr(|corr|={_format_num(worst[0])} with {worst[1]})"
                continue

        selected.append(k)
        reasons[k] = "keep_greedy"

    # ensure min_keep
    if len(selected) < min_keep:
        for i in idx_sorted:
            k = keys[i]
            if k not in ranges or k in selected:
                continue
            selected.append(k)
            reasons[k] = "keep_to_reach_min_keep"
            if len(selected) >= min_keep:
                break

    # build metrics per param for report
    for i, k in enumerate(keys):
        metrics[k] = {
            "score": float(score[i]),
            "jac_col": float(col[i]),
            "jac_col_rel": float(col[i] / max_col) if max_col > 0 else 0.0,
            "std": float(std[i]) if math.isfinite(std[i]) else None,
            "rel_std": float(rel_std[i]) if math.isfinite(rel_std[i]) else None,
        }

    dropped = [k for k in keys if (k in ranges and k not in selected)]
    out_ranges = {k: ranges[k] for k in selected}

    prune_report = {
        "meta": {
            "fit_report_json": str(fit_report_path),
            "fit_ranges_json": str(fit_ranges_path),
            "n_total": int(len([k for k in keys if k in ranges])),
            "n_selected": int(len(selected)),
            "n_dropped": int(len(dropped)),
            "max_params": int(max_params),
            "min_keep": int(min_keep),
            "corr_thr": float(corr_thr),
            "min_col_norm_frac": float(args.min_col_norm_frac),
            "max_rel_std": float(max_rel_std),
            "keep_forced": sorted(list(keep_forced)),
            "prefer": sorted(list(prefer)),
        },
        "selected": selected,
        "dropped": dropped,
        "reasons": reasons,
        "metrics": metrics,
    }

    _save_json(out_ranges, out_ranges_path)
    _save_json(prune_report, out_report_path)

    # markdown summary
    rows = []
    for k in selected:
        m = metrics.get(k, {})
        rows.append([
            k,
            reasons.get(k, "keep"),
            _format_num(_safe_float(m.get("score", float("nan")))),
            _format_num(_safe_float(m.get("jac_col_rel", float("nan")))),
            _format_num(_safe_float(m.get("rel_std", float("nan")))),
        ])
    rows_drop = []
    for k in dropped:
        m = metrics.get(k, {})
        rows_drop.append([
            k,
            reasons.get(k, "drop"),
            _format_num(_safe_float(m.get("score", float("nan")))),
            _format_num(_safe_float(m.get("jac_col_rel", float("nan")))),
            _format_num(_safe_float(m.get("rel_std", float("nan")))),
        ])

    md = []
    md.append("# Param prune (active set) — summary\n")
    md.append("## Selected parameters\n")
    md.append(_markdown_table(rows, header=["param", "reason", "score", "sens_rel", "rel_std"]))
    md.append("\n\n## Dropped parameters\n")
    if rows_drop:
        md.append(_markdown_table(rows_drop, header=["param", "reason", "score", "sens_rel", "rel_std"]))
    else:
        md.append("(none)\n")

    md.append("\n\n## Notes\n")
    md.append("- `sens_rel` is Jacobian column norm normalized by max (unbiased by group gains if available).\n")
    md.append("- `rel_std` is a local uncertainty proxy from Gauss-Newton covariance diag, scaled by max(|x|, 0.1*range_width).\n")
    md.append("- Correlation filter uses |corr| from covariance (if available).\n")

    _save_text("\n".join(md), out_md_path)


if __name__ == "__main__":
    main()
