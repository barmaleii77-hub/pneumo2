from __future__ import annotations

from typing import Any

import numpy as np


def prepare_svg_animation_series(
    *,
    df_mdot,
    selected_edges: list[str],
    scale: float,
    unit: str,
    mapping: Any,
    df_open=None,
    df_p=None,
    selected_nodes: list[str] | None = None,
    p_atm: float,
    pressure_divisor: float,
    pressure_unit: str,
) -> dict[str, Any]:
    time_s = df_mdot["время_с"].astype(float).tolist()

    edge_series: list[dict[str, Any]] = []
    missing_edges: list[str] = []
    for edge_name in selected_edges:
        q = (df_mdot[edge_name].astype(float).to_numpy() * scale).tolist()
        if df_open is not None and edge_name in df_open.columns:
            open_state = df_open[edge_name].astype(int).tolist()
        else:
            open_state = None
        edge_series.append({"name": edge_name, "q": q, "open": open_state, "unit": unit})

        try:
            if not mapping.get("edges", {}).get(edge_name):
                missing_edges.append(edge_name)
        except Exception:
            pass

    node_series: list[dict[str, Any]] = []
    missing_nodes: list[str] = []
    if df_p is not None and selected_nodes:
        try:
            target_time = np.array(time_s, dtype=float)
            source_time = df_p["время_с"].astype(float).to_numpy()
        except Exception:
            target_time = None
            source_time = None

        for node_name in selected_nodes:
            if node_name not in df_p.columns:
                continue
            source_pressure = df_p[node_name].astype(float).to_numpy()
            gauge_pressure = (source_pressure - p_atm) / pressure_divisor
            if target_time is not None and source_time is not None and len(source_time) >= 2 and len(target_time) >= 2:
                if (
                    len(source_time) != len(target_time)
                    or (abs(float(source_time[0]) - float(target_time[0])) > 1e-9)
                    or (abs(float(source_time[-1]) - float(target_time[-1])) > 1e-9)
                ):
                    try:
                        gauge_pressure = np.interp(target_time, source_time, gauge_pressure)
                    except Exception:
                        gauge_pressure = gauge_pressure[: len(target_time)]
            else:
                gauge_pressure = gauge_pressure[: len(time_s)]

            node_series.append({"name": node_name, "p": gauge_pressure.tolist(), "unit": pressure_unit})

            try:
                xy = mapping.get("nodes", {}).get(node_name)
                if not (isinstance(xy, list) and len(xy) >= 2):
                    missing_nodes.append(node_name)
            except Exception:
                pass

    return {
        "time_s": time_s,
        "edge_series": edge_series,
        "missing_edges": missing_edges,
        "node_series": node_series,
        "missing_nodes": missing_nodes,
    }
