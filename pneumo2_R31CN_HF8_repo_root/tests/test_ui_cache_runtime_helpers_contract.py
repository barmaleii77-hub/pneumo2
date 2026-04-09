from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.ui_cache_runtime_helpers import (
    build_runtime_baseline_cache_dir,
    load_runtime_detail_cache,
    save_runtime_baseline_cache,
)


def test_build_runtime_baseline_cache_dir_uses_workspace_and_model_content_hash(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "workspace"
    model_file = tmp_path / "model.py"
    model_file.write_text("print('hf8')\n", encoding="utf-8")

    out = build_runtime_baseline_cache_dir(
        workspace_dir,
        base_hash="base123",
        suite_hash="suite456",
        model_file=str(model_file),
        sanitize_id_fn=lambda value, max_len=32: str(value)[:max_len],
        stable_obj_hash_fn=lambda value: "fallbackhash",
    )

    assert out.parent == workspace_dir / "cache" / "baseline"
    assert out.name.startswith("base123_suite456_model_")
    assert "fallbackhash" not in out.name


def test_save_runtime_baseline_cache_forwards_optional_json_safe_and_log() -> None:
    calls: list[tuple[tuple, dict]] = []

    def _fake_save(*args, **kwargs):
        calls.append((args, kwargs))

    def _json_safe(value):
        return value

    def _log_event(*args, **kwargs):
        return None

    save_runtime_baseline_cache(
        Path("cache"),
        baseline_df="df",
        tests_map={"t": 1},
        base_override={"base": 1},
        meta={"m": 1},
        workspace_dir=Path("workspace"),
        save_baseline_cache_fn=_fake_save,
        log_event_fn=_log_event,
        json_safe_fn=_json_safe,
    )

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == (Path("cache"), "df", {"t": 1}, {"base": 1}, {"m": 1})
    assert kwargs["workspace_dir"] == Path("workspace")
    assert kwargs["log_event_fn"] is _log_event
    assert kwargs["json_safe_fn"] is _json_safe


def test_load_runtime_detail_cache_builds_resave_callback_from_runtime_save() -> None:
    observed: dict[str, object] = {}

    def _fake_save(*args, **kwargs):
        observed["resave_args"] = args
        return Path("saved.pkl.gz")

    def _fake_load(*args, **kwargs):
        observed["load_args"] = args
        observed["load_kwargs"] = kwargs
        observed["resave_result"] = kwargs["resave_payload_fn"]({"hello": "world"})
        return {"loaded": True}

    out = load_runtime_detail_cache(
        Path("cache"),
        "test-a",
        0.1,
        2.0,
        100,
        True,
        load_detail_cache_fn=_fake_load,
        resave_detail_cache_fn=_fake_save,
        sanitize_test_name=lambda value: value,
        load_payload_fn=lambda handle: {},
        float_tag_fn=lambda value: str(value),
        log_event_fn=lambda *args, **kwargs: None,
    )

    assert out == {"loaded": True}
    assert observed["resave_args"] == (
        Path("cache"),
        "test-a",
        0.1,
        2.0,
        100,
        True,
        {"hello": "world"},
    )
    assert observed["resave_result"] == Path("saved.pkl.gz")
