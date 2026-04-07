from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def write_tests_index_csv(osc_dir: Path, tests: list[dict[str, Any]], *, filename: str = "tests_index.csv") -> Path:
    """Генерирует tests_index.csv рядом с NPZ для пайплайнов калибровки."""
    osc_dir = Path(osc_dir)
    osc_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, t in enumerate(tests, start=1):
        name = str(t.get("name", f"T{i:02d}"))
        rows.append({"test_num": int(i), "имя_теста": name, "npz_file": f"T{i:02d}_osc.npz"})
    df = pd.DataFrame(rows)
    out = osc_dir / filename
    try:
        out.write_text(df.to_csv(index=False), encoding="utf-8-sig")
    except Exception:
        df.to_csv(out, index=False)
    return out


def downsample_df(df: pd.DataFrame, max_points: int = 1200) -> pd.DataFrame:
    """Уменьшает число точек для графиков/анимации (чтобы не тормозить UI)."""
    if df is None or len(df) <= max_points:
        return df
    idx = np.linspace(0, len(df) - 1, num=max_points, dtype=int)
    return df.iloc[idx].reset_index(drop=True)


def decimate_minmax(x: np.ndarray, y: np.ndarray, max_points: int = 2000) -> tuple[np.ndarray, np.ndarray]:
    """Min-max decimation to preserve spikes (keeps <= max_points points)."""
    try:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
    except Exception:
        return (x, y)
    n = int(len(x))
    if n <= 0 or n <= int(max_points):
        return (x, y)
    bins = max(2, int(max_points) // 2)
    step = n / float(bins)
    ox = []
    oy = []
    ox.append(float(x[0]))
    oy.append(float(y[0]) if np.isfinite(y[0]) else float("nan"))
    for bi in range(bins):
        a = int(bi * step)
        b = int((bi + 1) * step)
        if b <= a:
            continue
        if a < 0:
            a = 0
        if b > n:
            b = n
        ys = y[a:b]
        if ys.size <= 0:
            continue
        if not np.isfinite(ys).any():
            continue
        i_min = int(np.nanargmin(ys))
        i_max = int(np.nanargmax(ys))
        j1 = a + min(i_min, i_max)
        j2 = a + max(i_min, i_max)
        ox.append(float(x[j1]))
        oy.append(float(y[j1]))
        if j2 != j1:
            ox.append(float(x[j2]))
            oy.append(float(y[j2]))
    ox.append(float(x[-1]))
    oy.append(float(y[-1]) if np.isfinite(y[-1]) else float("nan"))
    return (np.asarray(ox, dtype=float), np.asarray(oy, dtype=float))


__all__ = [
    "decimate_minmax",
    "downsample_df",
    "write_tests_index_csv",
]
