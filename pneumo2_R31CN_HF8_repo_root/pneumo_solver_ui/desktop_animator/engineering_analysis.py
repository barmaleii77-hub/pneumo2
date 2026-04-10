# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Sequence

import numpy as np

from .data_bundle import CORNERS, DataBundle

BAR_PA = 100000.0
PATM_PA_DEFAULT = 101325.0

MODE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("all_all", "Все↔Все"),
    ("one_all", "Фокус↔Все"),
    ("corner_corner", "Угол↔Угол"),
)

GLOBAL_METRIC_OPTIONS: tuple[tuple[str, str], ...] = (
    ("body_az_mean", "Кузов az"),
    ("wheel_az_mean", "Колесо az"),
    ("contact_gap_mean", "Колесо↔дорога"),
    ("travel_mean", "Колесо↔рама"),
    ("roll_proxy", "Крен"),
    ("pitch_proxy", "Тангаж"),
    ("tire_split", "Нагрузочный split"),
    ("pressure_spread_bar", "Пневмо split"),
    ("air_fraction", "Air fraction"),
)

CORNER_METRIC_OPTIONS: tuple[tuple[str, str], ...] = (
    ("az_body", "az рамы"),
    ("az_wheel", "az колеса"),
    ("wheel_road", "Колесо↔дорога"),
    ("wheel_body", "Колесо↔рама"),
    ("stroke", "Положение штока"),
    ("tireF", "Нагрузка шины"),
    ("wheel_air", "Колесо в воздухе"),
)

_MAIN_PRESSURE_COLS: tuple[str, ...] = (
    "давление_ресивер1_Па",
    "давление_ресивер2_Па",
    "давление_ресивер3_Па",
    "давление_аккумулятор_Па",
)

_GLOBAL_LABEL_MAP: dict[str, str] = dict(GLOBAL_METRIC_OPTIONS)
_CORNER_LABEL_MAP: dict[str, str] = dict(CORNER_METRIC_OPTIONS)


@dataclass
class AnalysisCatalog:
    t: np.ndarray
    global_series: Dict[str, np.ndarray]
    corner_series: Dict[str, Dict[str, np.ndarray]]
    global_scales: Dict[str, float]
    corner_family_scales: Dict[str, float]
    corner_scales: Dict[str, Dict[str, float]]


def _series(values: Any, n: int, *, fill: float = 0.0) -> np.ndarray:
    try:
        arr = np.asarray(values, dtype=float).reshape(-1)
    except Exception:
        arr = np.zeros((0,), dtype=float)
    if n <= 0:
        return np.zeros((0,), dtype=float)
    if arr.size == n:
        return arr
    if arr.size <= 0:
        return np.full((n,), float(fill), dtype=float)
    out = np.full((n,), float(fill), dtype=float)
    k = min(int(arr.size), int(n))
    out[:k] = np.asarray(arr[:k], dtype=float)
    if k > 0 and k < n:
        out[k:] = float(arr[k - 1])
    return out


def _mean_stack(parts: Iterable[np.ndarray], n: int) -> np.ndarray:
    arrs = [np.asarray(x, dtype=float).reshape(-1) for x in parts]
    if not arrs:
        return np.zeros((n,), dtype=float)
    stack = np.vstack([_series(x, n) for x in arrs])
    return np.nanmean(stack, axis=0)


def _metric_scale(arr: np.ndarray, *, fallback: float = 1.0) -> float:
    try:
        finite = np.asarray(arr, dtype=float)
        finite = finite[np.isfinite(finite)]
        if finite.size <= 0:
            return float(fallback)
        scale = float(np.nanpercentile(np.abs(finite), 95.0))
        return float(scale if scale > 1e-9 else fallback)
    except Exception:
        return float(fallback)


def _corr_pair(x: np.ndarray, y: np.ndarray) -> float:
    xx = np.asarray(x, dtype=float).reshape(-1)
    yy = np.asarray(y, dtype=float).reshape(-1)
    m = np.isfinite(xx) & np.isfinite(yy)
    if int(np.count_nonzero(m)) < 3:
        return 0.0
    xx = xx[m]
    yy = yy[m]
    xx = xx - float(np.nanmean(xx))
    yy = yy - float(np.nanmean(yy))
    sx = float(np.nanstd(xx))
    sy = float(np.nanstd(yy))
    if sx <= 1e-9 or sy <= 1e-9:
        return 0.0
    corr = float(np.nanmean((xx / sx) * (yy / sy)))
    return float(np.clip(corr, -1.0, 1.0))


def _corr_matrix(series_map: Mapping[str, np.ndarray]) -> np.ndarray:
    keys = list(series_map.keys())
    n = len(keys)
    if n <= 0:
        return np.zeros((0, 0), dtype=float)
    out = np.eye(n, dtype=float)
    for i in range(n):
        xi = np.asarray(series_map[keys[i]], dtype=float)
        for j in range(i + 1, n):
            val = _corr_pair(xi, np.asarray(series_map[keys[j]], dtype=float))
            out[i, j] = val
            out[j, i] = val
    return out


def _window_mask(t: np.ndarray, center_t: float, window_s: float) -> np.ndarray:
    tt = np.asarray(t, dtype=float).reshape(-1)
    if tt.size <= 0:
        return np.zeros((0,), dtype=bool)
    half = float(max(0.20, window_s * 0.5))
    mask = np.abs(tt - float(center_t)) <= half
    if int(np.count_nonzero(mask)) >= min(8, int(tt.size)):
        return mask
    idx = int(np.clip(np.searchsorted(tt, float(center_t)), 0, max(0, int(tt.size) - 1)))
    lo = max(0, idx - 4)
    hi = min(int(tt.size), idx + 5)
    mask = np.zeros((int(tt.size),), dtype=bool)
    mask[lo:hi] = True
    return mask


def _sample_at_time(t: np.ndarray, arr: np.ndarray, center_t: float) -> float:
    tt = np.asarray(t, dtype=float).reshape(-1)
    aa = np.asarray(arr, dtype=float).reshape(-1)
    n = min(int(tt.size), int(aa.size))
    if n <= 0:
        return 0.0
    if n == 1:
        return float(aa[0])
    try:
        return float(np.interp(float(center_t), tt[:n], aa[:n]))
    except Exception:
        idx = int(np.clip(np.searchsorted(tt[:n], float(center_t)), 0, n - 1))
        return float(aa[idx])


def _format_metric_value(metric_id: str, value: float) -> str:
    v = float(value)
    if metric_id in {"body_az_mean", "wheel_az_mean", "az_body", "az_wheel"}:
        return f"{v:+.2f} м/с²"
    if metric_id in {"contact_gap_mean", "travel_mean", "roll_proxy", "pitch_proxy", "wheel_road", "wheel_body", "stroke"}:
        return f"{v:+.3f} м"
    if metric_id == "tireF":
        return f"{v / 1000.0:.2f} кН"
    if metric_id == "tire_split":
        return f"{v:+.2f}"
    if metric_id == "pressure_spread_bar":
        return f"{v:.2f} бар"
    if metric_id in {"air_fraction", "wheel_air"}:
        return f"{v:.2f}"
    return f"{v:+.3f}"


def _pressure_series(bundle: DataBundle, n: int) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    try:
        if bundle.p is not None:
            for name in ("Ресивер1", "Ресивер2", "Ресивер3", "Аккумулятор"):
                if bundle.p.has(name):
                    out.append(_series(bundle.p.column(name), n))
    except Exception:
        pass
    for col in _MAIN_PRESSURE_COLS:
        try:
            if bundle.main.has(col):
                out.append(_series(bundle.get(col, 0.0), n))
        except Exception:
            pass
    return out


def collect_analysis_catalog(bundle: DataBundle) -> AnalysisCatalog:
    t = np.asarray(bundle.t, dtype=float).reshape(-1)
    n = int(t.size)
    body_z: dict[str, np.ndarray] = {}
    body_az: dict[str, np.ndarray] = {}
    wheel_az: dict[str, np.ndarray] = {}
    wheel_road: dict[str, np.ndarray] = {}
    wheel_body: dict[str, np.ndarray] = {}
    stroke: dict[str, np.ndarray] = {}
    tire_force: dict[str, np.ndarray] = {}
    wheel_air: dict[str, np.ndarray] = {}

    for corner in CORNERS:
        c = str(corner)
        zb = _series(bundle.frame_corner_z(c, default=0.0), n)
        body_z[c] = zb
        body_az[c] = _series(bundle.frame_corner_a(c, default=0.0), n)
        zw = _series(bundle.get(f"перемещение_колеса_{c}_м", 0.0), n)
        zr = _series(bundle.road_series(c), n, fill=float("nan"))
        wheel_az[c] = _series(bundle.get(f"ускорение_колеса_{c}_м_с2", 0.0), n)
        wheel_road[c] = zw - zr
        wheel_body[c] = zw - zb
        stroke[c] = _series(bundle.get(f"положение_штока_{c}_м", 0.0), n)
        tire_force[c] = _series(bundle.get(f"нормальная_сила_шины_{c}_Н", 0.0), n)
        wheel_air[c] = _series(bundle.get(f"колесо_в_воздухе_{c}", 0.0), n)

    pressures = _pressure_series(bundle, n)
    if pressures:
        p_stack = np.vstack([np.asarray(x, dtype=float) for x in pressures])
        pressure_spread_bar = (np.nanmax(p_stack, axis=0) - np.nanmin(p_stack, axis=0)) / float(BAR_PA)
    else:
        pressure_spread_bar = np.zeros((n,), dtype=float)

    left_load = tire_force["ЛП"] + tire_force["ЛЗ"]
    right_load = tire_force["ПП"] + tire_force["ПЗ"]
    load_sum = np.maximum(np.abs(left_load) + np.abs(right_load), 1.0)
    tire_split = (left_load - right_load) / load_sum

    global_series = {
        "body_az_mean": _mean_stack(body_az.values(), n),
        "wheel_az_mean": _mean_stack(wheel_az.values(), n),
        "contact_gap_mean": _mean_stack(wheel_road.values(), n),
        "travel_mean": _mean_stack(wheel_body.values(), n),
        "roll_proxy": 0.5 * ((body_z["ЛП"] + body_z["ЛЗ"]) - (body_z["ПП"] + body_z["ПЗ"])),
        "pitch_proxy": 0.5 * ((body_z["ЛП"] + body_z["ПП"]) - (body_z["ЛЗ"] + body_z["ПЗ"])),
        "tire_split": tire_split,
        "pressure_spread_bar": np.asarray(pressure_spread_bar, dtype=float),
        "air_fraction": _mean_stack(wheel_air.values(), n),
    }

    corner_series = {
        "az_body": body_az,
        "az_wheel": wheel_az,
        "wheel_road": wheel_road,
        "wheel_body": wheel_body,
        "stroke": stroke,
        "tireF": tire_force,
        "wheel_air": wheel_air,
    }

    global_scales = {
        key: _metric_scale(arr, fallback=1.0)
        for key, arr in global_series.items()
    }
    corner_scales: dict[str, dict[str, float]] = {}
    corner_family_scales: dict[str, float] = {}
    for family, per_corner in corner_series.items():
        family_scale = max((_metric_scale(arr, fallback=1.0) for arr in per_corner.values()), default=1.0)
        corner_family_scales[family] = float(max(1e-9, family_scale))
        corner_scales[family] = {
            corner: _metric_scale(arr, fallback=corner_family_scales[family])
            for corner, arr in per_corner.items()
        }

    return AnalysisCatalog(
        t=t,
        global_series=global_series,
        corner_series=corner_series,
        global_scales=global_scales,
        corner_family_scales=corner_family_scales,
        corner_scales=corner_scales,
    )


def _corner_cloud_payload(
    catalog: AnalysisCatalog,
    *,
    center_t: float,
    corner_metric: str,
    mode: str,
) -> dict[str, dict[str, object]]:
    tt = np.asarray(catalog.t, dtype=float)
    payload: dict[str, dict[str, object]] = {}
    if mode == "corner_corner" and corner_metric in catalog.corner_series:
        family_map = catalog.corner_series[corner_metric]
        family_scale = float(max(1e-9, catalog.corner_family_scales.get(corner_metric, 1.0)))
        for corner in CORNERS:
            c = str(corner)
            value = _sample_at_time(tt, family_map[c], center_t)
            score = float(np.clip(abs(value) / family_scale, 0.0, 1.0))
            payload[c] = {
                "score": score,
                "metric": corner_metric,
                "label": _CORNER_LABEL_MAP.get(corner_metric, corner_metric),
                "value": value,
                "value_text": _format_metric_value(corner_metric, value),
            }
        return payload

    family_ids = ("wheel_road", "wheel_body", "stroke", "az_wheel", "wheel_air")
    for corner in CORNERS:
        c = str(corner)
        best_metric = "wheel_road"
        best_score = -1.0
        best_value = 0.0
        for family in family_ids:
            family_map = catalog.corner_series.get(family, {})
            arr = family_map.get(c)
            if arr is None:
                continue
            value = _sample_at_time(tt, arr, center_t)
            scale = float(max(1e-9, catalog.corner_scales.get(family, {}).get(c, catalog.corner_family_scales.get(family, 1.0))))
            score = float(np.clip(abs(value) / scale, 0.0, 1.0))
            if family == "wheel_air":
                score = 1.0 if value > 0.5 else 0.0
            if score > best_score:
                best_metric = family
                best_score = score
                best_value = value
        payload[c] = {
            "score": float(max(0.0, best_score)),
            "metric": best_metric,
            "label": _CORNER_LABEL_MAP.get(best_metric, best_metric),
            "value": best_value,
            "value_text": _format_metric_value(best_metric, best_value),
        }
    return payload


def rank_global_focus_metrics(
    catalog: AnalysisCatalog,
    *,
    idx: int = 0,
    sample_t: float | None = None,
    window_s: float = 2.0,
) -> list[dict[str, object]]:
    t = np.asarray(catalog.t, dtype=float).reshape(-1)
    if t.size <= 0:
        return []
    center_idx = int(np.clip(int(idx), 0, max(0, int(t.size) - 1)))
    center_t = float(sample_t if sample_t is not None else t[center_idx])
    mask = _window_mask(t, center_t, float(max(0.5, window_s)))
    metric_ids = [key for key, _label in GLOBAL_METRIC_OPTIONS if key in catalog.global_series]
    if not metric_ids:
        return []
    series_map = {
        metric_id: np.asarray(catalog.global_series[metric_id], dtype=float)[mask]
        for metric_id in metric_ids
    }
    matrix = _corr_matrix(series_map)
    ranked: list[dict[str, object]] = []
    for row_idx, metric_id in enumerate(metric_ids):
        full_arr = np.asarray(catalog.global_series[metric_id], dtype=float)
        value = float(_sample_at_time(t, full_arr, center_t))
        scale = float(max(1e-9, catalog.global_scales.get(metric_id, 1.0)))
        normalized = float(np.clip(abs(value) / scale, 0.0, 1.5))
        coupling = 0.0
        if matrix.shape[0] > 1:
            coupling = float(np.nanmean(np.abs(np.delete(matrix[row_idx], row_idx))))
        score = float((0.72 * normalized) + (0.28 * coupling))
        ranked.append(
            {
                "metric": metric_id,
                "label": _GLOBAL_LABEL_MAP.get(metric_id, metric_id),
                "value": value,
                "value_text": _format_metric_value(metric_id, value),
                "normalized": normalized,
                "coupling": coupling,
                "score": score,
            }
        )
    ranked.sort(key=lambda item: (float(item.get("score", 0.0)), float(item.get("normalized", 0.0))), reverse=True)
    return ranked


def build_multifactor_analysis_payload(
    catalog: AnalysisCatalog,
    *,
    idx: int,
    sample_t: float | None = None,
    mode: str = "all_all",
    focus_metric: str = "roll_proxy",
    corner_metric: str = "wheel_road",
    window_s: float = 2.0,
) -> dict[str, object]:
    t = np.asarray(catalog.t, dtype=float).reshape(-1)
    if t.size <= 0:
        return {
            "mode": str(mode),
            "center_t_s": 0.0,
            "names": [],
            "labels": [],
            "matrix": np.zeros((0, 0), dtype=float),
            "current_values": {},
            "current_text": {},
            "top_pairs": [],
            "insights": ["Данные для мультифакторного анализа отсутствуют."],
            "corner_cloud": {},
        }

    center_idx = int(np.clip(int(idx), 0, max(0, int(t.size) - 1)))
    center_t = float(sample_t if sample_t is not None else t[center_idx])
    window = float(max(0.5, window_s))
    mask = _window_mask(t, center_t, window)

    if mode == "corner_corner":
        family = str(corner_metric if corner_metric in catalog.corner_series else "wheel_road")
        series_map = {
            corner: np.asarray(catalog.corner_series[family][corner], dtype=float)[mask]
            for corner in CORNERS
        }
        labels = [str(corner) for corner in CORNERS]
        names = [str(corner) for corner in CORNERS]
        current_values = {
            str(corner): _sample_at_time(t, catalog.corner_series[family][str(corner)], center_t)
            for corner in CORNERS
        }
        title = f"Семейство углов: {_CORNER_LABEL_MAP.get(family, family)}"
    else:
        metric_ids = [key for key, _label in GLOBAL_METRIC_OPTIONS if key in catalog.global_series]
        if mode == "one_all":
            focus = str(focus_metric if focus_metric in catalog.global_series else "roll_proxy")
            metric_ids = [focus] + [key for key in metric_ids if key != focus]
            title = f"Фокус-метрика: {_GLOBAL_LABEL_MAP.get(focus, focus)}"
        else:
            title = "Глобальная инженерная сцепка"
        series_map = {
            metric_id: np.asarray(catalog.global_series[metric_id], dtype=float)[mask]
            for metric_id in metric_ids
        }
        labels = [_GLOBAL_LABEL_MAP.get(metric_id, metric_id) for metric_id in metric_ids]
        names = list(metric_ids)
        current_values = {
            metric_id: _sample_at_time(t, catalog.global_series[metric_id], center_t)
            for metric_id in metric_ids
        }

    matrix = _corr_matrix(series_map)
    current_text = {
        name: _format_metric_value(name if name in _GLOBAL_LABEL_MAP or name in _CORNER_LABEL_MAP else corner_metric, float(value))
        for name, value in current_values.items()
    }

    top_pairs: list[dict[str, object]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            corr = float(matrix[i, j])
            top_pairs.append(
                {
                    "left": names[i],
                    "right": names[j],
                    "left_label": labels[i],
                    "right_label": labels[j],
                    "corr": corr,
                    "strength": abs(corr),
                }
            )
    top_pairs.sort(key=lambda item: float(item["strength"]), reverse=True)
    top_pairs = top_pairs[:5]

    insights: list[str] = [title]
    if top_pairs:
        best = top_pairs[0]
        insights.append(
            f"Сильнейшая локальная связь: {best['left_label']} ↔ {best['right_label']} (corr {float(best['corr']):+.2f})."
        )

    air_now = float(current_values.get("air_fraction", 0.0))
    if air_now > 0.15:
        insights.append("Есть заметная доля состояний wheel-in-air: проверяйте контакт и демпфирование по углам.")

    roll_now = float(current_values.get("roll_proxy", 0.0))
    roll_scale = float(max(1e-9, catalog.global_scales.get("roll_proxy", 1.0)))
    if abs(roll_now) > 0.65 * roll_scale:
        insights.append("Крен сейчас выраженный: полезно сверить left/right load split и дорожный профиль.")

    pitch_now = float(current_values.get("pitch_proxy", 0.0))
    pitch_scale = float(max(1e-9, catalog.global_scales.get("pitch_proxy", 1.0)))
    if abs(pitch_now) > 0.65 * pitch_scale:
        insights.append("Тангаж сейчас доминирует: проверьте front/rear ход подвески и пики ускорения колёс.")

    p_now = float(current_values.get("pressure_spread_bar", 0.0))
    p_scale = float(max(1e-9, catalog.global_scales.get("pressure_spread_bar", 1.0)))
    if p_now > 0.60 * p_scale and p_now > 0.10:
        insights.append("Пневматика заметно асимметрична: разнос давлений уже влияет на общую картину движения.")

    if mode == "corner_corner":
        family = str(corner_metric if corner_metric in catalog.corner_series else "wheel_road")
        strongest_corner = max(
            CORNERS,
            key=lambda corner: abs(float(current_values.get(str(corner), 0.0))),
        )
        insights.append(
            f"Максимум по семейству '{_CORNER_LABEL_MAP.get(family, family)}' сейчас у угла {strongest_corner}: "
            f"{current_text.get(str(strongest_corner), '—')}."
        )

    corner_cloud = _corner_cloud_payload(
        catalog,
        center_t=center_t,
        corner_metric=str(corner_metric),
        mode=str(mode),
    )

    return {
        "mode": str(mode),
        "center_t_s": center_t,
        "window_s": window,
        "names": names,
        "labels": labels,
        "matrix": matrix,
        "current_values": current_values,
        "current_text": current_text,
        "top_pairs": top_pairs,
        "insights": insights,
        "corner_cloud": corner_cloud,
    }


__all__ = [
    "AnalysisCatalog",
    "CORNER_METRIC_OPTIONS",
    "GLOBAL_METRIC_OPTIONS",
    "MODE_OPTIONS",
    "build_multifactor_analysis_payload",
    "collect_analysis_catalog",
    "rank_global_focus_metrics",
]
