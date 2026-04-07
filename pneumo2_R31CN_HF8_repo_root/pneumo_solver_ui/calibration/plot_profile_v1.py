# -*- coding: utf-8 -*-
"""
plot_profile_v1.py

Построение графиков profile likelihood из profile_report.json, который пишет
profile_worker_v1_likelihood.py.

Выход:
- profile_plots/profile_<param>.png
- profile_plots/profile_index.csv

Зависимости: pandas, numpy, matplotlib

Пример:
python calibration/plot_profile_v1.py --profile_json profile_report.json --out_dir profile_plots

"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd


def _load_json(p: Path) -> Any:
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def slugify(text: str, max_len: int = 96) -> str:
    t = str(text).strip().replace("\\", "_").replace("/", "_")
    t = re.sub(r"\s+", "_", t)
    t2 = re.sub(r"[^0-9A-Za-z_\-]+", "_", t)
    t2 = re.sub(r"_+", "_", t2).strip("_")
    if not t2:
        import hashlib
        t2 = hashlib.sha1(t.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return t2[:max_len]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile_json", required=True)
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()

    try:
        import matplotlib.pyplot as plt  # noqa: F401
    except Exception as e:
        raise SystemExit("matplotlib не установлен. Установите: pip install matplotlib") from e

    import matplotlib.pyplot as plt

    prof = _load_json(Path(args.profile_json))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sse0 = float(prof.get("sse_star", float("nan")))
    sigma2 = float(prof.get("sigma2_hat", float("nan")))
    thr95 = float(prof.get("chi2_thr_95", 3.84))
    thr68 = float(prof.get("chi2_thr_68", 1.0))

    rows_index: List[Dict[str, Any]] = []

    profiles = prof.get("profiles", {})
    if not isinstance(profiles, dict) or not profiles:
        raise SystemExit("В profile_json нет профилей (profiles пусто).")

    for pname, pdata in profiles.items():
        rows = pdata.get("rows", [])
        if not rows:
            continue
        vals = np.array([float(r.get("fixed_value")) for r in rows], dtype=float)
        sses = np.array([float(r.get("sse")) for r in rows], dtype=float)
        if math.isfinite(sigma2) and sigma2 > 0:
            dchi2 = (sses - sse0) / sigma2
            ylab = "Δχ² ≈ (SSE - SSE*) / σ²"
            y = dchi2
            h1, h2 = thr68, thr95
            h1lab, h2lab = "68%", "95%"
        else:
            y = sses - sse0
            ylab = "ΔSSE = SSE - SSE*"
            h1, h2 = float(prof.get("delta_sse_thr_68", float("nan"))), float(prof.get("delta_sse_thr_95", float("nan")))
            h1lab, h2lab = "68%", "95%"

        slug = slugify(pname)
        png = out_dir / f"profile_{slug}.png"

        plt.figure()
        plt.plot(vals, y, marker="o", linewidth=1)
        if math.isfinite(h1):
            plt.axhline(h1, linestyle="--", linewidth=1)
            plt.text(vals.min(), h1, f" {h1lab}", va="bottom")
        if math.isfinite(h2):
            plt.axhline(h2, linestyle="--", linewidth=1)
            plt.text(vals.min(), h2, f" {h2lab}", va="bottom")
        plt.xlabel(pname)
        plt.ylabel(ylab)
        plt.title(f"Profile: {pname}")
        plt.tight_layout()
        plt.savefig(png, dpi=150)
        plt.close()

        ci95 = pdata.get("ci_95", [None, None])
        ci68 = pdata.get("ci_68", [None, None])
        rows_index.append({
            "param": pname,
            "theta_star": pdata.get("theta_star"),
            "ci_68_lo": ci68[0] if isinstance(ci68, list) else None,
            "ci_68_hi": ci68[1] if isinstance(ci68, list) else None,
            "ci_95_lo": ci95[0] if isinstance(ci95, list) else None,
            "ci_95_hi": ci95[1] if isinstance(ci95, list) else None,
            "plot_png": str(png.name),
        })

    df = pd.DataFrame(rows_index)
    df.to_csv(out_dir / "profile_index.csv", index=False, encoding="utf-8-sig")
    print("Wrote:", out_dir)


if __name__ == "__main__":
    main()
