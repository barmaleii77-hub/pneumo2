from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def csv_data_row_count(path: Path) -> int:
    """Best-effort CSV data-row count without loading the full dataframe.

    Returns the number of rows excluding the header. On any parse/IO issue,
    returns 0 instead of raising — progress UI must stay fail-soft.
    """
    try:
        if not path.exists() or path.stat().st_size <= 0:
            return 0
    except Exception:
        return 0
    try:
        with path.open("rb") as f:
            line_count = 0
            for _ in f:
                line_count += 1
        return max(0, int(line_count) - 1)
    except Exception:
        return 0


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _stage_dirs(run_dir: Path) -> List[Tuple[str, Path]]:
    out: List[Tuple[str, Path]] = []
    try:
        for p in sorted(run_dir.iterdir()):
            if not p.is_dir():
                continue
            if p.name == "staging":
                continue
            if not (p.name.startswith("stage") or p.name.startswith("s")):
                continue
            csvs = sorted(list(p.glob("o*.csv")) or list(p.glob("stage_*.csv")))
            if not csvs:
                csvs = [c for c in sorted(p.glob("*.csv")) if c.name not in {"suite.json", "ranges.json"}]
            if csvs:
                out.append((p.name, csvs[0]))
    except Exception:
        pass
    return out


def summarize_staged_progress(progress_payload: Dict[str, Any], run_dir: Optional[Path]) -> Dict[str, Any]:
    """Derive user-facing staged optimization progress from files on disk.

    The staged runner progress file can be newer than nested worker progress and
    nested worker progress can remain stale during expensive baseline/seed
    prelude. This helper derives *live* counts from stage CSVs so UI can show
    real progress instead of zeros.
    """
    payload = dict(progress_payload or {})
    idx = int(payload.get("idx", 0) or 0)
    stage_total = int(payload.get("stage_total", 0) or 0)
    stage_name = str(payload.get("stage", "") or "")

    worker_out_csv = payload.get("worker_out_csv")
    current_csv: Optional[Path] = None
    if worker_out_csv:
        try:
            current_csv = Path(str(worker_out_csv))
        except Exception:
            current_csv = None

    stage_rows_map: Dict[str, int] = {}
    previous_rows = 0
    current_rows = 0
    live_stage_csvs: List[Tuple[str, str, int]] = []
    if run_dir is not None:
        for nm, csv_path in _stage_dirs(run_dir):
            rows = csv_data_row_count(csv_path)
            stage_rows_map[nm] = rows
            live_stage_csvs.append((nm, str(csv_path), rows))
    if current_csv is not None and current_csv.exists():
        current_rows = csv_data_row_count(current_csv)
        if stage_name:
            stage_rows_map[stage_name] = max(stage_rows_map.get(stage_name, 0), current_rows)
    elif stage_name:
        current_rows = int(stage_rows_map.get(stage_name, 0) or 0)

    if stage_rows_map:
        names = list(stage_rows_map.keys())
        if stage_name in names:
            if idx > 0:
                ordered = [n for n, _, _ in live_stage_csvs]
                if stage_name in ordered:
                    current_pos = ordered.index(stage_name)
                    previous_rows = sum(int(stage_rows_map.get(n, 0) or 0) for n in ordered[:current_pos])
                else:
                    previous_rows = sum(int(v or 0) for n, v in stage_rows_map.items() if n != stage_name)
            else:
                previous_rows = 0
        else:
            previous_rows = sum(int(v or 0) for v in stage_rows_map.values())

    worker_progress = payload.get("worker_progress") or {}
    try:
        worker_done = int(worker_progress.get("готово_кандидатов", 0) or 0)
    except Exception:
        worker_done = 0
    try:
        worker_written = int(worker_progress.get("готово_кандидатов_в_файле", worker_done) or worker_done)
    except Exception:
        worker_written = worker_done

    worker_done = max(worker_done, current_rows)
    worker_written = max(worker_written, current_rows)

    worker_progress_stale = False
    try:
        ts_last_write = float(worker_progress.get("ts_last_write", 0.0) or 0.0)
        if current_csv is not None and current_csv.exists() and ts_last_write > 0.0:
            worker_progress_stale = float(current_csv.stat().st_mtime) > (ts_last_write + 1.0)
    except Exception:
        worker_progress_stale = False

    stage_started_ts = payload.get("stage_started_ts")
    stage_budget_sec = payload.get("stage_budget_sec")
    stage_elapsed_sec = payload.get("stage_elapsed_sec")

    summary = {
        "stage": stage_name,
        "idx": idx,
        "stage_total": stage_total,
        "stage_rows_current": int(current_rows),
        "stage_rows_done_before": int(previous_rows),
        "total_rows_live": int(previous_rows + current_rows),
        "worker_done_current": int(worker_done),
        "worker_written_current": int(worker_written),
        "worker_progress_stale": bool(worker_progress_stale),
        "stage_started_ts": stage_started_ts,
        "stage_budget_sec": float(stage_budget_sec) if stage_budget_sec is not None else None,
        "stage_elapsed_sec": float(stage_elapsed_sec) if stage_elapsed_sec is not None else None,
        "live_stage_csvs": live_stage_csvs,
    }
    return summary
