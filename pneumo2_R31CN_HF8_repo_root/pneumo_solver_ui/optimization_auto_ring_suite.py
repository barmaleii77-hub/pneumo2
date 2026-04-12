from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import numpy as np
import pandas as pd


AUTO_RING_SUITE_SCHEMA_VERSION = "pneumo_opt_auto_ring_suite_v1"
AUTO_RING_SUITE_DIRNAME = "optimization_auto_ring_suite"
AUTO_RING_SUITE_FILENAME = "suite_auto_ring.json"
AUTO_RING_META_FILENAME = "suite_auto_ring_meta.json"

_STAGE0_SOURCE_NAMES: tuple[str, ...] = (
    "инерция_крен_ay3",
    "инерция_тангаж_ax3",
    "микро_синфаза",
    "микро_pitch",
    "микро_diagonal",
)

_STAGE1_SOURCE_NAMES: tuple[str, ...] = (
    "кочка_ЛП_короткая",
    "кочка_диагональ",
    "комбо_ay3_плюс_микро",
)

_DEFAULT_RING_TARGETS: dict[str, float] = {
    "target_макс_доля_отрыва": 0.25,
    "target_мин_запас_до_Pmid_бар": -0.2,
    "target_мин_Fmin_Н": 0.0,
    "target_мин_запас_до_упора_штока_м": 0.001,
    "target_лимит_скорости_штока_м_с": 3.0,
    "target_мин_зазор_пружина_цилиндр_м": 0.001,
    "target_мин_зазор_пружина_пружина_м": 0.001,
    "target_макс_ошибка_midstroke_t0_м": 0.03,
    "target_мин_запас_до_coil_bind_пружины_м": 0.003,
}

AUTO_STAGE_PARAMETER_HINTS: list[dict[str, Any]] = [
    {
        "stage_name": "stage0_relevance",
        "focus": [
            "пружина_*",
            "пружина_Ц1_*",
            "пружина_Ц2_*",
            "ход_штока_Ц1_*",
            "ход_штока_Ц2_*",
            "давление_Pmin_*",
            "давление_Pmid_*",
            "открытие_дросселя_Ц2_*",
        ],
        "note": "Быстрый скрининг жёсткости, хода штока, regulator/throttle поведения без тяжёлой геометрии.",
    },
    {
        "stage_name": "stage1_long",
        "focus": [
            "диаметр_поршня_Ц1",
            "диаметр_поршня_Ц2",
            "объём_ресивера_2",
            "объём_ресивера_3",
            "объём_аккумулятора",
            "низ_Ц1_*",
            "низ_Ц2_*",
        ],
        "note": "Основной тюнинг расходной пневматики: насосная ступень Ц1 отдельно от стабилизирующей Ц2.",
    },
    {
        "stage_name": "stage2_final",
        "focus": [
            "верх_Ц1_*",
            "верх_Ц2_*",
            "пружина_Ц1_*",
            "пружина_Ц2_*",
            "spring_*",
            "ход_штока_*",
        ],
        "note": "Финальный long-ring добор геометрии креплений и семейства пружин при сохранении лево/правой симметрии.",
    },
]


def _safe_float(value: Any, default: float) -> float:
    try:
        out = float(value)
        if out != out or out in (float("inf"), float("-inf")):
            return float(default)
        return out
    except Exception:
        return float(default)


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(Path(path))


def _detect_time_column(df: pd.DataFrame) -> str:
    for cand in ("t", "time", "время_с"):
        if cand in df.columns:
            return str(cand)
    return str(df.columns[0])


def _numeric_columns(df: pd.DataFrame, *, exclude: Iterable[str] = ()) -> list[str]:
    exclude_set = {str(x) for x in exclude}
    cols: list[str] = []
    for col in df.columns:
        if str(col) in exclude_set:
            continue
        try:
            arr = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
        except Exception:
            continue
        if np.isfinite(arr).any():
            cols.append(str(col))
    return cols


def _moving_rms(arr: np.ndarray, window: int) -> np.ndarray:
    if arr.size == 0:
        return np.zeros(0, dtype=float)
    win = max(1, min(int(window), int(arr.size)))
    kernel = np.ones(win, dtype=float) / float(win)
    return np.sqrt(np.convolve(np.square(arr), kernel, mode="same"))


def _moving_abs(arr: np.ndarray, window: int) -> np.ndarray:
    if arr.size == 0:
        return np.zeros(0, dtype=float)
    return _moving_rms(np.abs(arr), window)


def _scenario_segment_windows(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    segments = list(spec.get("segments") or [])
    windows: list[dict[str, Any]] = []
    t_cur = 0.0
    for idx, seg in enumerate(segments):
        if not isinstance(seg, Mapping):
            continue
        duration = _safe_float(seg.get("duration_s"), 0.0)
        if duration <= 0.0:
            continue
        start_s = float(t_cur)
        end_s = float(t_cur + duration)
        t_cur = end_s
        events = list(seg.get("events") or [])
        windows.append(
            {
                "segment_index": int(idx),
                "name": str(seg.get("name") or f"segment_{idx+1}"),
                "start_s": start_s,
                "end_s": end_s,
                "duration_s": float(duration),
                "turn_direction": str(seg.get("turn_direction") or "STRAIGHT"),
                "road_mode": str(((seg.get("road") or {}) if isinstance(seg.get("road"), Mapping) else {}).get("mode") or ""),
                "event_count": int(len(events)),
            }
        )
    return windows


def _extract_ring_basics(scenario_spec: Mapping[str, Any], axay_df: pd.DataFrame, axay_time_col: str) -> dict[str, float]:
    meta = dict(scenario_spec.get("_generated_meta") or {})
    v0_mps = max(0.0, _safe_float(scenario_spec.get("v0_kph"), 0.0) / 3.6)
    if v0_mps <= 0.0:
        ax_cols = _numeric_columns(axay_df, exclude=[axay_time_col])
        if ax_cols:
            v0_mps = max(0.0, _safe_float(axay_df[ax_cols[0]].iloc[0], 0.0))
    return {
        "dt_s": _safe_float(scenario_spec.get("dt_s"), _safe_float(meta.get("dt_s"), 0.01)),
        "lap_time_s": _safe_float(meta.get("lap_time_s"), _safe_float(axay_df[axay_time_col].iloc[-1], 0.0)),
        "ring_length_m": _safe_float(meta.get("ring_length_m"), v0_mps * _safe_float(meta.get("lap_time_s"), 0.0)),
        "v0_mps": float(v0_mps),
        "wheelbase_m": _safe_float(scenario_spec.get("wheelbase_m"), _safe_float(meta.get("wheelbase_m"), 1.5)),
        "track_m": _safe_float(scenario_spec.get("track_m"), _safe_float(meta.get("track_m"), 1.0)),
    }


def analyze_ring_windows(
    road_csv: str | Path,
    axay_csv: str | Path,
    scenario_json: str | Path,
    *,
    window_s: float = 4.0,
) -> dict[str, Any]:
    road_df = _read_csv(road_csv)
    axay_df = _read_csv(axay_csv)
    scenario_spec = _read_json(scenario_json)
    if not isinstance(scenario_spec, Mapping):
        scenario_spec = {}

    road_t_col = _detect_time_column(road_df)
    axay_t_col = _detect_time_column(axay_df)
    t = pd.to_numeric(road_df[road_t_col], errors="coerce").to_numpy(dtype=float)
    if t.size < 2:
        raise ValueError(f"road_csv must contain at least 2 time samples: {road_csv}")
    dt = float(np.nanmean(np.diff(t)))
    if not np.isfinite(dt) or dt <= 0.0:
        dt = max(1e-3, float(t[-1] - t[0]) / max(1, int(t.size) - 1))
    win_n = max(3, int(round(float(window_s) / max(1e-6, dt))))

    wheel_cols = _numeric_columns(road_df, exclude=[road_t_col])[:4]
    if len(wheel_cols) < 4:
        raise ValueError(f"road_csv must expose four wheel channels: {road_csv}")
    z = np.column_stack([pd.to_numeric(road_df[col], errors="coerce").to_numpy(dtype=float) for col in wheel_cols])
    z_mean = np.nanmean(z, axis=1)
    z_lr = 0.5 * ((z[:, 1] + z[:, 3]) - (z[:, 0] + z[:, 2]))
    z_diag = 0.5 * ((z[:, 1] + z[:, 2]) - (z[:, 0] + z[:, 3]))

    ax_cols = _numeric_columns(axay_df, exclude=[axay_t_col])
    ax = pd.to_numeric(axay_df[ax_cols[0]], errors="coerce").to_numpy(dtype=float) if len(ax_cols) >= 1 else np.zeros_like(t)
    ay = pd.to_numeric(axay_df[ax_cols[1]], errors="coerce").to_numpy(dtype=float) if len(ax_cols) >= 2 else np.zeros_like(t)
    t_ax = pd.to_numeric(axay_df[axay_t_col], errors="coerce").to_numpy(dtype=float)
    if t_ax.size != t.size or np.nanmax(np.abs(t_ax - t[: t_ax.size])) > max(1e-6, 0.25 * dt):
        ax = np.interp(t, t_ax, ax, left=float(ax[0]) if ax.size else 0.0, right=float(ax[-1]) if ax.size else 0.0)
        ay = np.interp(t, t_ax, ay, left=float(ay[0]) if ay.size else 0.0, right=float(ay[-1]) if ay.size else 0.0)

    metrics = {
        "rough": _moving_rms(z_mean - np.nanmean(z_mean), win_n),
        "diag": _moving_rms(z_diag, win_n),
        "roll": _moving_abs(ay, win_n),
        "pitch": _moving_abs(ax, win_n),
        "lr": _moving_rms(z_lr, win_n),
    }

    segment_windows = _scenario_segment_windows(scenario_spec)
    lap_time_s = _safe_float(t[-1], 0.0)
    ring_basics = _extract_ring_basics(scenario_spec, axay_df, axay_t_col)

    candidates: list[dict[str, Any]] = []
    seed_specs = [
        ("rough", "неровности"),
        ("diag", "диагональ"),
        ("roll", "крен"),
        ("pitch", "тангаж"),
    ]
    for key, label in seed_specs:
        arr = np.asarray(metrics[key], dtype=float)
        if arr.size == 0 or not np.isfinite(arr).any():
            continue
        idx = int(np.nanargmax(arr))
        center_s = float(t[min(idx, t.size - 1)])
        t_start = max(float(t[0]), center_s - 0.5 * float(window_s))
        t_end = min(float(t[-1]), t_start + float(window_s))
        t_start = max(float(t[0]), t_end - float(window_s))
        overlaps = [
            seg
            for seg in segment_windows
            if float(seg["end_s"]) > t_start and float(seg["start_s"]) < t_end
        ]
        candidates.append(
            {
                "id": f"ringfrag_{key}",
                "label": str(label),
                "kind": str(key),
                "peak_value": float(arr[idx]),
                "center_s": center_s,
                "t_start": float(t_start),
                "t_end": float(t_end),
                "duration_s": float(t_end - t_start),
                "segments": overlaps,
            }
        )

    def _candidate_rank(item: Mapping[str, Any]) -> tuple[float, float]:
        segs = list(item.get("segments") or [])
        event_count = sum(int(seg.get("event_count", 0) or 0) for seg in segs if isinstance(seg, Mapping))
        turn_bonus = sum(1 for seg in segs if isinstance(seg, Mapping) and str(seg.get("turn_direction") or "").upper() != "STRAIGHT")
        return (
            float(item.get("peak_value", 0.0) or 0.0) + 0.25 * float(event_count) + 0.15 * float(turn_bonus),
            float(item.get("center_s", 0.0) or 0.0),
        )

    return {
        "road_csv": str(Path(road_csv).resolve()),
        "axay_csv": str(Path(axay_csv).resolve()),
        "scenario_json": str(Path(scenario_json).resolve()),
        "dt_s": float(dt),
        "window_s": float(window_s),
        "wheel_columns": list(wheel_cols),
        "lap_time_s": float(lap_time_s),
        "ring_basics": ring_basics,
        "segment_windows": segment_windows,
        "fragment_windows": [dict(item) for item in sorted(candidates, key=_candidate_rank, reverse=True)],
    }


def _clip_and_rebase_timeseries_csv(
    src_path: str | Path,
    dst_path: str | Path,
    *,
    t_start: float,
    t_end: float,
) -> dict[str, Any]:
    src = Path(src_path).resolve()
    dst = Path(dst_path).resolve()
    df = _read_csv(src)
    t_col = _detect_time_column(df)
    t = pd.to_numeric(df[t_col], errors="coerce").to_numpy(dtype=float)
    if t.size < 2:
        raise ValueError(f"timeseries CSV must contain at least 2 rows: {src}")
    mask = (t >= float(t_start) - 1e-12) & (t <= float(t_end) + 1e-12)
    frag = df.loc[mask].copy()
    if len(frag) < 2:
        idx0 = int(np.searchsorted(t, float(t_start), side="left"))
        lo = max(0, idx0 - 1)
        hi = min(len(df), lo + 2)
        frag = df.iloc[lo:hi].copy()
    frag_t = pd.to_numeric(frag[t_col], errors="coerce").to_numpy(dtype=float)
    frag[t_col] = frag_t - float(frag_t[0])
    dst.parent.mkdir(parents=True, exist_ok=True)
    frag.to_csv(dst, index=False)
    return {
        "src": str(src),
        "dst": str(dst),
        "rows": int(len(frag)),
        "t_start_source_s": float(frag_t[0]),
        "t_end_source_s": float(frag_t[-1]),
        "duration_s": float(frag_t[-1] - frag_t[0]),
    }


def _ring_targets_from_source(rows_by_name: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    ring_row = rows_by_name.get("ring_город_неровная_дорога_20кмч_15s", {})
    targets = {k: v for k, v in dict(ring_row).items() if isinstance(k, str) and k.startswith("target_")}
    merged = dict(_DEFAULT_RING_TARGETS)
    merged.update(targets)
    return merged


def _source_suite_rows(suite_source_path: str | Path) -> list[dict[str, Any]]:
    raw = _read_json(suite_source_path)
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for rec in raw:
        if isinstance(rec, Mapping):
            out.append(dict(rec))
    return out


def _enable_source_row(rec: Mapping[str, Any], *, stage: int) -> dict[str, Any]:
    out = dict(rec)
    out["включен"] = True
    out["стадия"] = int(stage)
    return out


def build_optimization_auto_ring_suite_rows(
    workspace_dir: str | Path,
    *,
    suite_source_path: str | Path,
    road_csv: str | Path,
    axay_csv: str | Path,
    scenario_json: str | Path,
    window_s: float = 4.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workspace = Path(workspace_dir).resolve()
    root = workspace / "ui_state" / AUTO_RING_SUITE_DIRNAME
    fragment_dir = root / "fragments"
    fragment_dir.mkdir(parents=True, exist_ok=True)

    source_rows = _source_suite_rows(suite_source_path)
    rows_by_name = {str((row or {}).get("имя") or "").strip(): dict(row) for row in source_rows if isinstance(row, Mapping)}
    ring_targets = _ring_targets_from_source(rows_by_name)
    analysis = analyze_ring_windows(road_csv, axay_csv, scenario_json, window_s=window_s)
    ring_basics = dict(analysis.get("ring_basics") or {})

    suite_rows: list[dict[str, Any]] = []
    for name in _STAGE0_SOURCE_NAMES:
        rec = rows_by_name.get(name)
        if rec:
            suite_rows.append(_enable_source_row(rec, stage=0))
    for name in _STAGE1_SOURCE_NAMES:
        rec = rows_by_name.get(name)
        if rec:
            suite_rows.append(_enable_source_row(rec, stage=1))

    dt_s = _safe_float(analysis.get("dt_s"), 0.01)
    v0_mps = _safe_float(ring_basics.get("v0_mps"), 0.0)
    full_ring_row = {
        "имя": "ring_auto_full",
        "включен": True,
        "стадия": 2,
        "тип": "maneuver_csv",
        "dt": float(dt_s),
        "t_end": float(_safe_float(ring_basics.get("lap_time_s"), _safe_float(analysis.get("lap_time_s"), 0.0))),
        "vx0_м_с": float(v0_mps),
        "auto_t_end_from_len": False,
        "road_len_m": float(_safe_float(ring_basics.get("ring_length_m"), 0.0)),
        "road_csv": str(Path(road_csv).resolve()),
        "axay_csv": str(Path(axay_csv).resolve()),
        "scenario_json": str(Path(scenario_json).resolve()),
        "комментарий": "Полное пользовательское кольцо для финальной long-ring проверки кандидатов.",
        "track_m": float(_safe_float(ring_basics.get("track_m"), 1.0)),
        "wheelbase_m": float(_safe_float(ring_basics.get("wheelbase_m"), 1.5)),
    }
    full_ring_row.update(ring_targets)
    suite_rows.append(full_ring_row)

    fragment_meta: list[dict[str, Any]] = []
    for idx, frag in enumerate(list(analysis.get("fragment_windows") or [])):
        if not isinstance(frag, Mapping):
            continue
        frag_id = str(frag.get("id") or f"ringfrag_{idx+1}")
        road_out = fragment_dir / f"{frag_id}_road.csv"
        axay_out = fragment_dir / f"{frag_id}_axay.csv"
        meta_out = fragment_dir / f"{frag_id}_meta.json"
        road_info = _clip_and_rebase_timeseries_csv(
            road_csv,
            road_out,
            t_start=float(frag.get("t_start", 0.0)),
            t_end=float(frag.get("t_end", 0.0)),
        )
        axay_info = _clip_and_rebase_timeseries_csv(
            axay_csv,
            axay_out,
            t_start=float(frag.get("t_start", 0.0)),
            t_end=float(frag.get("t_end", 0.0)),
        )
        frag_meta = {
            "schema_version": AUTO_RING_SUITE_SCHEMA_VERSION,
            "source_ring": {
                "road_csv": str(Path(road_csv).resolve()),
                "axay_csv": str(Path(axay_csv).resolve()),
                "scenario_json": str(Path(scenario_json).resolve()),
            },
            "fragment": dict(frag),
            "road_clip": road_info,
            "axay_clip": axay_info,
        }
        meta_out.write_text(json.dumps(frag_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        fragment_meta.append(frag_meta)

        row = {
            "имя": str(frag_id),
            "включен": True,
            "стадия": 1,
            "тип": "maneuver_csv",
            "dt": float(dt_s),
            "t_end": float(_safe_float(frag.get("duration_s"), axay_info["duration_s"])),
            "vx0_м_с": float(v0_mps),
            "auto_t_end_from_len": False,
            "road_len_m": float(max(0.0, v0_mps * _safe_float(frag.get("duration_s"), 0.0))),
            "road_csv": str(road_out),
            "axay_csv": str(axay_out),
            "scenario_json": str(meta_out),
            "комментарий": (
                f"Автофрагмент кольца: {str(frag.get('label') or frag_id)}; "
                f"окно {float(frag.get('t_start', 0.0)):.2f}..{float(frag.get('t_end', 0.0)):.2f} s."
            ),
            "track_m": float(_safe_float(ring_basics.get("track_m"), 1.0)),
            "wheelbase_m": float(_safe_float(ring_basics.get("wheelbase_m"), 1.5)),
        }
        row.update(ring_targets)
        suite_rows.append(row)

    by_name: dict[str, dict[str, Any]] = {}
    for rec in suite_rows:
        name = str(rec.get("имя") or "").strip()
        if name and name not in by_name:
            by_name[name] = rec
    final_rows = list(by_name.values())

    meta = {
        "schema_version": AUTO_RING_SUITE_SCHEMA_VERSION,
        "workspace_dir": str(workspace),
        "suite_source_path": str(Path(suite_source_path).resolve()),
        "input_ring": {
            "road_csv": str(Path(road_csv).resolve()),
            "axay_csv": str(Path(axay_csv).resolve()),
            "scenario_json": str(Path(scenario_json).resolve()),
        },
        "analysis": analysis,
        "fragment_meta_files": [str(Path(item["scenario_json"]).resolve()) for item in final_rows if str(item.get("имя") or "").startswith("ringfrag_")],
        "recommended_stage_param_hints": AUTO_STAGE_PARAMETER_HINTS,
        "design_symmetry": "left_right_only",
        "cylinder_freedom": {
            "allow_c1_c2_split": True,
            "allow_front_rear_split": True,
            "allow_left_right_asymmetry": False,
        },
        "spring_layout_modes": [
            "separate_c1_c2_with_symmetry",
            "single_spring_per_corner_with_symmetry",
        ],
        "generated_row_count": int(len(final_rows)),
    }
    return final_rows, meta


def materialize_optimization_auto_ring_suite_json(
    workspace_dir: str | Path,
    *,
    suite_source_path: str | Path,
    road_csv: str | Path,
    axay_csv: str | Path,
    scenario_json: str | Path,
    window_s: float = 4.0,
) -> Path:
    workspace = Path(workspace_dir).resolve()
    root = workspace / "ui_state" / AUTO_RING_SUITE_DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    rows, meta = build_optimization_auto_ring_suite_rows(
        workspace,
        suite_source_path=suite_source_path,
        road_csv=road_csv,
        axay_csv=axay_csv,
        scenario_json=scenario_json,
        window_s=window_s,
    )
    suite_path = root / AUTO_RING_SUITE_FILENAME
    meta_path = root / AUTO_RING_META_FILENAME
    suite_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return suite_path
