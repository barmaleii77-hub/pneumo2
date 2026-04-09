from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable


def build_runtime_baseline_cache_dir(
    workspace_dir: Path,
    *,
    base_hash: str,
    suite_hash: str,
    model_file: str,
    sanitize_id_fn: Callable[..., str],
    stable_obj_hash_fn: Callable[[Any], str],
) -> Path:
    """Build the per-model baseline cache path used by large UI entrypoints."""
    try:
        mf = Path(model_file)
        model_tag = sanitize_id_fn(mf.stem, max_len=32)
        if mf.is_file():
            h = hashlib.sha1()
            with mf.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            model_hash = h.hexdigest()[:12]
        else:
            model_hash = stable_obj_hash_fn(str(mf.resolve()))
    except Exception:
        model_tag = "model"
        model_hash = stable_obj_hash_fn(str(model_file))
    key = f"{base_hash}_{suite_hash}_{model_tag}_{model_hash}"
    return workspace_dir / "cache" / "baseline" / key


def save_runtime_last_baseline_ptr(
    cache_dir: Path,
    meta: dict[str, Any],
    *,
    workspace_dir: Path,
    save_last_baseline_ptr_fn: Callable[..., None],
) -> None:
    return save_last_baseline_ptr_fn(cache_dir, meta, workspace_dir=workspace_dir)


def load_runtime_last_baseline_ptr(
    *,
    workspace_dir: Path,
    load_last_baseline_ptr_fn: Callable[..., dict[str, Any] | None],
) -> dict[str, Any] | None:
    return load_last_baseline_ptr_fn(workspace_dir=workspace_dir)


def load_runtime_baseline_cache(
    cache_dir: Path,
    *,
    load_baseline_cache_fn: Callable[[Path], dict[str, Any] | None],
) -> dict[str, Any] | None:
    return load_baseline_cache_fn(cache_dir)


def save_runtime_baseline_cache(
    cache_dir: Path,
    baseline_df: Any,
    tests_map: dict[str, Any],
    base_override: dict[str, Any],
    meta: dict[str, Any],
    *,
    workspace_dir: Path,
    save_baseline_cache_fn: Callable[..., None],
    log_event_fn: Callable[..., None] | None = None,
    json_safe_fn: Callable[[Any], Any] | None = None,
) -> None:
    kwargs: dict[str, Any] = {
        "workspace_dir": workspace_dir,
    }
    if log_event_fn is not None:
        kwargs["log_event_fn"] = log_event_fn
    if json_safe_fn is not None:
        kwargs["json_safe_fn"] = json_safe_fn
    return save_baseline_cache_fn(
        cache_dir,
        baseline_df,
        tests_map,
        base_override,
        meta,
        **kwargs,
    )


def save_runtime_detail_cache(
    cache_dir: Path,
    test_name: str,
    dt: float,
    t_end: float,
    max_points: int,
    want_full: bool,
    payload: dict[str, Any],
    *,
    save_detail_cache_fn: Callable[..., Path | None],
    sanitize_test_name: Callable[[str], str],
    dump_payload_fn: Callable[..., Any],
    float_tag_fn: Callable[[float], str],
    log_event_fn: Callable[..., None] | None = None,
) -> Path | None:
    kwargs: dict[str, Any] = {
        "sanitize_test_name": sanitize_test_name,
        "dump_payload_fn": dump_payload_fn,
        "float_tag_fn": float_tag_fn,
    }
    if log_event_fn is not None:
        kwargs["log_event_fn"] = log_event_fn
    return save_detail_cache_fn(
        cache_dir,
        test_name,
        dt,
        t_end,
        max_points,
        want_full,
        payload,
        **kwargs,
    )


def load_runtime_detail_cache(
    cache_dir: Path,
    test_name: str,
    dt: float,
    t_end: float,
    max_points: int,
    want_full: bool,
    *,
    load_detail_cache_fn: Callable[..., dict[str, Any] | None],
    resave_detail_cache_fn: Callable[..., Path | None],
    sanitize_test_name: Callable[[str], str],
    load_payload_fn: Callable[..., Any],
    float_tag_fn: Callable[[float], str],
    log_event_fn: Callable[..., None] | None = None,
) -> dict[str, Any] | None:
    def _resave_detail_payload(loaded_payload: dict[str, Any]) -> Path | None:
        return resave_detail_cache_fn(
            cache_dir,
            test_name,
            dt,
            t_end,
            max_points,
            want_full,
            loaded_payload,
        )

    kwargs: dict[str, Any] = {
        "sanitize_test_name": sanitize_test_name,
        "load_payload_fn": load_payload_fn,
        "resave_payload_fn": _resave_detail_payload,
        "float_tag_fn": float_tag_fn,
    }
    if log_event_fn is not None:
        kwargs["log_event_fn"] = log_event_fn
    return load_detail_cache_fn(
        cache_dir,
        test_name,
        dt,
        t_end,
        max_points,
        want_full,
        **kwargs,
    )
