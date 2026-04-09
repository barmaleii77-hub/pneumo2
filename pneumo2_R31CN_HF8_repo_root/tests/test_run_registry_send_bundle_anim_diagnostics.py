from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary
from pneumo_solver_ui.run_registry import log_send_bundle_created
from pneumo_solver_ui.solver_points_contract import CORNERS, POINT_KINDS, point_cols
from pneumo_solver_ui.tools.make_send_bundle import _collect_anim_latest_bundle_diagnostics
from pneumo_solver_ui.tools.send_bundle_contract import ANIM_DIAG_SIDECAR_JSON, ANIM_DIAG_SIDECAR_MD


ROOT = Path(__file__).resolve().parents[1]


def _solver_df() -> pd.DataFrame:
    t = np.array([0.0, 0.1, 0.2], dtype=float)
    data: dict[str, object] = {
        "время_с": t,
        "скорость_vx_м_с": np.array([10.0, 10.0, 10.0], dtype=float),
        "yaw_рад": np.array([0.0, 0.0, 0.0], dtype=float),
    }
    for c in CORNERS:
        data[f"дорога_{c}_м"] = np.array([0.0, 0.0, 0.0], dtype=float)
        data[f"перемещение_колеса_{c}_м"] = np.array([0.3, 0.3, 0.3], dtype=float)
        data[f"рама_угол_{c}_z_м"] = np.array([0.5, 0.5, 0.5], dtype=float)

    seed = 0.0
    for kind in POINT_KINDS:
        for corner in CORNERS:
            for axis_i, col in enumerate(point_cols(kind, corner)):
                base = seed + float(axis_i)
                data[col] = np.array([base, base + 0.01, base + 0.02], dtype=float)
            seed += 0.1
    return pd.DataFrame(data)



def _prepare_anim_export(tmp_path: Path, monkeypatch) -> tuple[Path, Path, dict]:
    workspace_dir = tmp_path / "workspace"
    exports_dir = workspace_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))

    road_csv = tmp_path / "road.csv"
    road_csv.write_text(
        "t,z0,z1,z2,z3\n"
        "0,0,0,0,0\n"
        "0.1,0.01,0.02,-0.01,-0.02\n",
        encoding="utf-8",
    )

    npz_path, ptr_path = export_anim_latest_bundle(
        exports_dir=exports_dir,
        df_main=_solver_df(),
        meta={
            "source": "pytest",
            "geometry": {"wheelbase_m": 2.8, "track_m": 1.6},
            "road_csv": str(road_csv),
        },
    )
    (npz_path.with_name(f"{npz_path.stem}.desktop_mnemo_events.json")).write_text(
        json.dumps(
            {
                "schema_version": "desktop_mnemo_event_log_v1",
                "updated_utc": "2026-04-10T08:15:00Z",
                "npz_path": str(npz_path.resolve()),
                "current_mode": "Регуляторный коридор",
                "event_count": 4,
                "active_latch_count": 1,
                "acknowledged_latch_count": 2,
                "recent_events": [
                    {"title": "Большой перепад давлений"},
                    {"title": "Смена режима"},
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    pointer = json.loads(ptr_path.read_text(encoding="utf-8"))
    return npz_path, ptr_path, pointer



def test_collect_anim_latest_bundle_diagnostics_writes_sidecars(tmp_path: Path, monkeypatch) -> None:
    npz_path, ptr_path, pointer = _prepare_anim_export(tmp_path, monkeypatch)

    diag, md = _collect_anim_latest_bundle_diagnostics(tmp_path)

    assert diag["anim_latest_available"] is True
    assert diag["anim_latest_pointer_json"] == str(ptr_path.resolve())
    assert diag["anim_latest_npz_path"] == str(npz_path.resolve())
    assert diag["anim_latest_visual_cache_token"] == pointer["visual_cache_token"]
    assert diag["anim_latest_visual_reload_inputs"] == ["npz", "road_csv"]
    assert diag["anim_latest_mnemo_event_log_exists"] is True
    assert diag["anim_latest_mnemo_event_log_current_mode"] == "Регуляторный коридор"
    assert diag["anim_latest_mnemo_event_log_event_count"] == 4
    assert (tmp_path / ANIM_DIAG_SIDECAR_JSON).exists()
    assert (tmp_path / ANIM_DIAG_SIDECAR_MD).exists()
    assert pointer["visual_cache_token"] in md
    assert "anim_latest_mnemo_event_log_state: mode=Регуляторный коридор / total=4 / active=1 / acked=2" in md



def test_run_registry_send_bundle_created_accepts_extended_anim_fields(tmp_path: Path, monkeypatch) -> None:
    _npz_path, ptr_path, pointer = _prepare_anim_export(tmp_path, monkeypatch)
    diag = collect_anim_latest_diagnostics_summary(include_meta=True)

    runs_root = tmp_path / "runs"
    monkeypatch.setattr("pneumo_solver_ui.run_registry._runs_root", lambda: runs_root)

    zip_path = tmp_path / "bundle.zip"
    zip_path.write_bytes(b"zip bytes")
    dashboard_html = tmp_path / "latest_dashboard.html"
    dashboard_html.write_text("<html></html>", encoding="utf-8")

    log_send_bundle_created(
        zip_path=zip_path,
        latest_zip_path=tmp_path / "latest_send_bundle.zip",
        sha256="abc123",
        size_bytes=123,
        release="pytest-release",
        primary_session_dir=tmp_path / "session",
        validation_ok=True,
        validation_errors=0,
        validation_warnings=1,
        dashboard_created=True,
        dashboard_html_path=dashboard_html,
        env={"PNEUMO_RUN_ID": "PYTEST"},
        **diag,
    )

    lines = (runs_root / "run_registry.jsonl").read_text(encoding="utf-8").strip().splitlines()
    rec = json.loads(lines[-1])

    assert rec["event"] == "send_bundle_created"
    assert rec["zip_path"] == str(zip_path)
    assert rec["latest_zip_path"].endswith("latest_send_bundle.zip")
    assert rec["dashboard_created"] is True
    assert rec["anim_latest_pointer_json"] == str(ptr_path.resolve())
    assert rec["anim_latest_visual_cache_token"] == pointer["visual_cache_token"]
    assert rec["anim_latest_visual_reload_inputs"] == ["npz", "road_csv"]
    assert rec["anim_latest_available"] is True
    assert rec["anim_latest_mnemo_event_log_exists"] is True
    assert rec["anim_latest_mnemo_event_log_current_mode"] == "Регуляторный коридор"
    assert Path(rec["anim_latest_global_pointer_json"]).parts[-3:] == ("workspace", "_pointers", "anim_latest.json")



def test_run_registry_index_last_event_keeps_anim_latest_usability_summary(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    monkeypatch.setattr("pneumo_solver_ui.run_registry._runs_root", lambda: runs_root)

    log_send_bundle_created(
        zip_path=tmp_path / "bundle.zip",
        sha256="abc123",
        size_bytes=123,
        release="pytest-release",
        anim_latest_available=True,
        anim_latest_global_pointer_json=str(tmp_path / "workspace" / "_pointers" / "anim_latest.json"),
        anim_latest_pointer_json=str(tmp_path / "workspace" / "exports" / "anim_latest.json"),
        anim_latest_npz_path=str(tmp_path / "workspace" / "exports" / "anim_latest.npz"),
        anim_latest_visual_cache_token="tok-idx",
        anim_latest_visual_reload_inputs=["npz", "road_csv"],
        anim_latest_visual_cache_dependencies={"npz": {"path": "anim_latest.npz"}},
        anim_latest_updated_utc="2026-04-07T21:00:00Z",
        anim_latest_pointer_json_exists=False,
        anim_latest_npz_exists=False,
        anim_latest_pointer_json_in_workspace=True,
        anim_latest_npz_in_workspace=True,
        anim_latest_usable=False,
        anim_latest_issues=["not reproducible from this bundle"],
        anim_latest_mnemo_event_log_ref="anim_latest.desktop_mnemo_events.json",
        anim_latest_mnemo_event_log_exists=True,
        anim_latest_mnemo_event_log_schema_version="desktop_mnemo_event_log_v1",
        anim_latest_mnemo_event_log_updated_utc="2026-04-10T08:15:00Z",
        anim_latest_mnemo_event_log_current_mode="Регуляторный коридор",
        anim_latest_mnemo_event_log_event_count=4,
        anim_latest_mnemo_event_log_active_latch_count=1,
        anim_latest_mnemo_event_log_acknowledged_latch_count=2,
        anim_latest_mnemo_event_log_recent_titles=["Большой перепад давлений", "Смена режима"],
    )

    idx = json.loads((runs_root / "index.json").read_text(encoding="utf-8"))
    last = dict(idx.get("last_event") or {})

    assert last["anim_latest_available"] is True
    assert last["anim_latest_visual_cache_token"] == "tok-idx"
    assert last["anim_latest_visual_reload_inputs"] == ["npz", "road_csv"]
    assert last["anim_latest_pointer_json_exists"] is False
    assert last["anim_latest_npz_exists"] is False
    assert last["anim_latest_usable"] is False
    assert last["anim_latest_issues"] == ["not reproducible from this bundle"]
    assert last["anim_latest_mnemo_event_log_exists"] is True
    assert last["anim_latest_mnemo_event_log_current_mode"] == "Регуляторный коридор"
    assert last["anim_latest_mnemo_event_log_recent_titles"] == ["Большой перепад давлений", "Смена режима"]
    assert "anim_latest_visual_cache_dependencies" not in last


def test_run_registry_index_keeps_browser_perf_evidence_summary(tmp_path: Path, monkeypatch) -> None:
    runs_root = tmp_path / "runs"
    monkeypatch.setattr("pneumo_solver_ui.run_registry._runs_root", lambda: runs_root)

    log_send_bundle_created(
        zip_path=tmp_path / "bundle.zip",
        sha256="abc123",
        size_bytes=123,
        release="pytest-release",
        browser_perf_registry_snapshot_exists=True,
        browser_perf_registry_snapshot_in_bundle=True,
        browser_perf_previous_snapshot_exists=False,
        browser_perf_previous_snapshot_in_bundle=False,
        browser_perf_contract_exists=True,
        browser_perf_contract_in_bundle=True,
        browser_perf_evidence_report_exists=True,
        browser_perf_evidence_report_in_bundle=True,
        browser_perf_comparison_report_exists=True,
        browser_perf_comparison_report_in_bundle=True,
        browser_perf_trace_exists=False,
        browser_perf_trace_in_bundle=False,
        browser_perf_status="snapshot_only",
        browser_perf_level="WARN",
        browser_perf_evidence_status="snapshot_only",
        browser_perf_evidence_level="WARN",
        browser_perf_bundle_ready=False,
        browser_perf_snapshot_contract_match=True,
        browser_perf_comparison_status="no_reference",
        browser_perf_comparison_level="WARN",
        browser_perf_comparison_ready=False,
        browser_perf_comparison_changed=None,
        browser_perf_comparison_delta_total_wakeups=0,
        browser_perf_comparison_delta_total_duplicate_guard_hits=0,
        browser_perf_comparison_delta_total_render_count=0,
        browser_perf_component_count=2,
        browser_perf_total_wakeups=10,
        browser_perf_total_duplicate_guard_hits=3,
    )

    idx = json.loads((runs_root / "index.json").read_text(encoding="utf-8"))
    last = dict(idx.get("last_event") or {})

    assert last["browser_perf_registry_snapshot_exists"] is True
    assert last["browser_perf_registry_snapshot_in_bundle"] is True
    assert last["browser_perf_previous_snapshot_exists"] is False
    assert last["browser_perf_previous_snapshot_in_bundle"] is False
    assert last["browser_perf_contract_exists"] is True
    assert last["browser_perf_contract_in_bundle"] is True
    assert last["browser_perf_evidence_report_exists"] is True
    assert last["browser_perf_evidence_report_in_bundle"] is True
    assert last["browser_perf_comparison_report_exists"] is True
    assert last["browser_perf_comparison_report_in_bundle"] is True
    assert last["browser_perf_trace_in_bundle"] is False
    assert last["browser_perf_status"] == "snapshot_only"
    assert last["browser_perf_evidence_status"] == "snapshot_only"
    assert last["browser_perf_bundle_ready"] is False
    assert last["browser_perf_snapshot_contract_match"] is True
    assert last["browser_perf_comparison_status"] == "no_reference"
    assert last["browser_perf_comparison_ready"] is False
    assert last["browser_perf_comparison_delta_total_wakeups"] == 0
    assert last["browser_perf_component_count"] == 2


def test_sources_wire_anim_diagnostics_into_launcher_and_send_bundle() -> None:
    bundle_text = (ROOT / "pneumo_solver_ui" / "tools" / "make_send_bundle.py").read_text(encoding="utf-8")
    gui_text = (ROOT / "pneumo_solver_ui" / "tools" / "send_results_gui.py").read_text(encoding="utf-8")
    launcher_text = (ROOT / "START_PNEUMO_APP.py").read_text(encoding="utf-8")
    registry_text = (ROOT / "pneumo_solver_ui" / "run_registry.py").read_text(encoding="utf-8")

    assert '("_pointers", False)' in bundle_text
    assert 'ANIM_DIAG_SIDECAR_JSON' in bundle_text
    assert '**anim_diag_event' in bundle_text
    assert 'anim_latest_mnemo_event_log_state' in bundle_text
    assert 'collect_anim_latest_diagnostics_summary' in launcher_text
    assert 'send_results_gui_spawned' in launcher_text
    assert 'ANIM_DIAG_SIDECAR_JSON' in gui_text
    assert 'load_latest_send_bundle_anim_dashboard' in gui_text
    assert 'format_anim_dashboard_brief_lines' in gui_text
    assert 'Anim pointer diagnostics:' in gui_text
    assert 'pick_anim_latest_fields' in registry_text
    assert 'ANIM_LATEST_INDEX_FIELDS' in registry_text
    assert 'browser_perf_registry_snapshot_in_bundle' in registry_text
    assert 'in_bundle=' in bundle_text
