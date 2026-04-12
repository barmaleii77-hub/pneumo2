# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

import numpy as np
import pandas as pd

if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    __package__ = "pneumo_solver_ui.tools"

from pneumo_solver_ui.module_loading import load_python_module_from_path
from pneumo_solver_ui.opt_worker_v3_margins_energy import _compile_timeseries_inputs


_WORKER_CACHE: dict[str, Any] = {
    "key": None,
    "model": None,
    "base_params": None,
    "ring_test": None,
    "ring_t_end": None,
}


def _default_base_json_path() -> Path:
    return Path(__file__).resolve().parents[1] / "default_base.json"


def _default_model_path() -> Path:
    return Path(__file__).resolve().parents[1] / "model_pneumo_v9_mech_doublewishbone_worldroad.py"


def _default_outputs() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[2]
    return (
        root / "tmp_parallel_pneumo_curated_scan.csv",
        root / "tmp_parallel_pneumo_curated_best.json",
    )


def _builtin_curated_candidates() -> list[dict[str, Any]]:
    common_geom = {
        "верх_Ц1_перед_x_относительно_оси_ступицы_м": 0.05,
        "верх_Ц1_зад_x_относительно_оси_ступицы_м": 0.05,
        "верх_Ц2_перед_x_относительно_оси_ступицы_м": -0.06,
        "верх_Ц2_зад_x_относительно_оси_ступицы_м": -0.06,
        "верх_Ц1_перед_z_относительно_рамы_м": 0.52,
        "верх_Ц1_зад_z_относительно_рамы_м": 0.52,
        "верх_Ц2_перед_z_относительно_рамы_м": 0.52,
        "верх_Ц2_зад_z_относительно_рамы_м": 0.52,
    }
    return [
        {"name": "current_defaults", "overrides": {}},
        {
            "name": "higher_regulators",
            "overrides": {
                **common_geom,
                "диаметр_поршня_Ц1": 0.045,
                "диаметр_поршня_Ц2": 0.05,
                "низ_Ц1_перед_доля_рычага": 0.85,
                "низ_Ц1_зад_доля_рычага": 0.85,
                "низ_Ц2_перед_доля_рычага": 0.82,
                "низ_Ц2_зад_доля_рычага": 0.82,
                "ход_штока_Ц1_перед_м": 0.28,
                "ход_штока_Ц1_зад_м": 0.28,
                "ход_штока_Ц2_перед_м": 0.28,
                "ход_штока_Ц2_зад_м": 0.28,
                "пружина_масштаб": 0.14,
                "пружина_Ц1_перед_масштаб": 0.14,
                "пружина_Ц1_зад_масштаб": 0.14,
                "пружина_Ц2_перед_масштаб": 0.14,
                "пружина_Ц2_зад_масштаб": 0.14,
                "давление_Pmin_питание_Ресивер2": 505300.0,
                "давление_Pmin_сброс": 601325.0,
                "давление_Pmid_сброс": 851325.0,
                "давление_Pзаряд_аккумулятора_из_Ресивер3": 911325.0,
                "открытие_дросселя_Ц2_CAP_в_ROD": 0.26,
                "открытие_дросселя_Ц2_ROD_в_CAP": 0.14,
                "объём_ресивера_2": 0.002,
                "объём_ресивера_3": 0.003,
                "объём_аккумулятора": 0.003,
            },
        },
        {
            "name": "fullstroke_safe",
            "overrides": {
                **common_geom,
                "диаметр_поршня_Ц1": 0.045,
                "диаметр_поршня_Ц2": 0.05,
                "низ_Ц1_перед_доля_рычага": 0.82,
                "низ_Ц1_зад_доля_рычага": 0.82,
                "низ_Ц2_перед_доля_рычага": 0.74,
                "низ_Ц2_зад_доля_рычага": 0.74,
                "ход_штока_Ц1_перед_м": 0.32,
                "ход_штока_Ц1_зад_м": 0.32,
                "ход_штока_Ц2_перед_м": 0.32,
                "ход_штока_Ц2_зад_м": 0.32,
                "пружина_масштаб": 0.14,
                "пружина_Ц1_перед_масштаб": 0.14,
                "пружина_Ц1_зад_масштаб": 0.14,
                "пружина_Ц2_перед_масштаб": 0.14,
                "пружина_Ц2_зад_масштаб": 0.14,
                "давление_Pmin_питание_Ресивер2": 505300.0,
                "давление_Pmin_сброс": 601325.0,
                "давление_Pmid_сброс": 851325.0,
                "давление_Pзаряд_аккумулятора_из_Ресивер3": 911325.0,
                "открытие_дросселя_Ц2_CAP_в_ROD": 0.26,
                "открытие_дросселя_Ц2_ROD_в_CAP": 0.14,
                "объём_ресивера_2": 0.002,
                "объём_ресивера_3": 0.003,
                "объём_аккумулятора": 0.003,
            },
        },
        {
            "name": "reserve_pack",
            "overrides": {
                **common_geom,
                "диаметр_поршня_Ц1": 0.05,
                "диаметр_поршня_Ц2": 0.055,
                "низ_Ц1_перед_доля_рычага": 0.92,
                "низ_Ц1_зад_доля_рычага": 0.92,
                "низ_Ц2_перед_доля_рычага": 0.82,
                "низ_Ц2_зад_доля_рычага": 0.82,
                "ход_штока_Ц1_перед_м": 0.28,
                "ход_штока_Ц1_зад_м": 0.28,
                "ход_штока_Ц2_перед_м": 0.28,
                "ход_штока_Ц2_зад_м": 0.28,
                "пружина_масштаб": 0.12,
                "пружина_Ц1_перед_масштаб": 0.12,
                "пружина_Ц1_зад_масштаб": 0.12,
                "пружина_Ц2_перед_масштаб": 0.12,
                "пружина_Ц2_зад_масштаб": 0.12,
                "давление_Pmin_питание_Ресивер2": 505300.0,
                "давление_Pmin_сброс": 601325.0,
                "давление_Pmid_сброс": 851325.0,
                "давление_Pзаряд_аккумулятора_из_Ресивер3": 911325.0,
                "открытие_дросселя_Ц2_CAP_в_ROD": 0.18,
                "открытие_дросселя_Ц2_ROD_в_CAP": 0.10,
                "объём_ресивера_2": 0.003,
                "объём_ресивера_3": 0.003,
                "объём_аккумулятора": 0.003,
            },
        },
        {
            "name": "pump_biased_balanced",
            "overrides": {
                **common_geom,
                "диаметр_поршня_Ц1": 0.05,
                "диаметр_поршня_Ц2": 0.045,
                "низ_Ц1_перед_доля_рычага": 0.90,
                "низ_Ц1_зад_доля_рычага": 0.90,
                "низ_Ц2_перед_доля_рычага": 0.72,
                "низ_Ц2_зад_доля_рычага": 0.72,
                "ход_штока_Ц1_перед_м": 0.34,
                "ход_штока_Ц1_зад_м": 0.34,
                "ход_штока_Ц2_перед_м": 0.34,
                "ход_штока_Ц2_зад_м": 0.34,
                "пружина_масштаб": 0.135,
                "пружина_Ц1_перед_масштаб": 0.135,
                "пружина_Ц1_зад_масштаб": 0.135,
                "пружина_Ц2_перед_масштаб": 0.135,
                "пружина_Ц2_зад_масштаб": 0.135,
                "давление_Pmin_питание_Ресивер2": 505300.0,
                "давление_Pmin_сброс": 601325.0,
                "давление_Pmid_сброс": 851325.0,
                "давление_Pзаряд_аккумулятора_из_Ресивер3": 911325.0,
                "открытие_дросселя_Ц2_CAP_в_ROD": 0.24,
                "открытие_дросселя_Ц2_ROD_в_CAP": 0.11,
                "объём_ресивера_2": 0.0025,
                "объём_ресивера_3": 0.003,
                "объём_аккумулятора": 0.003,
            },
        },
        {
            "name": "pump_biased_longstroke",
            "overrides": {
                **common_geom,
                "диаметр_поршня_Ц1": 0.052,
                "диаметр_поршня_Ц2": 0.045,
                "низ_Ц1_перед_доля_рычага": 0.88,
                "низ_Ц1_зад_доля_рычага": 0.88,
                "низ_Ц2_перед_доля_рычага": 0.70,
                "низ_Ц2_зад_доля_рычага": 0.70,
                "ход_штока_Ц1_перед_м": 0.36,
                "ход_штока_Ц1_зад_м": 0.36,
                "ход_штока_Ц2_перед_м": 0.36,
                "ход_штока_Ц2_зад_м": 0.36,
                "пружина_масштаб": 0.13,
                "пружина_Ц1_перед_масштаб": 0.13,
                "пружина_Ц1_зад_масштаб": 0.13,
                "пружина_Ц2_перед_масштаб": 0.13,
                "пружина_Ц2_зад_масштаб": 0.13,
                "давление_Pmin_питание_Ресивер2": 505300.0,
                "давление_Pmin_сброс": 601325.0,
                "давление_Pmid_сброс": 851325.0,
                "давление_Pзаряд_аккумулятора_из_Ресивер3": 911325.0,
                "открытие_дросселя_Ц2_CAP_в_ROD": 0.22,
                "открытие_дросселя_Ц2_ROD_в_CAP": 0.10,
                "объём_ресивера_2": 0.0025,
                "объём_ресивера_3": 0.0035,
                "объём_аккумулятора": 0.003,
            },
        },
        {
            "name": "pump_biased_more_recharge",
            "overrides": {
                **common_geom,
                "диаметр_поршня_Ц1": 0.055,
                "диаметр_поршня_Ц2": 0.045,
                "низ_Ц1_перед_доля_рычага": 0.92,
                "низ_Ц1_зад_доля_рычага": 0.92,
                "низ_Ц2_перед_доля_рычага": 0.74,
                "низ_Ц2_зад_доля_рычага": 0.74,
                "ход_штока_Ц1_перед_м": 0.34,
                "ход_штока_Ц1_зад_м": 0.34,
                "ход_штока_Ц2_перед_м": 0.34,
                "ход_штока_Ц2_зад_м": 0.34,
                "пружина_масштаб": 0.14,
                "пружина_Ц1_перед_масштаб": 0.14,
                "пружина_Ц1_зад_масштаб": 0.14,
                "пружина_Ц2_перед_масштаб": 0.14,
                "пружина_Ц2_зад_масштаб": 0.14,
                "давление_Pmin_питание_Ресивер2": 505300.0,
                "давление_Pmin_сброс": 601325.0,
                "давление_Pmid_сброс": 851325.0,
                "давление_Pзаряд_аккумулятора_из_Ресивер3": 931325.0,
                "открытие_дросселя_Ц2_CAP_в_ROD": 0.24,
                "открытие_дросселя_Ц2_ROD_в_CAP": 0.12,
                "объём_ресивера_2": 0.003,
                "объём_ресивера_3": 0.0035,
                "объём_аккумулятора": 0.0025,
            },
        },
        {
            "name": "pump_biased_soft_bump",
            "overrides": {
                **common_geom,
                "диаметр_поршня_Ц1": 0.05,
                "диаметр_поршня_Ц2": 0.043,
                "низ_Ц1_перед_доля_рычага": 0.86,
                "низ_Ц1_зад_доля_рычага": 0.86,
                "низ_Ц2_перед_доля_рычага": 0.74,
                "низ_Ц2_зад_доля_рычага": 0.74,
                "ход_штока_Ц1_перед_м": 0.34,
                "ход_штока_Ц1_зад_м": 0.34,
                "ход_штока_Ц2_перед_м": 0.34,
                "ход_штока_Ц2_зад_м": 0.34,
                "пружина_масштаб": 0.14,
                "пружина_Ц1_перед_масштаб": 0.14,
                "пружина_Ц1_зад_масштаб": 0.14,
                "пружина_Ц2_перед_масштаб": 0.14,
                "пружина_Ц2_зад_масштаб": 0.14,
                "давление_Pmin_питание_Ресивер2": 505300.0,
                "давление_Pmin_сброс": 601325.0,
                "давление_Pmid_сброс": 831325.0,
                "давление_Pзаряд_аккумулятора_из_Ресивер3": 901325.0,
                "открытие_дросселя_Ц2_CAP_в_ROD": 0.20,
                "открытие_дросселя_Ц2_ROD_в_CAP": 0.12,
                "объём_ресивера_2": 0.002,
                "объём_ресивера_3": 0.003,
                "объём_аккумулятора": 0.0035,
            },
        },
    ]


def _load_candidates(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return _builtin_curated_candidates()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("candidate_json must be a JSON list")
    out: list[dict[str, Any]] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise SystemExit(f"candidate_json[{idx}] must be an object")
        if "overrides" in item:
            name = str(item.get("name") or f"candidate_{idx}")
            overrides = item.get("overrides")
            if not isinstance(overrides, dict):
                raise SystemExit(f"candidate_json[{idx}].overrides must be an object")
            out.append({"name": name, "overrides": dict(overrides)})
            continue
        name = str(item.get("name") or f"candidate_{idx}")
        overrides = {k: v for k, v in item.items() if k != "name"}
        out.append({"name": name, "overrides": overrides})
    return out


def _worker_runtime(config: Mapping[str, Any]) -> tuple[Any, dict[str, Any], dict[str, Any] | None, float | None]:
    key = json.dumps(dict(config), sort_keys=True, ensure_ascii=False)
    if _WORKER_CACHE["key"] == key:
        return (
            _WORKER_CACHE["model"],
            _WORKER_CACHE["base_params"],
            _WORKER_CACHE["ring_test"],
            _WORKER_CACHE["ring_t_end"],
        )
    model = load_python_module_from_path(Path(str(config["model_path"])))
    base_params = json.loads(Path(str(config["base_json"])).read_text(encoding="utf-8"))
    ring_test = None
    ring_t_end = None
    road_csv = str(config.get("road_csv") or "").strip()
    axay_csv = str(config.get("axay_csv") or "").strip()
    scenario_json = str(config.get("scenario_json") or "").strip()
    if road_csv and axay_csv and scenario_json and not bool(config.get("antiphase_only", False)):
        ring_test = _compile_timeseries_inputs(
            {
                "road_csv": road_csv,
                "axay_csv": axay_csv,
                "scenario_json": scenario_json,
            }
        )
        ring_t_end = float(ring_test.get("t_end", config.get("ring_t_end", 15.0)) or config.get("ring_t_end", 15.0))
    _WORKER_CACHE["key"] = key
    _WORKER_CACHE["model"] = model
    _WORKER_CACHE["base_params"] = base_params
    _WORKER_CACHE["ring_test"] = ring_test
    _WORKER_CACHE["ring_t_end"] = ring_t_end
    return model, base_params, ring_test, ring_t_end


def _primary_metrics(df_main: pd.DataFrame) -> dict[str, float]:
    z = df_main["перемещение_рамы_z_м"].to_numpy(dtype=float)
    az = df_main["ускорение_рамы_z_м_с2"].to_numpy(dtype=float)
    roll = np.rad2deg(df_main["крен_phi_рад"].to_numpy(dtype=float))
    pitch = np.rad2deg(df_main["тангаж_theta_рад"].to_numpy(dtype=float))
    frac_df = df_main[[c for c in df_main.columns if c.startswith("доля_хода_Ц")]]
    tire_df = df_main[[f"нормальная_сила_шины_{c}_Н" for c in ("ЛП", "ПП", "ЛЗ", "ПЗ")]]
    return {
        "az_rms": float(np.sqrt(np.mean(np.square(az)))),
        "z_std": float(np.std(z)),
        "roll_rms_deg": float(np.sqrt(np.mean(np.square(roll)))),
        "pitch_rms_deg": float(np.sqrt(np.mean(np.square(pitch)))),
        "lift": float(np.mean(tire_df.to_numpy(dtype=float) <= 1.0)),
        "stroke_min": float(frac_df.min().min()),
        "stroke_max": float(frac_df.max().max()),
        "stroke_span": float((frac_df.max() - frac_df.min()).mean()),
        "p3_final_bar_abs": float(df_main["давление_ресивер3_Па"].iloc[-1] / 1e5),
        "pacc_final_bar_abs": float(df_main["давление_аккумулятор_Па"].iloc[-1] / 1e5),
    }


def _stroke_window_metrics(primary: Mapping[str, float]) -> dict[str, float]:
    stroke_min = float(primary["stroke_min"])
    stroke_max = float(primary["stroke_max"])
    stroke_midpoint = 0.5 * (stroke_min + stroke_max)
    stroke_margin_low = stroke_min
    stroke_margin_high = max(0.0, 1.0 - stroke_max)
    stroke_margin_min = min(stroke_margin_low, stroke_margin_high)
    stroke_center_offset = abs(stroke_midpoint - 0.5)
    return {
        "stroke_margin_low": float(stroke_margin_low),
        "stroke_margin_high": float(stroke_margin_high),
        "stroke_margin_min": float(stroke_margin_min),
        "stroke_midpoint": float(stroke_midpoint),
        "stroke_center_offset": float(stroke_center_offset),
    }


def _score_candidate(
    primary: Mapping[str, float],
    diag_to_exhaust_ratio: float,
    pneu_share: float,
    params: Mapping[str, Any],
) -> tuple[float, float, dict[str, float]]:
    stroke_metrics = _stroke_window_metrics(primary)
    penalty = 0.0
    stroke_min = float(primary["stroke_min"])
    stroke_max = float(primary["stroke_max"])
    stroke_span = float(primary["stroke_span"])
    if stroke_metrics["stroke_margin_low"] < 0.10:
        penalty += (0.10 - stroke_metrics["stroke_margin_low"]) * 60.0
    if stroke_metrics["stroke_margin_high"] < 0.10:
        penalty += (0.10 - stroke_metrics["stroke_margin_high"]) * 75.0
    if stroke_span < 0.50:
        penalty += (0.50 - stroke_span) * 14.0
    if stroke_metrics["stroke_center_offset"] > 0.22:
        penalty += (stroke_metrics["stroke_center_offset"] - 0.22) * 8.0
    if diag_to_exhaust_ratio < 5.0:
        penalty += (5.0 - diag_to_exhaust_ratio) * 0.4
    c1_d = float(params.get("диаметр_поршня_Ц1", 0.0) or 0.0)
    c2_d = float(params.get("диаметр_поршня_Ц2", 0.0) or 0.0)
    if c1_d < c2_d:
        penalty += (c2_d - c1_d) * 800.0
    score = (
        float(primary["az_rms"])
        + 2.4 * float(primary["z_std"])
        + 0.10 * float(primary["roll_rms_deg"])
        + 0.07 * float(primary["pitch_rms_deg"])
        + 1.1 * float(primary["lift"])
        - 0.08 * float(pneu_share)
        - 0.02 * stroke_span
        - 0.01 * float(diag_to_exhaust_ratio)
        + penalty
    )
    return float(score), float(penalty), stroke_metrics


def _evaluate_candidate(task: tuple[Mapping[str, Any], Mapping[str, Any]]) -> dict[str, Any]:
    config, candidate = task
    model, base_params, ring_test, ring_t_end = _worker_runtime(config)
    params = dict(base_params)
    params["стабилизатор_вкл"] = False
    overrides = dict(candidate.get("overrides") or {})
    params.update(overrides)

    antiphase_amp = float(config.get("antiphase_amplitude_m", 0.015) or 0.015)
    antiphase_freq = float(config.get("antiphase_frequency_hz", 1.5) or 1.5)
    w = 2.0 * math.pi * antiphase_freq
    antiphase_test = {
        "road_func": lambda t, A=antiphase_amp, w=w: np.array([0.0, A * math.sin(w * t), -A * math.sin(w * t), 0.0], dtype=float),
        "ax_func": lambda t: 0.0,
        "ay_func": lambda t: 0.0,
    }
    antiphase_df, _, antiphase_drossel, _, _, antiphase_edges, _, _ = model.simulate(
        params,
        antiphase_test,
        dt=float(config.get("antiphase_dt", 0.005) or 0.005),
        t_end=float(config.get("antiphase_t_end", 4.0) or 4.0),
        record_full=False,
    )

    primary_df = antiphase_df
    if ring_test is not None and ring_t_end is not None:
        primary_df, *_ = model.simulate(
            params,
            dict(ring_test),
            dt=float(config.get("ring_dt", 0.01) or 0.01),
            t_end=float(ring_t_end),
            record_full=False,
        )

    primary = _primary_metrics(primary_df)
    diag_mask = antiphase_drossel["дроссель"].astype(str).str.contains("дроссель‑диагональ‑Ц2", regex=False)
    exh_mask = antiphase_edges["элемент"].astype(str).str.contains("дроссель_выхлоп_", regex=False)
    diag_energy = float(antiphase_drossel.loc[diag_mask, "энергия_рассеяна_Дж"].sum())
    exhaust_energy = float(antiphase_edges.loc[exh_mask, "энергия_Дж"].sum())
    diag_to_exhaust_ratio = float(diag_energy / max(exhaust_energy, 1e-9))

    pneu_cols = [f"сила_пневматики_{c}_Н" for c in ("ЛП", "ПП", "ЛЗ", "ПЗ")]
    spr_cols = [f"сила_пружины_{c}_Н" for c in ("ЛП", "ПП", "ЛЗ", "ПЗ")]
    pneu_abs = float(np.mean(np.sum(np.abs(primary_df[pneu_cols].to_numpy(dtype=float)), axis=1)))
    spr_abs = float(np.mean(np.sum(np.abs(primary_df[spr_cols].to_numpy(dtype=float)), axis=1)))
    pneu_share = float(pneu_abs / max(spr_abs, 1e-9))

    score, penalty, stroke_metrics = _score_candidate(primary, diag_to_exhaust_ratio, pneu_share, params)
    row: dict[str, Any] = {
        "name": str(candidate.get("name") or "candidate"),
        "score": score,
        "penalty": penalty,
        "diag_energy_J": diag_energy,
        "exhaust_energy_J": exhaust_energy,
        "diag_to_exhaust_ratio": diag_to_exhaust_ratio,
        "pneu_share": pneu_share,
        "overrides_json": json.dumps(overrides, ensure_ascii=False, sort_keys=True),
    }
    row.update(primary)
    row.update(stroke_metrics)
    for key, value in overrides.items():
        row[f"параметр__{key}"] = value
    return row


def _build_arg_parser() -> argparse.ArgumentParser:
    out_csv_default, out_best_default = _default_outputs()
    parser = argparse.ArgumentParser(description="Parallel compute-only curated scan for pneumatic tuning")
    parser.add_argument("--candidate-json", default="", help="Optional JSON list of candidates; each item is either {name, overrides} or {name, ...params}.")
    parser.add_argument("--base-json", default=str(_default_base_json_path()), help="Base parameter JSON")
    parser.add_argument("--model-path", default=str(_default_model_path()), help="Worldroad model path")
    parser.add_argument("--road-csv", default="", help="Ring road CSV for archive scenario")
    parser.add_argument("--axay-csv", default="", help="Ring ax/ay CSV for archive scenario")
    parser.add_argument("--scenario-json", default="", help="Ring scenario JSON for archive scenario")
    parser.add_argument("--antiphase-only", action="store_true", help="Skip ring scenario and score on diagonal antiphase only")
    parser.add_argument("--workers", type=int, default=0, help="0=auto")
    parser.add_argument("--ring-dt", type=float, default=0.01)
    parser.add_argument("--antiphase-dt", type=float, default=0.005)
    parser.add_argument("--antiphase-t-end", type=float, default=4.0)
    parser.add_argument("--antiphase-amplitude-m", type=float, default=0.015)
    parser.add_argument("--antiphase-frequency-hz", type=float, default=1.5)
    parser.add_argument("--out-csv", default=str(out_csv_default))
    parser.add_argument("--best-json", default=str(out_best_default))
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    candidates = _load_candidates(args.candidate_json)
    if not candidates:
        raise SystemExit("No candidates to evaluate")

    workers = int(args.workers or 0)
    if workers <= 0:
        cpu_count = int(os.cpu_count() or 1)
        workers = max(1, min(len(candidates), cpu_count))

    config = {
        "base_json": str(Path(args.base_json).resolve()),
        "model_path": str(Path(args.model_path).resolve()),
        "road_csv": str(Path(args.road_csv).resolve()) if args.road_csv else "",
        "axay_csv": str(Path(args.axay_csv).resolve()) if args.axay_csv else "",
        "scenario_json": str(Path(args.scenario_json).resolve()) if args.scenario_json else "",
        "antiphase_only": bool(args.antiphase_only),
        "ring_dt": float(args.ring_dt),
        "antiphase_dt": float(args.antiphase_dt),
        "antiphase_t_end": float(args.antiphase_t_end),
        "antiphase_amplitude_m": float(args.antiphase_amplitude_m),
        "antiphase_frequency_hz": float(args.antiphase_frequency_hz),
    }

    started = time.perf_counter()
    tasks = [(config, candidate) for candidate in candidates]
    with ProcessPoolExecutor(max_workers=workers) as executor:
        rows = list(executor.map(_evaluate_candidate, tasks))
    elapsed = time.perf_counter() - started

    df = pd.DataFrame(rows).sort_values(["score", "penalty", "az_rms"], ascending=[True, True, True]).reset_index(drop=True)
    out_csv = Path(args.out_csv).resolve()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)

    best_json = Path(args.best_json).resolve()
    best_json.parent.mkdir(parents=True, exist_ok=True)
    best_name = str(df.iloc[0]["name"])
    best_candidate = next(item for item in candidates if str(item.get("name") or "") == best_name)
    best_json.write_text(json.dumps(best_candidate.get("overrides", {}), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"workers={workers}")
    print(f"elapsed_s={elapsed:.3f}")
    print(
        df[
            [
                "name",
                "score",
                "az_rms",
                "z_std",
                "roll_rms_deg",
                "pitch_rms_deg",
                "lift",
                "stroke_min",
                "stroke_max",
                "stroke_margin_min",
                "diag_to_exhaust_ratio",
            ]
        ].to_string(index=False)
    )
    print(f"out_csv={out_csv}")
    print(f"best_json={best_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
