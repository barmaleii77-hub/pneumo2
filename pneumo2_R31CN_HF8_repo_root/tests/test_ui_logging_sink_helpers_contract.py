from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.ui_logging_runtime_helpers import append_ui_log_lines


ROOT = Path(__file__).resolve().parents[1]


def test_append_ui_log_lines_writes_session_and_combined_outputs(tmp_path: Path) -> None:
    append_ui_log_lines(
        tmp_path,
        session_id="S1",
        session_metrics_line='{"event":"session"}',
        combined_metrics_line='{"event":"combined"}',
        combined_text_line='{"event":"text"}',
    )

    assert (tmp_path / "metrics_S1.jsonl").read_text(encoding="utf-8").strip() == '{"event":"session"}'
    assert (tmp_path / "metrics_combined.jsonl").read_text(encoding="utf-8").strip() == '{"event":"combined"}'
    assert (tmp_path / "ui_combined.log").read_text(encoding="utf-8").strip() == '{"event":"text"}'


def test_append_ui_log_lines_supports_locked_mode_and_replace_errors(tmp_path: Path) -> None:
    append_ui_log_lines(
        tmp_path,
        session_id="S2",
        session_metrics_line=json.dumps({"event": "strict", "session_id": "S2"}, ensure_ascii=False),
        combined_text_line=json.dumps({"event": "strict", "session_id": "S2"}, ensure_ascii=False),
        use_lock=True,
        errors="replace",
    )

    assert "strict" in (tmp_path / "metrics_S2.jsonl").read_text(encoding="utf-8")
    assert "strict" in (tmp_path / "metrics_combined.jsonl").read_text(encoding="utf-8")
    assert "strict" in (tmp_path / "ui_combined.log").read_text(encoding="utf-8")


def test_active_entrypoints_use_shared_log_sink_helper() -> None:
    helper_source = (ROOT / "pneumo_solver_ui" / "ui_logging_runtime_helpers.py").read_text(encoding="utf-8")
    app_source = (ROOT / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    heavy_source = (ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")

    assert "def append_ui_log_lines" in helper_source
    assert "append_ui_log_lines(" in app_source
    assert "append_ui_log_lines(" in heavy_source
    assert "metrics_combined.jsonl" in helper_source
    assert "ui_combined.log" in helper_source
