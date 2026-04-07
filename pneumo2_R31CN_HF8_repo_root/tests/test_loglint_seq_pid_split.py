from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.tools.loglint import lint_file


def test_loglint_seq_allows_reset_across_different_pids(tmp_path: Path) -> None:
    fp = tmp_path / "events.jsonl"
    rows = [
        {"ts": "2026-03-24T00:00:00", "schema": "ui", "schema_version": "1.2.0", "event": "a", "event_id": "e1", "trace_id": "t1", "release": "R31P", "session_id": "UI_X", "pid": 111, "seq": 1},
        {"ts": "2026-03-24T00:00:01", "schema": "ui", "schema_version": "1.2.0", "event": "b", "event_id": "e2", "trace_id": "t1", "release": "R31P", "session_id": "UI_X", "pid": 111, "seq": 2},
        {"ts": "2026-03-24T00:00:02", "schema": "ui", "schema_version": "1.2.0", "event": "c", "event_id": "e3", "trace_id": "t1", "release": "R31P", "session_id": "UI_X", "pid": 222, "seq": 1},
    ]
    fp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    n_lines, errors = lint_file(fp, schema="ui", strict=True, check_seq=True)

    assert n_lines == 3
    assert errors == []
