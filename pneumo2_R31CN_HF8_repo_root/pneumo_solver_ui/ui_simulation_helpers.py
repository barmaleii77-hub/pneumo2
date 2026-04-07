from __future__ import annotations

import copy
import inspect
from typing import Any

import numpy as np
import pandas as pd

try:
    import streamlit as st
except Exception:
    st = None  # type: ignore


def _emit_ui_log_event(event: str, **fields: Any) -> None:
    try:
        cb = getattr(getattr(st, "session_state", {}), "get", lambda *_args, **_kwargs: None)("_log_event_cb")
        if callable(cb):
            cb(event, **fields)
    except Exception:
        return


def call_simulate(
    model_mod: Any,
    params: dict,
    test: dict,
    *,
    dt: float | None = None,
    t_end: float | None = None,
    record_full: bool = False,
    **kwargs: Any,
) -> Any:
    """Совместимый вызов model.simulate() для разных версий модели."""
    sim = getattr(model_mod, "simulate", None)
    if sim is None:
        raise AttributeError("model_mod has no simulate()")
    if dt is None:
        dt = (test or {}).get("dt") or (params or {}).get("dt")
    if t_end is None:
        t_end = (test or {}).get("t_end") or (test or {}).get("t_end_s") or (params or {}).get("t_end")
    try:
        dt = float(dt) if dt is not None else 0.01
    except Exception:
        dt = 0.01
    try:
        t_end = float(t_end) if t_end is not None else 1.0
    except Exception:
        t_end = 1.0

    params = copy.deepcopy(params)
    test = copy.deepcopy(test)
    ts_compile_error = ""
    try:
        from pneumo_solver_ui import opt_worker_v3_margins_energy as _tsw

        if isinstance(test, dict) and (str(test.get("road_csv") or "").strip() or str(test.get("axay_csv") or "").strip()):
            test = _tsw._compile_timeseries_inputs(test)
            if callable(test.get("road_dfunc")) and (not callable(test.get("road_func_dot"))):
                test["road_func_dot"] = test.get("road_dfunc")
    except Exception as e:
        ts_compile_error = (f"{type(e).__name__}: {e}")[:300]
        _emit_ui_log_event("timeseries_compile_error", error=ts_compile_error)
        if bool((test or {}).get("timeseries_strict", True)):
            raise RuntimeError("Time-series input compile failed: " + ts_compile_error) from e

    base_kwargs = dict(params=params, test=test, dt=float(dt), t_end=float(t_end), record_full=bool(record_full))
    extra_kwargs = dict(kwargs or {})
    try:
        sig = inspect.signature(sim)
        allowed = set(sig.parameters.keys())
        call_kwargs = {k: v for k, v in {**base_kwargs, **extra_kwargs}.items() if k in allowed}
        dropped = sorted(set({**base_kwargs, **extra_kwargs}.keys()) - set(call_kwargs.keys()))
        if dropped:
            _emit_ui_log_event("call_simulate_dropped_kwargs", dropped=dropped)
        return sim(**call_kwargs)
    except TypeError:
        return sim(params, test, dt=float(dt), t_end=float(t_end), record_full=bool(record_full))
    except Exception:
        return sim(params, test, dt=float(dt), t_end=float(t_end), record_full=bool(record_full))


def compute_road_profile_from_suite(
    model_mod: Any,
    test_obj: dict[str, Any],
    time_s: list[float],
    wheelbase_m: float,
    track_m: float,
    corners: list[str],
) -> dict[str, list[float]] | None:
    """Road profile under each wheel corner from suite definition (input)."""
    try:
        if model_mod is None:
            return None
        compile_fn = getattr(model_mod, "_compile_suite_test_inputs", None)
        if not callable(compile_fn):
            return None
        params = {"база": float(wheelbase_m), "колея": float(track_m)}
        add = compile_fn(test_obj, params)
        road_func = add.get("road_func")
        if not callable(road_func):
            return None
        arr = np.asarray([road_func(float(t)) for t in time_s], dtype=float)
        if arr.ndim != 2 or arr.shape[1] != 4:
            return None
        out: dict[str, list[float]] = {}
        for i, c in enumerate(corners[:4]):
            out[c] = arr[:, i].astype(float).tolist()
        return out
    except Exception:
        return None


def parse_sim_output(out: Any, *, want_full: bool = False) -> dict[str, Any]:
    """Нормализует вывод model.simulate() в единый dict."""
    _ = want_full
    res: dict[str, Any] = {
        "df_main": None,
        "df_drossel": None,
        "df_energy_drossel": None,
        "nodes": None,
        "edges": None,
        "df_Eedges": None,
        "df_Egroups": None,
        "df_atm": None,
        "df_p": None,
        "df_mdot": None,
        "df_open": None,
    }
    if out is None:
        return res
    if isinstance(out, dict):
        res.update(out)
        if res.get("df_main") is None:
            res["df_main"] = out.get("main") or out.get("df")
        return res
    if not isinstance(out, (list, tuple)):
        res["raw"] = out
        return res

    n = len(out)
    try:
        if n > 0:
            res["df_main"] = out[0]
        if n > 1:
            res["df_drossel"] = out[1]
        if n > 2:
            res["df_energy_drossel"] = out[2]
        if n > 3:
            res["nodes"] = out[3]
        if n > 4:
            res["edges"] = out[4]
        if n > 5:
            res["df_Eedges"] = out[5]
        if n > 6:
            res["df_Egroups"] = out[6]
        if n > 7:
            res["df_atm"] = out[7]
        if n >= 11:
            res["df_p"] = out[8]
            res["df_mdot"] = out[9]
            res["df_open"] = out[10]
        if n >= 12 and isinstance(out[11], pd.DataFrame):
            res["df_Eedges"] = out[11]
        if n >= 13 and isinstance(out[12], pd.DataFrame):
            res["df_Egroups"] = out[12]
        if n >= 14 and isinstance(out[13], pd.DataFrame):
            res["df_atm"] = out[13]
    except Exception as e:
        _emit_ui_log_event("parse_sim_output_error", err=str(e), n=int(n))
        res["raw"] = out
    return res


__all__ = [
    "call_simulate",
    "compute_road_profile_from_suite",
    "parse_sim_output",
]
