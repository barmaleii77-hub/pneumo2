from __future__ import annotations

"""Shared cache/export helpers for large UI entrypoints."""

import gzip
import hashlib
import json
import os
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd


def pareto_front_2d(df: pd.DataFrame, obj1: str, obj2: str) -> pd.Series:
    """Boolean mask of non-dominated points for 2D minimization."""
    if len(df) == 0:
        return pd.Series([], dtype=bool)
    d = df[[obj1, obj2]].copy()
    d = d.replace([np.inf, -np.inf], np.nan).dropna()
    if len(d) == 0:
        return pd.Series([False] * len(df), index=df.index)
    d = d.sort_values(obj1, ascending=True)
    best2 = float("inf")
    keep_idx = []
    for idx, row in d.iterrows():
        v2 = float(row[obj2])
        if v2 < best2:
            keep_idx.append(idx)
            best2 = v2
    return df.index.isin(keep_idx)


def df_to_excel_bytes(sheets: dict) -> bytes:
    """Build an in-memory Excel file from {sheet_name: DataFrame}."""
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=str(name)[:31], index=False)
    bio.seek(0)
    return bio.read()


def stable_obj_hash(obj: Any) -> str:
    """Stable short hash for parameter/test payloads."""
    try:
        s = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        s = str(obj)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def float_tag(x: float) -> str:
    """Format float into a filesystem-friendly tag."""
    try:
        s = f"{float(x):.6g}"
    except Exception:
        s = str(x)
    return s.replace("-", "m").replace(".", "p")


def make_detail_cache_key(
    model_hash: str,
    test_name: str,
    dt: float,
    t_end: float,
    max_points: int,
    want_full: bool,
) -> str:
    """Canonical key for detail/full-cache entries."""
    return (
        f"{model_hash}::{test_name}::dt{float_tag(float(dt))}::t{float_tag(float(t_end))}"
        f"::mp{int(max_points)}::full{int(bool(want_full))}"
    )


def baseline_cache_meta_path(cache_dir: Path) -> Path:
    """Location of baseline metadata JSON inside a cache directory."""
    return cache_dir / "meta.json"


def baseline_cache_table_path(cache_dir: Path) -> Path:
    """Location of baseline summary CSV inside a cache directory."""
    return cache_dir / "baseline_table.csv"


def baseline_cache_tests_path(cache_dir: Path) -> Path:
    """Location of cached tests map JSON inside a cache directory."""
    return cache_dir / "tests_map.json"


def baseline_cache_base_path(cache_dir: Path) -> Path:
    """Location of cached base override JSON inside a cache directory."""
    return cache_dir / "base_override.json"


def baseline_cache_last_ptr_path(workspace_dir: Path) -> Path:
    """Global pointer to the most recently saved baseline cache."""
    return workspace_dir / "cache" / "baseline" / "_last_baseline.json"


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text via a temp file and replace to avoid partial caches."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)


def atomic_write_csv(path: Path, df: pd.DataFrame) -> None:
    """Write CSV via a temp file and replace to avoid partial caches."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def detail_cache_path(
    cache_dir: Path,
    test_name: str,
    dt: float,
    t_end: float,
    max_points: int,
    want_full: bool,
    *,
    sanitize_test_name: Callable[[str], str],
    float_tag_fn: Callable[[float], str] = float_tag,
) -> Path:
    """Canonical detail-cache filename with dt/t_end encoded in the path."""
    ddir = cache_dir / "detail"
    test_tag = sanitize_test_name(test_name)
    dt_tag = float_tag_fn(dt)
    te_tag = float_tag_fn(t_end)
    return ddir / f"{test_tag}__dt{dt_tag}__t{te_tag}__mp{int(max_points)}__full{int(bool(want_full))}.pkl.gz"


def legacy_detail_cache_path(
    cache_dir: Path,
    test_name: str,
    max_points: int,
    want_full: bool,
    *,
    sanitize_test_name: Callable[[str], str],
) -> Path:
    """Legacy detail-cache filename from releases without dt/t_end suffixes."""
    ddir = cache_dir / "detail"
    test_tag = sanitize_test_name(test_name)
    return ddir / f"{test_tag}__mp{int(max_points)}__full{int(bool(want_full))}.pkl.gz"


def save_last_baseline_ptr(
    cache_dir: Path,
    meta: dict[str, Any],
    *,
    workspace_dir: Path,
) -> None:
    """Persist a pointer to the most recently saved baseline cache."""
    try:
        pointer_path = baseline_cache_last_ptr_path(workspace_dir)
        pointer_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cache_dir": str(cache_dir),
            "ts": datetime.now().isoformat(timespec="seconds"),
            "meta": meta,
        }
        atomic_write_text(
            pointer_path,
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def load_last_baseline_ptr(*, workspace_dir: Path) -> Optional[dict[str, Any]]:
    """Load a pointer to the most recently saved baseline cache."""
    try:
        pointer_path = baseline_cache_last_ptr_path(workspace_dir)
        if not pointer_path.exists():
            return None
        return json.loads(pointer_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_baseline_cache(cache_dir: Path) -> Optional[dict[str, Any]]:
    """Load cached baseline artifacts if the cache is complete."""
    try:
        table_path = baseline_cache_table_path(cache_dir)
        tests_path = baseline_cache_tests_path(cache_dir)
        base_path = baseline_cache_base_path(cache_dir)
        if not (table_path.exists() and tests_path.exists() and base_path.exists()):
            return None
        baseline_df = pd.read_csv(table_path)
        tests_map = json.loads(tests_path.read_text(encoding="utf-8"))
        base_override = json.loads(base_path.read_text(encoding="utf-8"))
        meta_path = baseline_cache_meta_path(cache_dir)
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        return {
            "baseline_df": baseline_df,
            "tests_map": tests_map,
            "base_override": base_override,
            "meta": meta,
        }
    except Exception:
        return None


def save_baseline_cache(
    cache_dir: Path,
    baseline_df: pd.DataFrame,
    tests_map: dict[str, Any],
    base_override: dict[str, Any],
    meta: dict[str, Any],
    *,
    workspace_dir: Path,
    json_safe_fn: Optional[Callable[[Any], Any]] = None,
    log_event_fn: Optional[Callable[..., None]] = None,
) -> None:
    """Persist baseline artifacts atomically with an optional JSON sanitizer."""
    try:
        sanitize = json_safe_fn or (lambda value: value)
        cache_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_csv(baseline_cache_table_path(cache_dir), baseline_df)
        atomic_write_text(
            baseline_cache_tests_path(cache_dir),
            json.dumps(sanitize(tests_map), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        atomic_write_text(
            baseline_cache_base_path(cache_dir),
            json.dumps(sanitize(base_override), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        atomic_write_text(
            baseline_cache_meta_path(cache_dir),
            json.dumps(sanitize(meta), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        save_last_baseline_ptr(cache_dir, meta, workspace_dir=workspace_dir)
    except Exception as exc:
        if log_event_fn is not None:
            try:
                log_event_fn("baseline_cache_save_error", error=str(exc), cache_dir=str(cache_dir))
            except Exception:
                pass


def save_detail_cache_payload(
    cache_dir: Path,
    test_name: str,
    dt: float,
    t_end: float,
    max_points: int,
    want_full: bool,
    payload: dict[str, Any],
    *,
    sanitize_test_name: Callable[[str], str],
    dump_payload_fn: Callable[[Any, dict[str, Any]], None],
    float_tag_fn: Callable[[float], str] = float_tag,
    log_event_fn: Optional[Callable[..., None]] = None,
) -> Optional[Path]:
    """Persist detail-cache payload via a serializer provided by the caller."""
    cache_path = detail_cache_path(
        cache_dir,
        test_name,
        dt,
        t_end,
        max_points,
        want_full,
        sanitize_test_name=sanitize_test_name,
        float_tag_fn=float_tag_fn,
    )
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        with gzip.open(tmp_path, "wb") as handle:
            dump_payload_fn(handle, payload)
        os.replace(tmp_path, cache_path)
        return cache_path
    except Exception as exc:
        try:
            if "tmp_path" in locals() and Path(tmp_path).exists():
                Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass
        try:
            if cache_path.exists():
                bad_path = cache_path.with_suffix(cache_path.suffix + f".bad{int(time.time())}")
                try:
                    os.replace(cache_path, bad_path)
                except Exception:
                    pass
        except Exception:
            pass
        if log_event_fn is not None:
            try:
                log_event_fn(
                    "detail_cache_save_error",
                    test=str(test_name),
                    dt=float(dt),
                    t_end=float(t_end),
                    max_points=int(max_points),
                    want_full=bool(want_full),
                    error=str(exc),
                )
            except Exception:
                pass
        return None


def load_detail_cache_payload(
    cache_dir: Path,
    test_name: str,
    dt: float,
    t_end: float,
    max_points: int,
    want_full: bool,
    *,
    sanitize_test_name: Callable[[str], str],
    load_payload_fn: Callable[[Any], dict[str, Any]],
    resave_payload_fn: Optional[Callable[[dict[str, Any]], Optional[Path]]] = None,
    float_tag_fn: Callable[[float], str] = float_tag,
    log_event_fn: Optional[Callable[..., None]] = None,
) -> Optional[dict[str, Any]]:
    """Load detail-cache payload, with optional legacy migration and quarantine."""
    cache_path = detail_cache_path(
        cache_dir,
        test_name,
        dt,
        t_end,
        max_points,
        want_full,
        sanitize_test_name=sanitize_test_name,
        float_tag_fn=float_tag_fn,
    )
    legacy_path = legacy_detail_cache_path(
        cache_dir,
        test_name,
        max_points,
        want_full,
        sanitize_test_name=sanitize_test_name,
    )
    for path in [cache_path, legacy_path]:
        if not path.exists():
            continue
        try:
            with gzip.open(path, "rb") as handle:
                payload = load_payload_fn(handle)
            if path == legacy_path and not cache_path.exists() and resave_payload_fn is not None:
                try:
                    resave_payload_fn(payload)
                except Exception:
                    pass
            return payload
        except Exception as exc:
            if log_event_fn is not None:
                try:
                    log_event_fn(
                        "detail_cache_load_error",
                        test=str(test_name),
                        dt=float(dt),
                        t_end=float(t_end),
                        max_points=int(max_points),
                        want_full=bool(want_full),
                        path=str(path),
                        error=str(exc),
                    )
                except Exception:
                    pass
            try:
                bad_path = path.with_suffix(path.suffix + f".bad{int(time.time())}")
                os.replace(path, bad_path)
            except Exception:
                pass
            return None
    return None


__all__ = [
    "atomic_write_csv",
    "atomic_write_text",
    "baseline_cache_base_path",
    "baseline_cache_last_ptr_path",
    "baseline_cache_meta_path",
    "baseline_cache_table_path",
    "baseline_cache_tests_path",
    "df_to_excel_bytes",
    "detail_cache_path",
    "float_tag",
    "legacy_detail_cache_path",
    "load_baseline_cache",
    "load_detail_cache_payload",
    "load_last_baseline_ptr",
    "make_detail_cache_key",
    "pareto_front_2d",
    "save_baseline_cache",
    "save_detail_cache_payload",
    "save_last_baseline_ptr",
    "stable_obj_hash",
]
