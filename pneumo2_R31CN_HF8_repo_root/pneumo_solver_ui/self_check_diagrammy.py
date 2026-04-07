# -*- coding: utf-8 -*-
"""self_check_diagrammy.py

Автономная самопроверка "Диаграммы" (Compare NPZ: Web+Qt общий слой).

Зачем:
- Проверить, что compare_ui.py (baseline / units / locked scales / Δ-матрицы)
  работает на синтетическом наборе данных и не зависит от Streamlit/Qt.
- Это быстрый smoke-test, чтобы ловить регрессии при изменениях UI/экспорта NPZ.

Запуск:
    python self_check_diagrammy.py

Выход:
    0  - OK
    !=0 - ошибка
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


def _make_synth_npz(path: Path) -> None:
    """Создать минимальный NPZ, похожий на export format."""
    t = np.linspace(0.0, 1.0, 101)

    # В t=0 есть ненулевое смещение штока — baseline(t0) должен его убрать.
    road = 0.0 * t
    stroke = 0.10 + 0.01 * np.sin(2 * math.pi * t)  # m
    pressure_gauge = 1.0 + 0.2 * np.sin(2 * math.pi * t)  # bar
    angle = 0.05 * np.sin(2 * math.pi * t)  # rad

    cols = np.array(["t", "road_m", "stroke_m", "P_bar", "phi_rad"], dtype=object)
    values = np.vstack([t, road, stroke, pressure_gauge, angle]).T

    meta = {
        "export_version": "synth",
        "note": "self_check_diagrammy synthetic bundle",
        "params": {"k": 1.0},
        "metrics": {"dummy": 1.0},
    }

    np.savez(
        path,
        meta_json=json.dumps(meta, ensure_ascii=False),
        main_cols=cols,
        main_values=values,
    )


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)



def _test_trust_and_deltat_cube() -> None:
    # Проверка новых слоев: trust-banner + Δ(t) cube builder.
    import numpy as _np
    import pandas as _pd

    from pneumo_solver_ui.compare_trust import inspect_bundle
    from pneumo_solver_ui.compare_deltat_heatmap import build_deltat_cube

    t = _np.linspace(0.0, 1.0, 11)
    df1 = _pd.DataFrame({"t": t, "a": _np.sin(t), "b": t})
    df2 = _pd.DataFrame({"t": t, "a": _np.sin(t) + 1.0, "b": t * 2.0})

    b1 = {"tables": {"main": df1}, "meta": {"name": "r1"}}
    b2 = {"tables": {"main": df2}, "meta": {"name": "r2"}}

    issues_ok = inspect_bundle(b1, run_label="r1", table="main", signals=["a", "b"])
    assert issues_ok == []

    # delta cube
    cube = build_deltat_cube(
        [("r1", b1), ("r2", b2)],
        table="main",
        sigs=["a", "b"],
        ref_label="r1",
        mode="delta",
        max_time_points=2000,
    )
    assert cube.cube.shape[1] == 2  # signals
    assert cube.cube.shape[2] == 2  # runs

    # at t=0: a2-a1 ~ 1, b2-b1 = 0
    a_delta0 = float(cube.cube[0, 0, 1])
    b_delta0 = float(cube.cube[0, 1, 1])
    assert abs(a_delta0 - 1.0) < 1e-6
    assert abs(b_delta0 - 0.0) < 1e-9

    # trust: non-monotonic time + NaN
    df_bad = df1.copy()
    df_bad.loc[5, "t"] = df_bad.loc[4, "t"] - 0.1  # make dt<=0
    df_bad.loc[3, "a"] = _np.nan
    b_bad = {"tables": {"main": df_bad}, "meta": {"name": "bad"}}
    issues_bad = inspect_bundle(b_bad, run_label="bad", table="main", signals=["a", "b"])
    assert any(getattr(i, "code", "") == "time_nonmonotonic" for i in issues_bad)
    assert any(getattr(i, "code", "") == "nan_inf" for i in issues_bad)




def _test_influence_utils() -> None:
    # Проверяем общий слой compare_influence (Web+Qt).
    try:
        from compare_influence import flatten_meta_numeric, corr_matrix
    except Exception:
        from pneumo_solver_ui.compare_influence import flatten_meta_numeric, corr_matrix  # type: ignore

    meta = {"a": 1.0, "b": {"c": 2.0, "d": "skip"}, "e": None}
    flat = flatten_meta_numeric(meta)
    assert flat.get("a") == 1.0
    assert flat.get("b.c") == 2.0
    assert "b.d" not in flat

    # X perfectly correlates with Y
    X = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]], dtype=float)  # runs×features
    Y = np.array([[0.0], [2.0], [4.0]], dtype=float)  # runs×targets
    C = corr_matrix(X, Y, min_n=3)
    assert C.shape == (2, 1)
    assert abs(float(C[0, 0]) - 1.0) < 1e-12
    assert abs(float(C[1, 0]) - 1.0) < 1e-12

def run() -> int:
    # Import here to keep this script independent of streamlit/qt
    _test_trust_and_deltat_cube()
    _test_influence_utils()

    try:
        from compare_ui import (
            load_npz_bundle,
            get_xy,
            compute_locked_ranges,
            delta_run_signal_maxabs,
            P_ATM_DEFAULT,
        )
    except Exception:
        from pneumo_solver_ui.compare_ui import (  # type: ignore
            load_npz_bundle,
            get_xy,
            compute_locked_ranges,
            delta_run_signal_maxabs,
            P_ATM_DEFAULT,
        )

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        f1 = td / "runA.npz"
        f2 = td / "runB.npz"
        _make_synth_npz(f1)
        _make_synth_npz(f2)

        # modify second run a bit
        npz = np.load(f2, allow_pickle=True)
        cols = npz["main_cols"]
        vals = npz["main_values"].copy()
        # perturb stroke
        t = vals[:, 0]
        vals[:, 2] += 0.005 * np.sin(2 * math.pi * t)
        meta = json.loads(npz["meta_json"].tolist())
        meta["params"]["k"] = 2.0
        np.savez(
            f2,
            meta_json=json.dumps(meta, ensure_ascii=False),
            main_cols=cols,
            main_values=vals,
        )

        b1 = load_npz_bundle(f1)
        b2 = load_npz_bundle(f2)

        _assert("main" in b1 and isinstance(b1["main"], pd.DataFrame), "bundle['main'] должен быть DataFrame")
        _assert(len(b1["main"]) == 101, "ожидаем 101 точку по времени")

        # get_xy should return baseline-zeroed for stroke (позиционная величина)
        t, y, unit = get_xy(
            b1,
            "main",
            "stroke_m",
            dist_unit="m",
            angle_unit="rad",
            P_ATM=P_ATM_DEFAULT,
            baseline_mode="t0",
            baseline_window_s=0.0,
            baseline_first_n=0,
            zero_positions=True,
        )
        _assert(unit in {"m", "mm"}, f"ожидаем unit для stroke: m/mm, got {unit!r}")
        _assert(len(t) == len(y) == 101, "t/y длины должны совпадать")
        _assert(abs(float(y[0])) < 1e-12, "baseline(t0) должен обнулять первый элемент")

        # locked ranges should be finite
        _, y2, _ = get_xy(
            b2,
            "main",
            "stroke_m",
            dist_unit="m",
            angle_unit="rad",
            P_ATM=P_ATM_DEFAULT,
            baseline_mode="t0",
            baseline_window_s=0.0,
            baseline_first_n=0,
            zero_positions=True,
        )
        series_by_sig = {"stroke_m": [y, y2]}
        unit_by_sig = {"stroke_m": unit}
        rngs = compute_locked_ranges(series_by_sig, unit_by_sig, lock_mode="by_signal", robust=True, sym_zero=False)
        _assert("stroke_m" in rngs, "range spec должен содержать stroke_m")
        rs = rngs["stroke_m"]
        _assert(np.isfinite(rs.lo) and np.isfinite(rs.hi), "lo/hi должны быть finite")
        _assert(rs.hi > rs.lo, "hi должно быть > lo")

        # delta matrix should detect diff between runB and runA
        runs = [("A", b1), ("B", b2)]
        df = delta_run_signal_maxabs(
            runs,
            table="main",
            sigs=["stroke_m"],
            ref_label="A",
            dist_unit="m",
            angle_unit="rad",
            P_ATM=P_ATM_DEFAULT,
            BAR_PA=100000.0,
            baseline_mode="t0",
            baseline_window_s=0.0,
            baseline_first_n=0,
            zero_positions=True,
            flow_unit="raw",
        )
        _assert(df.shape == (2, 1), f"ожидаем 2x1 матрицу, got {df.shape}")
        _assert(float(df.loc["B", "stroke_m"]) > 0.0, "Δ для B должен быть >0 (есть смещение)")

    print("[Diagrammy] self_check_diagrammy: OK")
    return 0


def main() -> int:
    try:
        return int(run())
    except Exception as e:
        print("[Diagrammy] self_check_diagrammy: FAIL:", repr(e))
        return 90


if __name__ == "__main__":
    raise SystemExit(main())
