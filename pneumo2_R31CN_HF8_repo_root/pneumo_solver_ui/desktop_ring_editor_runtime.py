from __future__ import annotations

import json
import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .desktop_ring_editor_model import (
    build_segment_flow_rows,
    safe_float,
    safe_int,
)
from .optimization_auto_ring_suite import (
    _STAGE0_SOURCE_NAMES,
    _STAGE1_SOURCE_NAMES,
    AUTO_RING_META_FILENAME,
    analyze_ring_windows,
    materialize_optimization_auto_ring_suite_json,
)
from .optimization_defaults import canonical_suite_json_path
from .ring_visuals import build_ring_visual_payload_from_spec
from .run_artifacts import local_anim_latest_export_paths
from .scenario_ring import (
    _resolve_initial_speed_kph,
    generate_ring_drive_profile,
    generate_ring_scenario_bundle,
    generate_ring_tracks,
    summarize_ring_track_segments,
    validate_ring_spec,
)


PREVIEW_COLORS = (
    "#3b82f6",
    "#f97316",
    "#10b981",
    "#ef4444",
    "#8b5cf6",
    "#eab308",
    "#06b6d4",
    "#f43f5e",
)

ANIM_LATEST_RING_EXPORT_NAMES: dict[str, str] = {
    "road_csv": "anim_latest_road_csv.csv",
    "axay_csv": "anim_latest_axay_csv.csv",
    "scenario_json": "anim_latest_scenario_json.json",
}


@dataclass(frozen=True)
class RingPreviewSegment:
    index: int
    name: str
    color: str
    start_fraction: float
    end_fraction: float
    turn_direction: str
    road_mode: str
    event_count: int


@dataclass(frozen=True)
class RingRoadProfilePreview:
    x_m: tuple[float, ...]
    left_mm: tuple[float, ...]
    right_mm: tuple[float, ...]


@dataclass
class RingEditorDiagnostics:
    errors: list[str]
    warnings: list[str]
    metrics: dict[str, float | str]
    segment_rows: list[dict[str, Any]]
    preview_segments: list[RingPreviewSegment]
    road_profile: RingRoadProfilePreview | None
    summary_text: str


def _safe_end_speed_kph(segment_rows: list[dict[str, Any]], start_speed_kph: float) -> float:
    if not segment_rows:
        return float(start_speed_kph)
    return float(segment_rows[-1].get("speed_end_kph", start_speed_kph))


def _build_preview_segments(
    segment_rows: list[dict[str, Any]],
    ring_length_m: float,
    visual_segments: list[dict[str, Any]] | None = None,
) -> list[RingPreviewSegment]:
    if not segment_rows:
        return []

    ring_length_m = max(1e-9, float(ring_length_m))
    visual_by_index = {
        int(segment.get("seg_idx", 0)) - 1: segment
        for segment in (visual_segments or [])
        if isinstance(segment, dict)
    }
    segments: list[RingPreviewSegment] = []
    cursor = 0.0
    for index, row in enumerate(segment_rows):
        length_m = max(0.0, safe_float(row.get("length_m", 0.0), 0.0))
        visual = dict(visual_by_index.get(index) or {})
        start_m = safe_float(visual.get("x_start_m", cursor), cursor)
        end_m = safe_float(visual.get("x_end_m", start_m + length_m), start_m + length_m)
        if end_m <= start_m:
            end_m = start_m + length_m
        cursor = end_m
        color = str(visual.get("edge_color") or PREVIEW_COLORS[index % len(PREVIEW_COLORS)])
        segments.append(
            RingPreviewSegment(
                index=index,
                name=str(row.get("name") or f"S{index + 1}"),
                color=color,
                start_fraction=max(0.0, min(1.0, start_m / ring_length_m)),
                end_fraction=max(0.0, min(1.0, end_m / ring_length_m)),
                turn_direction=str(row.get("turn_direction") or "STRAIGHT"),
                road_mode=str(row.get("road_mode") or "ISO8608"),
                event_count=int(row.get("event_count", 0) or 0),
            )
        )
    return segments


def _downsample_profile_indices(size: int, *, limit: int = 1600) -> np.ndarray:
    if size <= max(2, limit):
        return np.arange(size, dtype=int)
    idx = np.linspace(0, size - 1, num=limit, dtype=int)
    return np.unique(idx)


def _build_road_profile_preview(tracks: dict[str, Any]) -> RingRoadProfilePreview | None:
    x = np.asarray(tracks.get("x_m", []), dtype=float).reshape(-1)
    z_left = np.asarray(tracks.get("zL_m", []), dtype=float).reshape(-1)
    z_right = np.asarray(tracks.get("zR_m", []), dtype=float).reshape(-1)
    if x.size < 2 or z_left.size != x.size or z_right.size != x.size:
        return None
    pick = _downsample_profile_indices(int(x.size))
    x_pick = np.asarray(x[pick], dtype=float).reshape(-1)
    z_left_pick = np.asarray(z_left[pick], dtype=float).reshape(-1)
    z_right_pick = np.asarray(z_right[pick], dtype=float).reshape(-1)
    return RingRoadProfilePreview(
        x_m=tuple(float(value) for value in x_pick),
        left_mm=tuple(float(value) * 1000.0 for value in z_left_pick),
        right_mm=tuple(float(value) * 1000.0 for value in z_right_pick),
    )


def _build_summary_text(errors: list[str], warnings: list[str], metrics: dict[str, float | str]) -> str:
    lines: list[str] = []
    lines.append("Сводка кольца")
    lines.append(
        "Длина круга ≈ "
        f"{float(metrics.get('ring_length_m', 0.0) or 0.0):.2f} м, "
        f"длительность круга {float(metrics.get('lap_time_s', 0.0) or 0.0):.2f} с, "
        f"всего {float(metrics.get('total_time_s', 0.0) or 0.0):.2f} с."
    )
    lines.append(
        "Скорость start→end: "
        f"{float(metrics.get('start_speed_kph', 0.0) or 0.0):.2f} → "
        f"{float(metrics.get('end_speed_kph', 0.0) or 0.0):.2f} км/ч."
    )
    lines.append(
        "Шов дороги L/R/max: "
        f"{float(metrics.get('seam_left_mm', 0.0) or 0.0):.2f} / "
        f"{float(metrics.get('seam_right_mm', 0.0) or 0.0):.2f} / "
        f"{float(metrics.get('seam_max_mm', 0.0) or 0.0):.2f} мм."
    )
    lines.append(
        "Whole-ring amplitude A L/R: "
        f"{float(metrics.get('ring_amp_left_mm', 0.0) or 0.0):.2f} / "
        f"{float(metrics.get('ring_amp_right_mm', 0.0) or 0.0):.2f} мм; "
        "p-p L/R: "
        f"{float(metrics.get('ring_p2p_left_mm', 0.0) or 0.0):.2f} / "
        f"{float(metrics.get('ring_p2p_right_mm', 0.0) or 0.0):.2f} мм."
    )
    lines.append(f"Режим замыкания: {str(metrics.get('closure_policy', ''))}.")

    if errors:
        lines.append("")
        lines.append("Ошибки:")
        lines.extend(f"- {item}" for item in errors)
    if warnings:
        lines.append("")
        lines.append("Предупреждения:")
        lines.extend(f"- {item}" for item in warnings)
    return "\n".join(lines)


def build_ring_editor_diagnostics(spec: dict[str, Any]) -> RingEditorDiagnostics:
    report = validate_ring_spec(spec)
    errors = list(report.get("errors", []) or [])
    warnings = list(report.get("warnings", []) or [])
    flow_rows = build_segment_flow_rows(spec)
    segment_rows = list(flow_rows)

    lap_time_s = float(sum(max(0.0, safe_float(segment.get("duration_s", 0.0), 0.0)) for segment in list(spec.get("segments", []) or [])))
    total_time_s = lap_time_s * max(1, safe_int(spec.get("n_laps", 1), 1))
    start_speed_kph = float(_resolve_initial_speed_kph(spec))
    end_speed_kph = _safe_end_speed_kph(segment_rows, start_speed_kph)

    ring_length_m = float(sum(float(row.get("length_m", 0.0) or 0.0) for row in segment_rows))
    seam_left_mm = 0.0
    seam_right_mm = 0.0
    seam_max_mm = 0.0
    ring_amp_left_mm = 0.0
    ring_amp_right_mm = 0.0
    ring_p2p_left_mm = 0.0
    ring_p2p_right_mm = 0.0
    closure_policy = str(spec.get("closure_policy", "closed_c1_periodic") or "closed_c1_periodic")
    visual_segments: list[dict[str, Any]] = []
    road_profile: RingRoadProfilePreview | None = None

    if not errors:
        try:
            tracks = generate_ring_tracks(
                spec,
                dx_m=float(max(1e-4, safe_float(spec.get("dx_m", 0.02), 0.02))),
                seed=safe_int(spec.get("seed", 123), 123),
            )
            ring_length_m = float((tracks.get("meta", {}) or {}).get("L_total_m", ring_length_m) or ring_length_m)
            z_left = np.asarray(tracks.get("zL_m", []), dtype=float).reshape(-1)
            z_right = np.asarray(tracks.get("zR_m", []), dtype=float).reshape(-1)
            road_profile = _build_road_profile_preview(tracks)
            if z_left.size >= 2 and z_right.size >= 2:
                seam_left_mm = float(abs(z_left[-1] - z_left[0]) * 1000.0)
                seam_right_mm = float(abs(z_right[-1] - z_right[0]) * 1000.0)
                seam_max_mm = float(max(seam_left_mm, seam_right_mm))
                z_left_median = float(np.nanmedian(z_left))
                z_right_median = float(np.nanmedian(z_right))
                ring_amp_left_mm = float(np.nanmax(np.abs(z_left - z_left_median)) * 1000.0)
                ring_amp_right_mm = float(np.nanmax(np.abs(z_right - z_right_median)) * 1000.0)
                ring_p2p_left_mm = float((np.nanmax(z_left) - np.nanmin(z_left)) * 1000.0)
                ring_p2p_right_mm = float((np.nanmax(z_right) - np.nanmin(z_right)) * 1000.0)
            closure_policy = str((tracks.get("meta", {}) or {}).get("closure_policy", closure_policy) or closure_policy)
            summarized_rows = summarize_ring_track_segments(spec, tracks)
            for index, row in enumerate(summarized_rows):
                flow_row = flow_rows[index] if 0 <= index < len(flow_rows) else {}
                row["event_count"] = int(flow_row.get("event_count", 0) or 0)
                row["index"] = int(flow_row.get("index", index) or index)
                row["uid"] = str(flow_row.get("uid", "") or "")
            segment_rows = summarized_rows
            drive = generate_ring_drive_profile(
                spec,
                dt_s=max(0.001, safe_float(spec.get("dt_s", 0.01), 0.01)),
                n_laps=1,
            )
            drive_end = np.asarray(drive.get("v_mps", []), dtype=float).reshape(-1)
            if drive_end.size:
                end_speed_kph = float(drive_end[-1] * 3.6)

            visual = build_ring_visual_payload_from_spec(
                spec,
                track_m=max(0.1, safe_float(spec.get("track_m", 1.0), 1.0)),
                wheel_width_m=0.18,
                seed=safe_int(spec.get("seed", 123), 123),
            )
            if isinstance(visual, dict):
                visual_segments = list(visual.get("segments", []) or [])
        except Exception as exc:
            warnings.append(f"Предпросмотр кольца собран частично: {exc}")

    preview_segments = _build_preview_segments(segment_rows, ring_length_m, visual_segments)
    metrics: dict[str, float | str] = {
        "ring_length_m": float(ring_length_m),
        "lap_time_s": float(lap_time_s),
        "total_time_s": float(total_time_s),
        "start_speed_kph": float(start_speed_kph),
        "end_speed_kph": float(end_speed_kph),
        "seam_left_mm": float(seam_left_mm),
        "seam_right_mm": float(seam_right_mm),
        "seam_max_mm": float(seam_max_mm),
        "ring_amp_left_mm": float(ring_amp_left_mm),
        "ring_amp_right_mm": float(ring_amp_right_mm),
        "ring_p2p_left_mm": float(ring_p2p_left_mm),
        "ring_p2p_right_mm": float(ring_p2p_right_mm),
        "closure_policy": str(closure_policy),
    }
    summary_text = _build_summary_text(errors, warnings, metrics)
    return RingEditorDiagnostics(
        errors=errors,
        warnings=warnings,
        metrics=metrics,
        segment_rows=list(segment_rows),
        preview_segments=preview_segments,
        road_profile=road_profile,
        summary_text=summary_text,
    )


def export_ring_scenario_bundle(spec: dict[str, Any], *, output_dir: str | Path, tag: str) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return generate_ring_scenario_bundle(
        spec,
        out_dir=out_dir,
        dt_s=max(0.001, safe_float(spec.get("dt_s", 0.01), 0.01)),
        n_laps=max(1, safe_int(spec.get("n_laps", 1), 1)),
        wheelbase_m=max(0.01, safe_float(spec.get("wheelbase_m", 1.5), 1.5)),
        dx_m=max(1e-4, safe_float(spec.get("dx_m", 0.02), 0.02)),
        seed=safe_int(spec.get("seed", 123), 123),
        tag=str(tag or "ring"),
    )


def mirror_ring_bundle_to_anim_latest_exports(
    bundle: dict[str, Any],
    *,
    exports_dir: str | Path | None = None,
) -> dict[str, str]:
    local_npz, _local_pointer = local_anim_latest_export_paths(
        Path(exports_dir) if exports_dir is not None else None,
        ensure_exists=True,
    )
    target_dir = local_npz.parent
    mirrored: dict[str, str] = {}
    for source_key, target_name in ANIM_LATEST_RING_EXPORT_NAMES.items():
        source_raw = str(bundle.get(source_key) or "").strip()
        if not source_raw:
            raise ValueError(f"Bundle does not contain required field: {source_key}")
        source_path = Path(source_raw).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Bundle source is missing for {source_key}: {source_path}")
        target_path = (target_dir / target_name).resolve()
        shutil.copy2(source_path, target_path)
        mirrored[source_key] = str(target_path)
    return mirrored


def build_ring_bundle_optimization_preview(
    bundle: dict[str, Any],
    *,
    window_s: float = 4.0,
) -> list[dict[str, Any]]:
    road_csv = Path(
        str(bundle.get("anim_latest_road_csv") or bundle.get("road_csv") or "")
    ).expanduser().resolve()
    axay_csv = Path(
        str(bundle.get("anim_latest_axay_csv") or bundle.get("axay_csv") or "")
    ).expanduser().resolve()
    scenario_json = Path(
        str(bundle.get("anim_latest_scenario_json") or bundle.get("scenario_json") or "")
    ).expanduser().resolve()
    for label, path in (
        ("road_csv", road_csv),
        ("axay_csv", axay_csv),
        ("scenario_json", scenario_json),
    ):
        if not path.exists():
            raise FileNotFoundError(f"Required path is missing for {label}: {path}")

    analysis = analyze_ring_windows(
        road_csv,
        axay_csv,
        scenario_json,
        window_s=float(max(0.5, window_s)),
    )
    rows: list[dict[str, Any]] = []
    for frag in list(analysis.get("fragment_windows") or []):
        if not isinstance(frag, dict):
            continue
        segments = [dict(item) for item in list(frag.get("segments") or []) if isinstance(item, dict)]
        seg_names = [str(item.get("name") or f"S{int(item.get('segment_index', 0)) + 1}") for item in segments]
        event_count = sum(int(item.get("event_count", 0) or 0) for item in segments)
        rows.append(
            {
                "id": str(frag.get("id") or ""),
                "label": str(frag.get("label") or ""),
                "kind": str(frag.get("kind") or ""),
                "t_start_s": float(frag.get("t_start", 0.0) or 0.0),
                "t_end_s": float(frag.get("t_end", 0.0) or 0.0),
                "duration_s": float(frag.get("duration_s", 0.0) or 0.0),
                "peak_value": float(frag.get("peak_value", 0.0) or 0.0),
                "segment_count": int(len(segments)),
                "event_count": int(event_count),
                "segments_text": ", ".join(seg_names),
            }
        )
    return rows


def build_ring_bundle_optimization_suite_preview(
    bundle: dict[str, Any],
    *,
    window_s: float = 4.0,
    suite_source_path: str | Path | None = None,
) -> dict[str, Any]:
    ui_root = Path(__file__).resolve().parent
    source_suite = (
        Path(suite_source_path).expanduser().resolve()
        if suite_source_path is not None
        else canonical_suite_json_path(ui_root)
    )
    available_names: set[str] = set()
    try:
        raw = json.loads(source_suite.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    name = str(item.get("имя") or "").strip()
                    if name:
                        available_names.add(name)
    except Exception:
        available_names = set()

    def _enabled(names: tuple[str, ...]) -> list[str]:
        if not available_names:
            return list(names)
        return [name for name in names if name in available_names]

    stage0_rows = _enabled(_STAGE0_SOURCE_NAMES)
    stage1_seed_rows = _enabled(_STAGE1_SOURCE_NAMES)
    fragment_rows = build_ring_bundle_optimization_preview(bundle, window_s=window_s)
    suite_rows: list[dict[str, Any]] = []
    suite_rows.extend({"stage": 0, "name": name, "kind": "seed"} for name in stage0_rows)
    suite_rows.extend({"stage": 1, "name": name, "kind": "seed"} for name in stage1_seed_rows)
    suite_rows.extend(
        {
            "stage": 1,
            "name": str(row.get("id") or ""),
            "kind": "fragment",
            "label": str(row.get("label") or ""),
        }
        for row in fragment_rows
    )
    suite_rows.append({"stage": 2, "name": "ring_auto_full", "kind": "full"})
    stage_counts = {
        "stage0_seed_count": int(len(stage0_rows)),
        "stage1_seed_count": int(len(stage1_seed_rows)),
        "fragment_count": int(len(fragment_rows)),
        "stage2_full_count": 1,
        "total_count": int(len(suite_rows)),
    }
    summary_text = (
        f"stage0 seeds={stage_counts['stage0_seed_count']} | "
        f"stage1 seeds={stage_counts['stage1_seed_count']} | "
        f"fragments={stage_counts['fragment_count']} | "
        f"stage2 full={stage_counts['stage2_full_count']} | "
        f"total={stage_counts['total_count']}"
    )
    return {
        "suite_source_json": str(source_suite),
        "stage_counts": stage_counts,
        "fragment_rows": fragment_rows,
        "suite_rows": suite_rows,
        "summary_text": summary_text,
    }


def materialize_ring_bundle_optimization_suite(
    bundle: dict[str, Any],
    *,
    workspace_dir: str | Path | None = None,
    suite_source_path: str | Path | None = None,
    window_s: float = 4.0,
) -> dict[str, str | int | float]:
    ui_root = Path(__file__).resolve().parent
    workspace = (
        Path(workspace_dir).expanduser().resolve()
        if workspace_dir is not None
        else Path(os.environ.get("PNEUMO_WORKSPACE_DIR") or (ui_root / "workspace")).expanduser().resolve()
    )
    source_suite = (
        Path(suite_source_path).expanduser().resolve()
        if suite_source_path is not None
        else canonical_suite_json_path(ui_root)
    )
    road_csv = Path(
        str(bundle.get("anim_latest_road_csv") or bundle.get("road_csv") or "")
    ).expanduser().resolve()
    axay_csv = Path(
        str(bundle.get("anim_latest_axay_csv") or bundle.get("axay_csv") or "")
    ).expanduser().resolve()
    scenario_json = Path(
        str(bundle.get("anim_latest_scenario_json") or bundle.get("scenario_json") or "")
    ).expanduser().resolve()
    for label, path in (
        ("road_csv", road_csv),
        ("axay_csv", axay_csv),
        ("scenario_json", scenario_json),
        ("suite_source_path", source_suite),
    ):
        if not path.exists():
            raise FileNotFoundError(f"Required path is missing for {label}: {path}")

    suite_path = materialize_optimization_auto_ring_suite_json(
        workspace,
        suite_source_path=source_suite,
        road_csv=road_csv,
        axay_csv=axay_csv,
        scenario_json=scenario_json,
        window_s=float(max(0.5, window_s)),
    )
    meta_path = suite_path.with_name(AUTO_RING_META_FILENAME)
    row_count = 0
    try:
        rows_obj = json.loads(suite_path.read_text(encoding="utf-8"))
        if isinstance(rows_obj, list):
            row_count = len(rows_obj)
    except Exception:
        row_count = 0
    return {
        "workspace_dir": str(workspace),
        "suite_source_json": str(source_suite),
        "suite_json": str(suite_path),
        "suite_meta_json": str(meta_path),
        "window_s": float(max(0.5, window_s)),
        "generated_row_count": int(row_count),
    }
