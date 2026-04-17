from __future__ import annotations

import json
from pathlib import Path

from pneumo_solver_ui.browser_perf_artifacts import (
    BROWSER_PERF_COMPARISON_REPORT_JSON_NAME,
    BROWSER_PERF_CONTRACT_JSON_NAME,
    BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME,
    BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME,
    BROWSER_PERF_REGISTRY_SNAPSHOT_JSON_NAME,
    BROWSER_PERF_TRACE_JSON_NAME,
    VIEWPORT_GATING_REPORT_JSON_NAME,
    collect_browser_perf_artifacts_summary,
    persist_browser_perf_snapshot_event,
    write_browser_perf_artifacts,
    write_browser_perf_trace_artifact,
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
    prev_snap_path = tmp_path / BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME
    contract_path = tmp_path / BROWSER_PERF_CONTRACT_JSON_NAME
    report_path = tmp_path / BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME
    comparison_path = tmp_path / BROWSER_PERF_COMPARISON_REPORT_JSON_NAME
    assert snap_path.exists()
    assert contract_path.exists()
    assert report_path.exists()
    assert comparison_path.exists()
    assert prev_snap_path.exists() is False
    assert out["browser_perf_registry_snapshot"]["exists"] is True
    assert out["browser_perf_contract"]["exists"] is True
    assert out["browser_perf_evidence_report"]["exists"] is True
    assert out["browser_perf_comparison_report"]["exists"] is True

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    assert snap["schema"] == "browser_perf_registry_snapshot_v1"
    assert snap["summary"]["component_count"] == 2
    assert contract["schema"] == "browser_perf_contract_v1"
    assert contract["status"] == "snapshot_only"
    assert contract["level"] == "WARN"
    assert report["schema"] == "browser_perf_evidence_report_v1"
    assert report["status"] == "snapshot_only"
    assert report["level"] == "WARN"
    assert report["bundle_ready"] is False
    assert report["snapshot_contract_match"] is True
    assert comparison["schema"] == "browser_perf_comparison_report_v1"
    assert comparison["status"] == "no_reference"
    assert comparison["level"] == "WARN"
    assert comparison["comparison_ready"] is False


def test_write_browser_perf_artifacts_marks_bundle_ready_when_trace_exists(tmp_path: Path) -> None:
    (tmp_path / "browser_perf_trace.json").write_text('{"traceEvents":[]}', encoding="utf-8")
    out = write_browser_perf_artifacts(tmp_path, _snapshot(), updated_utc="2026-03-31T00:00:01Z")
    report = json.loads((tmp_path / BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME).read_text(encoding="utf-8"))

    assert out["browser_perf_trace"]["exists"] is True
    assert out["browser_perf_evidence_report"]["status"] == "trace_bundle_ready"
    assert report["status"] == "trace_bundle_ready"
    assert report["level"] == "PASS"
    assert report["bundle_ready"] is True


def test_write_browser_perf_trace_artifact_and_viewport_report_pass_hidden_budget(tmp_path: Path) -> None:
    snap = _snapshot()
    hidden = snap["components"]["mech_anim"]
    hidden.update(
        {
            "wakeups": 0,
            "render_count": 0,
            "schedule_raf_count": 0,
            "schedule_timeout_count": 0,
            "duplicate_guard_hits": 0,
        }
    )
    trace = write_browser_perf_trace_artifact(
        tmp_path,
        {"traceEvents": [{"name": "frame", "ts": 1}]},
        trace_session_id="pytest-trace",
        surfaces=["playhead_ctrl", "mech_anim"],
        idle_cpu_summary={"idle_cpu_pct": 1.5},
    )
    out = write_browser_perf_artifacts(tmp_path, snap, updated_utc="2026-03-31T00:00:01Z")
    report = json.loads((tmp_path / VIEWPORT_GATING_REPORT_JSON_NAME).read_text(encoding="utf-8"))
    trace_payload = json.loads((tmp_path / BROWSER_PERF_TRACE_JSON_NAME).read_text(encoding="utf-8"))

    assert trace["exists"] is True
    assert trace_payload["schema"] == "browser_perf_trace.v1"
    assert trace_payload["trace_session_id"] == "pytest-trace"
    assert out["viewport_gating_report"]["status"] == "hidden_surfaces_gated"
    assert out["viewport_gating_report"]["release_gate"] == "PASS"
    assert report["schema"] == "viewport_gating_report.v1"
    assert report["hidden_surface_count"] == 1
    assert report["hidden_surface_update_count"] == 0
    assert report["hidden_surfaces_gated"] is True
    summary = collect_browser_perf_artifacts_summary(tmp_path)
    assert summary["browser_perf_trace_exists"] is True
    assert summary["viewport_gating_report_exists"] is True
    assert summary["viewport_gating_release_gate"] == "PASS"
    assert summary["viewport_gating_hidden_surfaces_gated"] is True


def test_viewport_report_hard_fails_hidden_surface_activity(tmp_path: Path) -> None:
    write_browser_perf_artifacts(tmp_path, _snapshot(), updated_utc="2026-03-31T00:00:01Z")
    report = json.loads((tmp_path / VIEWPORT_GATING_REPORT_JSON_NAME).read_text(encoding="utf-8"))
    summary = collect_browser_perf_artifacts_summary(tmp_path)

    assert report["status"] == "hidden_surface_updates"
    assert report["release_gate"] == "FAIL"
    assert report["hard_fail"] is True
    assert report["hidden_surface_update_count"] == 1
    assert summary["viewport_gating_hard_fail"] is True
    assert summary["viewport_gating_hidden_surface_update_count"] == 1


def test_write_browser_perf_artifacts_writes_previous_snapshot_and_comparison_on_second_run(tmp_path: Path) -> None:
    first = _snapshot()
    second = _snapshot()
    second["summary"] = dict(second["summary"])
    second["summary"]["total_wakeups"] = 14
    second["summary"]["total_duplicate_guard_hits"] = 5
    second["summary"]["total_render_count"] = 18
    second["summary"]["max_idle_poll_ms"] = 120000

    write_browser_perf_artifacts(tmp_path, first, updated_utc="2026-03-31T00:00:01Z")
    summary = collect_browser_perf_artifacts_summary(tmp_path)
    assert summary["browser_perf_comparison_status"] == "no_reference"
    assert summary["browser_perf_previous_snapshot_exists"] is False

    write_browser_perf_artifacts(tmp_path, second, updated_utc="2026-03-31T00:00:02Z")
    summary = collect_browser_perf_artifacts_summary(tmp_path)
    prev = json.loads((tmp_path / BROWSER_PERF_PREVIOUS_SNAPSHOT_JSON_NAME).read_text(encoding="utf-8"))
    comparison = json.loads((tmp_path / BROWSER_PERF_COMPARISON_REPORT_JSON_NAME).read_text(encoding="utf-8"))

    assert prev["summary"]["total_wakeups"] == 10
    assert summary["browser_perf_previous_snapshot_exists"] is True
    assert summary["browser_perf_comparison_status"] == "changed"
    assert summary["browser_perf_comparison_level"] == "PASS"
    assert summary["browser_perf_comparison_ready"] is True
    assert summary["browser_perf_comparison_changed"] is True
    assert summary["browser_perf_comparison_delta_total_wakeups"] == 4
    assert summary["browser_perf_comparison_delta_total_duplicate_guard_hits"] == 2
    assert summary["browser_perf_comparison_delta_total_render_count"] == 5
    assert summary["browser_perf_comparison_delta_max_idle_poll_ms"] == 60000
    assert comparison["reference_snapshot_exists"] is True
    assert comparison["status"] == "changed"
    assert comparison["comparison_ready"] is True


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
    assert summary["browser_perf_evidence_report_exists"] is True
    assert summary["browser_perf_evidence_status"] == "snapshot_only"
    assert summary["browser_perf_bundle_ready"] is False
    assert summary["browser_perf_snapshot_contract_match"] is True
    assert summary["browser_perf_comparison_report_exists"] is True
    assert summary["browser_perf_comparison_status"] == "no_reference"
    assert summary["browser_perf_comparison_ready"] is False


def test_persist_browser_perf_snapshot_event_writes_trace_when_present(tmp_path: Path) -> None:
    snap = _snapshot()
    snap["components"]["mech_anim"].update({"wakeups": 0, "render_count": 0, "schedule_raf_count": 0, "schedule_timeout_count": 0})
    evt = {
        "kind": "browser_perf_snapshot",
        "dataset_id": "pytest-dataset",
        "source_component": "playhead_ctrl",
        "snapshot": snap,
        "browser_perf_trace": {"traceEvents": [{"name": "present", "ts": 123}]},
        "trace_session_id": "evt-trace",
        "updated_utc": "2026-03-31T00:00:02Z",
    }
    summary = persist_browser_perf_snapshot_event(evt, tmp_path)
    assert summary is not None
    assert (tmp_path / BROWSER_PERF_TRACE_JSON_NAME).exists()
    assert summary["browser_perf_trace_exists"] is True
    assert summary["browser_perf_evidence_status"] == "trace_bundle_ready"


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
    assert summary["browser_perf_evidence_report_ref"] == BROWSER_PERF_EVIDENCE_REPORT_JSON_NAME
    assert summary["browser_perf_evidence_report_exists"] is True
    assert summary["browser_perf_comparison_report_ref"] == BROWSER_PERF_COMPARISON_REPORT_JSON_NAME
    assert summary["browser_perf_comparison_report_exists"] is True
    assert summary["browser_perf_status"] == "snapshot_only"
    assert summary["browser_perf_level"] == "WARN"
    assert summary["browser_perf_evidence_status"] == "snapshot_only"
    assert summary["browser_perf_evidence_level"] == "WARN"
    assert summary["browser_perf_comparison_status"] == "no_reference"
    assert summary["browser_perf_comparison_level"] == "WARN"
    assert summary["browser_perf_component_count"] == 2

    diag, md = _collect_anim_latest_bundle_diagnostics(tmp_path)
    assert diag["browser_perf_registry_snapshot_exists"] is True
    assert diag["browser_perf_contract_exists"] is True
    assert diag["browser_perf_evidence_report_exists"] is True
    assert diag["browser_perf_comparison_report_exists"] is True
    assert "browser_perf_registry_snapshot" in md
    assert "browser_perf_status" in md
    assert "browser_perf_evidence_report" in md
    assert "browser_perf_evidence_status" in md
    assert "browser_perf_comparison_report" in md
    assert "browser_perf_comparison_status" in md


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
    assert anim["browser_perf_evidence_report_exists"] is True
    assert anim["browser_perf_comparison_report_exists"] is True
    assert anim["browser_perf_status"] == "snapshot_only"
    assert anim["browser_perf_comparison_status"] == "no_reference"
    assert "browser_perf_registry_snapshot" in md
    assert "browser_perf_status" in md
    assert "browser_perf_evidence_report" in md
    assert "browser_perf_evidence_status" in md
    assert "browser_perf_comparison_report" in md
    assert "browser_perf_comparison_status" in md


def test_playhead_component_exports_browser_perf_snapshot_to_python() -> None:
    text = (ROOT / "pneumo_solver_ui" / "components" / "playhead_ctrl" / "index.html").read_text(encoding="utf-8")
    assert 'kind: "browser_perf_snapshot"' in text
    assert "function collectBrowserPerfTracePayload(snapshot)" in text
    assert "evt.browser_perf_trace = tracePayload.trace" in text
    assert "sendPerfSnapshotToPython(true, {includeTrace: true});" in text


def test_ui_sources_consume_browser_perf_snapshot_event() -> None:
    helper_text = (ROOT / "pneumo_solver_ui" / "ui_event_sync_helpers.py").read_text(encoding="utf-8")
    assert 'evt.get("kind") == "browser_perf_snapshot"' in helper_text
    assert "persist_browser_perf_snapshot_event_fn(evt, workspace_exports_dir)" in helper_text

    for rel in ("pneumo_solver_ui/pneumo_ui_app.py", "pneumo_solver_ui/app.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "consume_playhead_event = build_playhead_event_consumer(" in text
        assert "persist_browser_perf_snapshot_event_fn=persist_browser_perf_snapshot_event" in text
        assert "workspace_exports_dir=WORKSPACE_EXPORTS_DIR" in text
