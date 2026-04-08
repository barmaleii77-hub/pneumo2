from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.browser_perf_artifacts import (
    BROWSER_PERF_CONTRACT_JSON_NAME,
    BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME,
    collect_browser_perf_artifacts_summary,
    persist_browser_perf_snapshot_event,
    write_browser_perf_artifacts,
)
from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary
from pneumo_solver_ui.tools.make_send_bundle import _collect_anim_latest_bundle_diagnostics
from pneumo_solver_ui.tools.triage_report import generate_triage_report


ROOT = Path(__file__).resolve().parents[1]


def _snapshot() -> dict:
    return {
        "ts_iso": "2026-03-31T00:00:00Z",
        "dataset_id": "pytest-dataset",
        "components": {
            "playhead_ctrl": {
                "component": "playhead_ctrl",
                "dataset_id": "pytest-dataset",
                "viewport_state": "visible",
                "wakeups": 7,
                "duplicate_guard_hits": 2,
                "render_count": 9,
                "schedule_raf_count": 10,
                "schedule_timeout_count": 1,
                "idle_poll_ms": 300,
            },
            "mech_anim": {
                "component": "mech_anim",
                "dataset_id": "pytest-dataset",
                "viewport_state": "offscreen",
                "wakeups": 3,
                "duplicate_guard_hits": 1,
                "render_count": 4,
                "schedule_raf_count": 5,
                "schedule_timeout_count": 2,
                "idle_poll_ms": 60000,
            },
        },
        "summary": {
            "component_count": 2,
            "visible_count": 1,
            "offscreen_count": 1,
            "total_wakeups": 10,
            "total_duplicate_guard_hits": 3,
            "total_render_count": 13,
            "total_schedule_raf": 15,
            "total_schedule_timeout": 3,
            "max_idle_poll_ms": 60000,
        },
    }


def test_write_browser_perf_artifacts_writes_snapshot_and_contract(tmp_path: Path) -> None:
    out = write_browser_perf_artifacts(tmp_path, _snapshot(), updated_utc="2026-03-31T00:00:01Z")

    snap_path = tmp_path / BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME
    contract_path = tmp_path / BROWSER_PERF_CONTRACT_JSON_NAME
    assert snap_path.exists()
    assert contract_path.exists()
    assert out["browser_perf_registry_snapshot"]["exists"] is True
    assert out["browser_perf_contract"]["exists"] is True

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert snap["schema"] == "browser_perf_registry_snapshot_v1"
    assert snap["summary"]["component_count"] == 2
    assert contract["schema"] == "browser_perf_contract_v1"
    assert contract["status"] == "snapshot_only"
    assert contract["level"] == "WARN"


def test_persist_browser_perf_snapshot_event_returns_summary(tmp_path: Path) -> None:
    evt = {
        "kind": "browser_perf_snapshot",
        "dataset_id": "pytest-dataset",
        "source_component": "playhead_ctrl",
        "snapshot": _snapshot(),
        "ts": 1234567890,
        "updated_utc": "2026-03-31T00:00:02Z",
    }
    summary = persist_browser_perf_snapshot_event(evt, tmp_path)
    assert summary is not None
    assert summary["browser_perf_registry_snapshot_exists"] is True
    assert summary["browser_perf_contract_exists"] is True
    assert summary["browser_perf_trace_exists"] is False
    assert summary["browser_perf_component_count"] == 2
    assert summary["browser_perf_total_wakeups"] == 10
    assert summary["browser_perf_total_duplicate_guard_hits"] == 3


def test_collect_anim_latest_diagnostics_summary_surfaces_browser_perf_artifacts(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    exports = workspace / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))

    write_browser_perf_artifacts(exports, _snapshot(), updated_utc="2026-03-31T00:00:03Z")
    summary = collect_anim_latest_diagnostics_summary(include_meta=False)
    assert summary["browser_perf_registry_snapshot_ref"] == BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME
    assert summary["browser_perf_registry_snapshot_exists"] is True
    assert summary["browser_perf_contract_ref"] == BROWSER_PERF_CONTRACT_JSON_NAME
    assert summary["browser_perf_contract_exists"] is True
    assert summary["browser_perf_status"] == "snapshot_only"
    assert summary["browser_perf_level"] == "WARN"
    assert summary["browser_perf_component_count"] == 2

    diag, md = _collect_anim_latest_bundle_diagnostics(tmp_path)
    assert diag["browser_perf_registry_snapshot_exists"] is True
    assert diag["browser_perf_contract_exists"] is True
    assert "browser_perf_registry_snapshot" in md
    assert "browser_perf_status" in md


def test_generate_triage_report_surfaces_browser_perf_artifacts(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    exports = workspace / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))
    write_browser_perf_artifacts(exports, _snapshot(), updated_utc="2026-03-31T00:00:04Z")

    md, summary = generate_triage_report(tmp_path, keep_last_n=1)
    anim = dict(summary.get("anim_latest") or {})
    assert anim["browser_perf_registry_snapshot_exists"] is True
    assert anim["browser_perf_contract_exists"] is True
    assert anim["browser_perf_status"] == "snapshot_only"
    assert "browser_perf_registry_snapshot" in md
    assert "browser_perf_status" in md


def test_playhead_component_exports_browser_perf_snapshot_to_python() -> None:
    text = (ROOT / "pneumo_solver_ui" / "components" / "playhead_ctrl" / "index.html").read_text(encoding="utf-8")
    assert 'kind: "browser_perf_snapshot"' in text
    assert 'sendPerfSnapshotToPython(true);' in text


def test_ui_sources_consume_browser_perf_snapshot_event() -> None:
    helper_text = (ROOT / "pneumo_solver_ui" / "ui_event_sync_helpers.py").read_text(encoding="utf-8")
    assert 'evt.get("kind") == "browser_perf_snapshot"' in helper_text
    assert "persist_browser_perf_snapshot_event_fn(evt, workspace_exports_dir)" in helper_text

    for rel in ("pneumo_solver_ui/pneumo_ui_app.py", "pneumo_solver_ui/app.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "consume_playhead_event = partial(" in text
        assert "persist_browser_perf_snapshot_event_fn=persist_browser_perf_snapshot_event" in text
        assert "workspace_exports_dir=WORKSPACE_EXPORTS_DIR" in text
