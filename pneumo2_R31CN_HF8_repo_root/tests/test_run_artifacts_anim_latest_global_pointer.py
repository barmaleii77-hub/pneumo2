
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.run_artifacts import (
    apply_anim_latest_to_session,
    autoload_to_session,
    collect_anim_latest_diagnostics_summary,
    global_anim_latest_pointer_path,
    local_anim_latest_export_paths,
    latest_animation_ptr_path,
    latest_simulation_ptr_path,
    load_latest_animation_ptr,
    save_last_baseline_ptr,
    write_anim_latest_pointer_json,
)
from pneumo_solver_ui.solver_points_contract import CORNERS, POINT_KINDS, point_cols
from pneumo_solver_ui.ui_preflight import collect_steps, _pick_next_page_canonical


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


def _prepare_anim_export(tmp_path: Path, monkeypatch) -> tuple[Path, Path, Path, dict]:
    app_dir = tmp_path / "project"
    workspace_dir = app_dir / "pneumo_solver_ui" / "workspace"
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
    pointer = json.loads(ptr_path.read_text(encoding="utf-8"))
    return app_dir, npz_path, ptr_path, pointer


def test_run_artifacts_global_anim_pointer_mirrors_visual_reload_diagnostics(tmp_path: Path, monkeypatch) -> None:
    app_dir, npz_path, ptr_path, pointer = _prepare_anim_export(tmp_path, monkeypatch)

    global_anim = load_latest_animation_ptr()
    assert global_anim is not None
    assert latest_animation_ptr_path().exists()
    assert global_anim["pointer_json"] == str(ptr_path.resolve())
    assert global_anim["npz_path"] == str(npz_path.resolve())
    assert global_anim["visual_cache_token"] == pointer["visual_cache_token"]
    assert global_anim["visual_reload_inputs"] == ["npz", "road_csv"]

    sim_ptr = save_last_baseline_ptr(
        cache_dir=app_dir / "pneumo_solver_ui" / "workspace" / "baseline",
        meta={"source": "pytest-baseline"},
        anim_latest_npz=npz_path,
        anim_latest_json=ptr_path,
    )
    assert latest_simulation_ptr_path().exists()
    assert sim_ptr["visual_cache_token"] == pointer["visual_cache_token"]
    assert sim_ptr["pointer_json"] == str(ptr_path.resolve())


def test_autoload_to_session_restores_anim_latest_diagnostics(tmp_path: Path, monkeypatch) -> None:
    app_dir, npz_path, ptr_path, pointer = _prepare_anim_export(tmp_path, monkeypatch)

    save_last_baseline_ptr(
        cache_dir=app_dir / "pneumo_solver_ui" / "workspace" / "baseline",
        meta={"source": "pytest-baseline"},
        anim_latest_npz=npz_path,
        anim_latest_json=ptr_path,
    )

    session_state: dict = {}
    autoload_to_session(session_state)

    assert session_state["anim_latest_npz"] == str(npz_path.resolve())
    assert session_state["anim_latest_pointer"] == str(ptr_path.resolve())
    assert session_state["anim_latest_visual_cache_token"] == pointer["visual_cache_token"]
    assert session_state["anim_latest_visual_reload_inputs"] == ["npz", "road_csv"]
    deps = dict(session_state["anim_latest_visual_cache_dependencies"])
    assert deps["road_csv_path"].endswith("anim_latest_road_csv.csv")


def test_apply_anim_latest_to_session_enriches_legacy_pointer_payload(tmp_path: Path, monkeypatch) -> None:
    workspace_dir = tmp_path / "workspace"
    exports_dir = workspace_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))

    pointer_path = exports_dir / "anim_latest.json"
    npz_path = exports_dir / "anim_latest.npz"
    npz_path.write_bytes(b"npz-bytes")
    pointer_path.write_text(
        json.dumps(
            {
                "updated_utc": "2026-04-07T18:30:00Z",
                "visual_cache_token": "tok-session",
                "visual_reload_inputs": ["npz", "road_csv"],
                "visual_cache_dependencies": {"road_csv_path": "anim_latest_road_csv.csv"},
                "npz_path": "anim_latest.npz",
                "meta": {"source": "session-pointer"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    session_state: dict = {}
    applied = apply_anim_latest_to_session(
        session_state,
        {
            "anim_latest_json": str(pointer_path),
            "anim_latest_npz": str(npz_path),
            "anim_latest_meta": {"source": "session-inline"},
        },
    )

    assert applied is not None
    assert session_state["anim_latest_npz"] == str(npz_path.resolve())
    assert session_state["anim_latest_pointer"] == str(pointer_path.resolve())
    assert session_state["anim_latest_visual_cache_token"] == "tok-session"
    assert session_state["anim_latest_visual_reload_inputs"] == ["npz", "road_csv"]
    assert session_state["anim_latest_meta"] == {"source": "session-inline"}


def test_write_anim_latest_pointer_json_writes_canonical_pointer_and_global_mirror(tmp_path: Path, monkeypatch) -> None:
    workspace_dir = tmp_path / "workspace"
    exports_dir = workspace_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))

    npz_path, pointer_path = local_anim_latest_export_paths(exports_dir)
    npz_path.write_bytes(b"npz-bytes")
    road_csv = exports_dir / "anim_latest_road_csv.csv"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n", encoding="utf-8")

    pointer_path, payload, mirrored = write_anim_latest_pointer_json(
        npz_path,
        pointer_path=pointer_path,
        meta={"road_csv": str(road_csv), "source": "run-artifacts-pointer"},
        updated_utc="2026-04-07T19:00:00Z",
        extra_fields={"ts": 123.0, "custom": "ok"},
        context="pytest shared pointer writer",
        mirror_global_pointer=True,
    )

    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    global_pointer = json.loads(latest_animation_ptr_path().read_text(encoding="utf-8"))

    assert mirrored is True
    assert payload["schema_version"]
    assert pointer["npz_path"] == str(npz_path.resolve())
    assert pointer["visual_cache_token"]
    assert pointer["visual_reload_inputs"] == ["npz", "road_csv"]
    assert pointer["ts"] == 123.0
    assert pointer["custom"] == "ok"
    assert global_pointer["pointer_json"] == str(pointer_path.resolve())
    assert global_pointer["visual_cache_token"] == pointer["visual_cache_token"]


def test_global_anim_latest_pointer_path_supports_read_only_resolution(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "workspace"
    pointer_path = global_anim_latest_pointer_path(workspace_dir, ensure_exists=False)

    assert pointer_path == workspace_dir / "_pointers" / "anim_latest.json"
    assert pointer_path.parent.exists() is False


def test_collect_anim_latest_diagnostics_summary_supports_legacy_anim_latest_aliases(
    tmp_path: Path, monkeypatch
) -> None:
    workspace_dir = tmp_path / "workspace"
    exports_dir = workspace_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace_dir))

    pointer_path = exports_dir / "anim_latest.json"
    npz_path = exports_dir / "anim_latest.npz"
    npz_path.write_bytes(b"npz-bytes")
    pointer_path.write_text(
        json.dumps(
            {
                "updated_utc": "2026-04-07T18:00:00Z",
                "visual_cache_token": "tok-legacy",
                "visual_reload_inputs": ["npz", "road_csv"],
                "visual_cache_dependencies": {"road_csv_path": "anim_latest_road_csv.csv"},
                "npz_path": "anim_latest.npz",
                "meta": {"source": "legacy-pointer"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    npz_path.with_name("anim_latest.desktop_mnemo_events.json").write_text(
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

    diag = collect_anim_latest_diagnostics_summary(
        {
            "anim_latest_json": str(pointer_path),
            "anim_latest_npz": str(npz_path),
            "anim_latest_meta": {"source": "legacy-inline"},
            "anim_latest_issues": ["preexisting-warning"],
        },
        include_meta=True,
    )

    assert diag["anim_latest_available"] is True
    assert diag["anim_latest_pointer_json"] == str(pointer_path.resolve())
    assert diag["anim_latest_npz_path"] == str(npz_path.resolve())
    assert diag["anim_latest_visual_cache_token"] == "tok-legacy"
    assert diag["anim_latest_visual_reload_inputs"] == ["npz", "road_csv"]
    assert diag["anim_latest_pointer_json_exists"] is True
    assert diag["anim_latest_npz_exists"] is True
    assert diag["anim_latest_meta"] == {"source": "legacy-inline"}
    assert diag["anim_latest_issues"] == ["preexisting-warning"]
    assert diag["anim_latest_mnemo_event_log_exists"] is True
    assert diag["anim_latest_mnemo_event_log_schema_version"] == "desktop_mnemo_event_log_v1"
    assert diag["anim_latest_mnemo_event_log_current_mode"] == "Регуляторный коридор"
    assert diag["anim_latest_mnemo_event_log_recent_titles"] == ["Большой перепад давлений", "Смена режима"]


class _FakeSt:
    def __init__(self) -> None:
        self.session_state = {
            "df_suite_edit": pd.DataFrame({"включен": [True], "имя": ["t1"]}),
            "baseline_ran_tests": ["t1"],
            "baseline_updated_ts": time.time(),
        }


def test_ui_preflight_export_step_reports_visual_token_and_global_sync(tmp_path: Path, monkeypatch) -> None:
    app_dir, npz_path, ptr_path, pointer = _prepare_anim_export(tmp_path, monkeypatch)

    save_last_baseline_ptr(
        cache_dir=app_dir / "pneumo_solver_ui" / "workspace" / "baseline",
        meta={"source": "pytest-baseline"},
        anim_latest_npz=npz_path,
        anim_latest_json=ptr_path,
    )

    steps = collect_steps(_FakeSt(), app_dir)
    export_step = steps["export"]

    assert export_step.ok is True
    assert "visual_cache_token:" in export_step.detail
    assert "global pointer:" in export_step.detail
    assert "global token sync: OK" in export_step.detail
    assert pointer["visual_cache_token"][:8] in export_step.detail


def test_ui_preflight_recommends_desktop_mnemo_after_export_is_ready(tmp_path: Path, monkeypatch) -> None:
    app_dir, npz_path, ptr_path, _pointer = _prepare_anim_export(tmp_path, monkeypatch)

    save_last_baseline_ptr(
        cache_dir=app_dir / "pneumo_solver_ui" / "workspace" / "baseline",
        meta={"source": "pytest-baseline"},
        anim_latest_npz=npz_path,
        anim_latest_json=ptr_path,
    )

    steps = collect_steps(_FakeSt(), app_dir)

    assert "mnemo" in steps
    assert steps["export"].page == "pneumo_solver_ui/pages/08_DesktopMnemo.py"
    assert steps["mnemo"].page == "pneumo_solver_ui/pages/08_DesktopMnemo.py"
    assert steps["mnemo"].action_label == "Открыть Desktop Mnemo"

    next_page, next_label = _pick_next_page_canonical(steps)
    assert next_page in {
        "pneumo_solver_ui/pages/08_DesktopMnemo.py",
        "pneumo_solver_ui/pages/09_Validation_Web.py",
    }
    if next_page == "pneumo_solver_ui/pages/08_DesktopMnemo.py":
        assert "Desktop Mnemo" in next_label


def test_ui_preflight_send_bundle_step_reports_last_bundle_summary(tmp_path: Path, monkeypatch) -> None:
    app_dir, _npz_path, _ptr_path, _pointer = _prepare_anim_export(tmp_path, monkeypatch)
    send_bundles = app_dir / "send_bundles"
    send_bundles.mkdir(parents=True, exist_ok=True)
    (send_bundles / "last_bundle_meta.json").write_text(
        json.dumps(
            {
                "ok": True,
                "ts": "2026-04-09 12:00:00",
                "trigger": "manual",
                "zip": {
                    "name": "latest_send_bundle.zip",
                    "path": str(send_bundles / "latest_send_bundle.zip"),
                    "size_bytes": 3 * 1024 * 1024,
                },
                "summary_lines": [
                    "Browser perf evidence: trace_bundle_ready / PASS / bundle_ready=True",
                    "Browser perf comparison: regression_checked / PASS / ready=True",
                ],
                "anim_pointer_diagnostics_path": str(send_bundles / "latest_anim_pointer_diagnostics.json"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    st_mod = _FakeSt()
    st_mod.session_state["diag_output_dir"] = "send_bundles"
    steps = collect_steps(st_mod, app_dir)
    send_bundle_step = steps["send_bundle"]

    assert send_bundle_step.ok is True
    assert "Последний ZIP: latest_send_bundle.zip" in send_bundle_step.detail
    assert "Browser perf evidence: trace_bundle_ready / PASS / bundle_ready=True" in send_bundle_step.detail
    assert "Anim pointer diagnostics:" in send_bundle_step.detail


def test_ui_preflight_send_bundle_step_rebuilds_ring_summary_from_anim_latest_summary(tmp_path: Path, monkeypatch) -> None:
    app_dir, _npz_path, _ptr_path, _pointer = _prepare_anim_export(tmp_path, monkeypatch)
    send_bundles = app_dir / "send_bundles"
    send_bundles.mkdir(parents=True, exist_ok=True)
    (send_bundles / "last_bundle_meta.json").write_text(
        json.dumps(
            {
                "ok": True,
                "ts": "2026-04-10 12:00:00",
                "trigger": "manual",
                "zip": {
                    "name": "latest_send_bundle.zip",
                    "path": str(send_bundles / "latest_send_bundle.zip"),
                    "size_bytes": 3 * 1024 * 1024,
                },
                "anim_latest_summary": {
                    "available": True,
                    "scenario_kind": "ring",
                    "ring_closure_policy": "strict_exact",
                    "ring_closure_applied": False,
                    "ring_seam_open": True,
                    "ring_seam_max_jump_m": 0.012,
                    "ring_raw_seam_max_jump_m": 0.015,
                    "browser_perf_evidence_status": "trace_bundle_ready",
                    "browser_perf_evidence_level": "PASS",
                    "browser_perf_bundle_ready": True,
                },
                "anim_pointer_diagnostics_path": str(send_bundles / "latest_anim_pointer_diagnostics.json"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    st_mod = _FakeSt()
    st_mod.session_state["diag_output_dir"] = "send_bundles"
    steps = collect_steps(st_mod, app_dir)
    send_bundle_step = steps["send_bundle"]

    assert send_bundle_step.ok is True
    assert "Browser perf evidence: trace_bundle_ready / PASS / bundle_ready=True" in send_bundle_step.detail
    assert "Ring seam: closure=strict_exact / open=True / seam_max_m=0.012 / raw_seam_max_m=0.015" in send_bundle_step.detail


def test_sources_use_run_artifacts_global_anim_pointer_flow() -> None:
    root = Path(__file__).resolve().parents[1]
    ui_text = (root / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    app_text = (root / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")
    exporter_text = (root / "pneumo_solver_ui" / "npz_bundle.py").read_text(encoding="utf-8")
    run_artifacts_text = (root / "pneumo_solver_ui" / "run_artifacts.py").read_text(encoding="utf-8")

    assert "save_last_baseline_ptr as save_last_baseline_ptr_global" in ui_text
    assert "apply_anim_latest_to_session_global(st.session_state" in ui_text
    assert "apply_anim_latest_to_session_global(" in app_text
    assert "write_anim_latest_pointer_json_global(" in app_text
    assert "write_anim_latest_pointer_json(" in exporter_text
    assert "save_latest_animation_ptr(" in run_artifacts_text
