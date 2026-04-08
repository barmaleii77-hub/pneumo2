from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pneumo_solver_ui.optimization_stage_runtime_block import (
    load_json_dict,
    render_stage_policy_runtime_block,
)


def test_stage_runtime_block_load_json_dict_handles_missing_and_invalid(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    invalid = tmp_path / "invalid.json"
    invalid.write_text("[1, 2, 3]", encoding="utf-8")

    assert load_json_dict(missing) == {}
    assert load_json_dict(invalid) == {}


def test_stage_runtime_block_renders_snapshot_from_progress_payload(tmp_path: Path) -> None:
    progress = tmp_path / "sp.json"
    progress.write_text('{"stage":"stage1_long","idx":1}', encoding="utf-8")
    job = SimpleNamespace(progress_path=progress, run_dir=tmp_path)
    events: list[tuple[str, object]] = []

    render_stage_policy_runtime_block(
        object(),
        job,
        summarize_progress_fn=lambda payload, run_dir: {"stage_rows_current": 7, "run_dir": str(run_dir), "stage": payload["stage"]},
        summarize_policy_fn=lambda run_dir, **kwargs: {"policy_name": "focus", "stage_idx": kwargs["stage_idx"], "stage_name": kwargs["stage_name"], "run_dir": str(run_dir)},
        render_snapshot_fn=lambda _st, **kwargs: events.append(
            ("snapshot", kwargs["progress_payload"], kwargs["staged_summary"], kwargs["policy"])
        ),
    )

    assert events == [
        (
            "snapshot",
            {"stage": "stage1_long", "idx": 1},
            {"stage_rows_current": 7, "run_dir": str(tmp_path), "stage": "stage1_long"},
            {"policy_name": "focus", "stage_idx": 1, "stage_name": "stage1_long", "run_dir": str(tmp_path)},
        )
    ]
