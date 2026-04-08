from __future__ import annotations

from typing import Callable, List

import numpy as np
import pandas as pd


TIME_COL = "время_с"
CORNERS = ["ЛП", "ПП", "ЛЗ", "ПЗ"]


def align_frame_to_time_vector(
    df: pd.DataFrame,
    target_time_s: np.ndarray,
    *,
    time_col: str = TIME_COL,
) -> pd.DataFrame:
    t_src = df[time_col].to_numpy(dtype=float)
    order = np.argsort(t_src)
    t_src = t_src[order]
    df_sorted = df.iloc[order].reset_index(drop=True)

    if t_src.size == 0:
        return df_sorted.iloc[0:0].copy()
    if t_src.size == 1:
        idx_near = np.zeros_like(target_time_s, dtype=int)
    else:
        idx = np.searchsorted(t_src, target_time_s, side="left")
        idx = np.clip(idx, 1, t_src.size - 1)
        left = idx - 1
        right = idx
        choose_right = (t_src[right] - target_time_s) < (target_time_s - t_src[left])
        idx_near = np.where(choose_right, right, left)
    return df_sorted.iloc[idx_near].reset_index(drop=True)


def add_wheels_identical_sanity_event(
    *,
    df_main: pd.DataFrame,
    add_event_fn: Callable[[int, str, str, str, str], None],
) -> None:
    road_cols = [f"дорога_{corner}_м" for corner in CORNERS]
    wheel_cols = [f"перемещение_колеса_{corner}_м" for corner in CORNERS]
    if not all(col in df_main.columns for col in road_cols):
        return
    if not all(col in df_main.columns for col in wheel_cols):
        return

    road_mat = df_main[road_cols].to_numpy(dtype=float)
    wheel_mat = df_main[wheel_cols].to_numpy(dtype=float)
    road_span = np.ptp(road_mat, axis=1)
    wheel_span = np.ptp(wheel_mat, axis=1)

    if float(np.nanmax(road_span)) > 1e-4 and float(np.nanmax(wheel_span)) < 1e-5:
        idx0 = int(np.where(road_span > 1e-4)[0][0])
        add_event_fn(
            idx0,
            "warn",
            "sanity",
            "wheels_identical",
            "Санити: профиль дороги различается по колёсам, но ходы колёс почти одинаковы — проверьте road_func/графики/ключи колеи/базы.",
        )


def compute_events(
    df_main: pd.DataFrame | None,
    df_p: pd.DataFrame | None,
    df_open: pd.DataFrame | None,
    params_abs: dict,
    test: dict,
    vacuum_min_gauge: float = -0.2,
    pmax_margin_gauge: float = 0.10,
    chatter_window_s: float = 0.25,
    chatter_toggle_count: int = 6,
    max_events: int = 240,
    *,
    gauge_pressure_scale_pa: float,
    vacuum_unit_label: str,
    run_starts_fn: Callable[[np.ndarray], List[int]],
    shorten_name_fn: Callable[[str, int], str],
    align_pressure_df_to_main: bool = False,
    align_open_df_to_main: bool = False,
    use_nan_pressure_reducers: bool = False,
    extra_event_hook_fn: Callable[..., None] | None = None,
) -> List[dict]:
    events: List[dict] = []

    if df_main is None or TIME_COL not in df_main.columns or len(df_main) == 0:
        return events

    t_arr = df_main[TIME_COL].to_numpy(dtype=float)
    n = int(len(t_arr))
    if n <= 1:
        return events

    p_atm = float(params_abs.get("_P_ATM", 101325.0))

    def add_event(idx: int, severity: str, kind: str, name: str, label: str) -> None:
        idx_i = int(max(0, min(int(idx), n - 1)))
        events.append(
            {
                "id": f"{kind}:{name}:{idx_i}",
                "idx": idx_i,
                "t": float(t_arr[idx_i]),
                "severity": severity,
                "kind": kind,
                "name": name,
                "label": label,
            }
        )

    for corner in CORNERS:
        col = f"колесо_в_воздухе_{corner}"
        if col in df_main.columns:
            starts = run_starts_fn(df_main[col].to_numpy() != 0)
            for idx0 in starts:
                add_event(idx0, "warn", "wheel_lift", corner, f"Колесо {corner} в воздухе")

    if extra_event_hook_fn is not None:
        try:
            extra_event_hook_fn(df_main=df_main, add_event_fn=add_event)
        except Exception:
            pass

    stroke = float(params_abs.get("ход_штока", 0.25))
    margin = float(test.get("target_мин_запас_до_упора_штока_м", 0.005))
    margin = max(0.0, margin)
    for corner in CORNERS:
        col = f"положение_штока_{corner}_м"
        if col in df_main.columns:
            x = df_main[col].to_numpy(dtype=float)
            for idx0 in run_starts_fn(x <= margin):
                add_event(idx0, "warn", "stroke_limit", corner, f"Шток {corner}: близко к упору (min)")
            for idx0 in run_starts_fn(x >= (stroke - margin)):
                add_event(idx0, "warn", "stroke_limit", corner, f"Шток {corner}: близко к упору (max)")

    v_lim = float(test.get("target_лимит_скорости_штока_м_с", 2.0))
    if v_lim > 0:
        for corner in CORNERS:
            col = f"скорость_штока_{corner}_м_с"
            if col in df_main.columns:
                v = df_main[col].to_numpy(dtype=float)
                for idx0 in run_starts_fn(np.abs(v) > v_lim):
                    add_event(idx0, "warn", "rod_speed", corner, f"Скорость штока {corner} > {v_lim:g} м/с")

    pressure_df_ok = False
    if df_p is not None and TIME_COL in df_p.columns:
        pressure_df_ok = len(df_p) > 1 if align_pressure_df_to_main else len(df_p) == n
    if pressure_df_ok:
        cols = [col for col in df_p.columns if col not in (TIME_COL, "АТМ")]
        if cols:
            pmax_abs = float(params_abs.get("давление_Pmax_предохран", p_atm + 8e5))
            pmax_thr = pmax_abs + float(pmax_margin_gauge) * float(gauge_pressure_scale_pa)
            try:
                df_p_eval = align_frame_to_time_vector(df_p, t_arr) if align_pressure_df_to_main else df_p
                p_nodes = df_p_eval[cols].to_numpy(dtype=float)
                if use_nan_pressure_reducers:
                    p_max = np.nanmax(p_nodes, axis=1)
                    p_min = np.nanmin(p_nodes, axis=1)
                else:
                    p_max = np.max(p_nodes, axis=1)
                    p_min = np.min(p_nodes, axis=1)
            except Exception:
                p_max = None
                p_min = None

            if p_max is not None:
                for idx0 in run_starts_fn(p_max > pmax_thr):
                    add_event(idx0, "error", "overpressure", "nodes", "P>ПРЕДОХ (max node)")

            vac_thr = p_atm + float(vacuum_min_gauge) * float(gauge_pressure_scale_pa)
            p_abs_min = float(params_abs.get("минимальное_абсолютное_давление_Па", 1000.0))
            vac_thr = max(vac_thr, p_abs_min + 1.0)
            if p_min is not None:
                for idx0 in run_starts_fn(p_min < vac_thr):
                    add_event(
                        idx0,
                        "warn",
                        "vacuum",
                        "nodes",
                        f"Вакуум: min node < {vacuum_min_gauge:g} {vacuum_unit_label}",
                    )

    open_df_ok = False
    if df_open is not None and TIME_COL in df_open.columns:
        open_df_ok = len(df_open) > 1 if align_open_df_to_main else len(df_open) == n
    if open_df_ok:
        try:
            df_open_eval = align_frame_to_time_vector(df_open, t_arr) if align_open_df_to_main else df_open
        except Exception:
            df_open_eval = df_open

        edge_cols = [col for col in df_open_eval.columns if col != TIME_COL]
        toggle_stats = []
        for col in edge_cols:
            arr = df_open_eval[col].to_numpy()
            d = np.diff(arr.astype(int), prepend=int(arr[0]))
            togg = np.where(d != 0)[0].astype(int)
            if togg.size > 0:
                toggle_stats.append((int(togg.size), col, togg))
        toggle_stats.sort(reverse=True, key=lambda item: item[0])

        for cnt, col, togg in toggle_stats[:8]:
            if cnt < chatter_toggle_count:
                continue
            i = 0
            j = 0
            togg_list = togg.tolist()
            while i < len(togg_list):
                t_i = float(t_arr[togg_list[i]])
                if j < i:
                    j = i
                while j < len(togg_list) and float(t_arr[togg_list[j]]) - t_i <= chatter_window_s:
                    j += 1
                win_cnt = j - i
                if win_cnt >= chatter_toggle_count:
                    name = shorten_name_fn(col, 55)
                    add_event(
                        togg_list[i],
                        "info",
                        "chatter",
                        name,
                        f"Дребезг: {name} ({win_cnt} toggles/{chatter_window_s:.2f}s)",
                    )
                    i = j
                else:
                    i += 1

    sev_rank = {"error": 0, "warn": 1, "info": 2}
    events.sort(key=lambda ev: (int(ev.get("idx", 0)), sev_rank.get(str(ev.get("severity")), 9), str(ev.get("id"))))

    if len(events) > max_events:
        errs = [ev for ev in events if ev.get("severity") == "error"]
        warns = [ev for ev in events if ev.get("severity") == "warn"]
        infos = [ev for ev in events if ev.get("severity") == "info"]

        keep: List[dict] = []
        keep.extend(errs[:max_events])
        if len(keep) < max_events:
            keep.extend(warns[: (max_events - len(keep))])
        if len(keep) < max_events:
            keep.extend(infos[: (max_events - len(keep))])
        keep.sort(key=lambda ev: (int(ev.get("idx", 0)), sev_rank.get(str(ev.get("severity")), 9)))
        events = keep

    return events
