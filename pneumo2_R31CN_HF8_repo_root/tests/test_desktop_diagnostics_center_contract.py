from __future__ import annotations

import json
import zipfile
from pathlib import Path

from pneumo_solver_ui.desktop_diagnostics_model import (
    LATEST_DESKTOP_DIAGNOSTICS_RUN_JSON,
    LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD,
    LATEST_SEND_BUNDLE_INSPECTION_JSON,
    DesktopDiagnosticsRequest,
    DesktopDiagnosticsRunRecord,
    build_run_full_diagnostics_command,
    parse_run_full_diagnostics_output_line,
)
from pneumo_solver_ui.desktop_diagnostics_runtime import (
    append_desktop_diagnostics_run_log,
    load_last_desktop_diagnostics_center_state,
    load_last_desktop_diagnostics_run_record,
    load_last_desktop_diagnostics_run_log_text,
    persist_desktop_diagnostics_run,
    refresh_desktop_diagnostics_bundle_record,
    write_desktop_diagnostics_summary_md,
    write_desktop_diagnostics_center_state,
)


ROOT = Path(__file__).resolve().parents[1]


def test_desktop_diagnostics_model_builds_headless_command_and_parses_paths() -> None:
    req = DesktopDiagnosticsRequest(
        level="full",
        skip_ui_smoke=True,
        no_zip=True,
        run_opt_smoke=True,
        opt_minutes=5,
        opt_jobs=3,
        osc_dir="C:/tmp/osc",
        out_root="C:/tmp/diagnostics",
    )

    cmd = build_run_full_diagnostics_command("python", Path("tool.py"), req)
    assert cmd == [
        "python",
        "tool.py",
        "--level",
        "full",
        "--skip_ui_smoke",
        "--no_zip",
        "--run_opt_smoke",
        "--opt_minutes",
        "5",
        "--opt_jobs",
        "3",
        "--osc_dir",
        "C:/tmp/osc",
        "--out_root",
        "C:/tmp/diagnostics",
    ]

    assert parse_run_full_diagnostics_output_line("Run dir: C:/tmp/run") == {"run_dir": "C:/tmp/run"}
    assert parse_run_full_diagnostics_output_line("Zip: C:/tmp/run.zip") == {"zip_path": "C:/tmp/run.zip"}
    assert parse_run_full_diagnostics_output_line("noop") == {}


def test_desktop_diagnostics_runtime_persists_machine_readable_bundle_and_run_state(tmp_path: Path) -> None:
    out_dir = tmp_path / "send_bundles"
    out_dir.mkdir()

    zip_path = out_dir / "latest_send_bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "bundle/meta.json",
            json.dumps({"release": "TEST", "run_id": "R1", "created_at": "2026-04-13 00:00:00"}),
        )

    (out_dir / "last_bundle_meta.json").write_text(
        json.dumps(
            {
                "ok": True,
                "summary_lines": ["Anim latest token: tok-123"],
                "zip": {"path": str(zip_path.resolve()), "name": zip_path.name, "size_bytes": zip_path.stat().st_size},
                "anim_pointer_diagnostics_path": str((out_dir / "latest_anim_pointer_diagnostics.json").resolve()),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "latest_send_bundle_validation.json").write_text(
        json.dumps(
            {
                "anim_latest": {
                    "visual_cache_token": "tok-123",
                    "visual_reload_inputs": ["anim_latest.npz"],
                    "npz_path": "workspace/exports/anim_latest.npz",
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "latest_send_bundle_clipboard_status.json").write_text(
        json.dumps({"ok": True, "message": "powershell ok", "zip_path": str(zip_path.resolve())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    bundle = refresh_desktop_diagnostics_bundle_record(tmp_path, out_dir=out_dir, zip_path=zip_path)
    assert bundle.latest_zip_path == str(zip_path.resolve())
    assert "Anim latest token: tok-123" in bundle.summary_lines
    assert Path(bundle.latest_inspection_json_path).exists()
    assert Path(bundle.latest_health_json_path).exists()

    run = DesktopDiagnosticsRunRecord(
        ok=True,
        started_at="2026-04-13 00:00:00",
        finished_at="2026-04-13 00:05:00",
        status="finished",
        command=["python", "tool.py"],
        returncode=0,
        out_root=str((tmp_path / "diagnostics").resolve()),
        last_message="OK",
    )
    append_desktop_diagnostics_run_log(tmp_path / "diagnostics", "line-1\n")
    append_desktop_diagnostics_run_log(tmp_path / "diagnostics", "line-2\n")
    assert load_last_desktop_diagnostics_run_log_text(tmp_path / "diagnostics") == "line-1\nline-2\n"
    run = persist_desktop_diagnostics_run(tmp_path / "diagnostics", run, log_text="diagnostics log")
    assert Path(run.state_path).exists()
    assert Path(run.log_path).exists()
    loaded_run = load_last_desktop_diagnostics_run_record(tmp_path / "diagnostics")
    assert loaded_run is not None
    assert loaded_run.status == "finished"
    assert loaded_run.returncode == 0
    assert loaded_run.last_message == "OK"
    assert load_last_desktop_diagnostics_run_log_text(tmp_path / "diagnostics") == "diagnostics log"

    summary_md = write_desktop_diagnostics_summary_md(out_dir, "# Desktop diagnostics/send summary\n")
    center_state = write_desktop_diagnostics_center_state(
        out_dir,
        bundle_record=bundle,
        run_record=run,
        summary_md_path=summary_md,
        ui_state={
            "selected_tab": "bundle",
            "bundle_busy": False,
            "level": "full",
            "out_root": str((tmp_path / "diagnostics").resolve()),
            "active_bundle_out_dir": str(out_dir.resolve()),
        },
    )
    payload = json.loads(center_state.read_text(encoding="utf-8"))
    loaded_center_state = load_last_desktop_diagnostics_center_state(out_dir)
    assert summary_md.name == LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD
    assert payload["machine_paths"]["latest_summary_md"].endswith(LATEST_DESKTOP_DIAGNOSTICS_SUMMARY_MD)
    assert payload["machine_paths"]["latest_bundle_inspection_json"].endswith(LATEST_SEND_BUNDLE_INSPECTION_JSON)
    assert payload["machine_paths"]["latest_run_state_json"].endswith(LATEST_DESKTOP_DIAGNOSTICS_RUN_JSON)
    assert payload["bundle"]["latest_clipboard_status_path"].endswith("latest_send_bundle_clipboard_status.json")
    assert payload["ui"]["selected_tab"] == "bundle"
    assert payload["ui"]["active_bundle_out_dir"].endswith("send_bundles")
    assert loaded_center_state["ui"]["level"] == "full"
    assert loaded_center_state["ui"]["out_root"].endswith("diagnostics")
    assert loaded_center_state["ui"]["selected_tab"] == "bundle"


def test_diagnostics_and_send_wrappers_delegate_to_shared_desktop_center() -> None:
    diag_src = (ROOT / "pneumo_solver_ui" / "tools" / "run_full_diagnostics_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    send_src = (ROOT / "pneumo_solver_ui" / "tools" / "send_results_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    center_src = (ROOT / "pneumo_solver_ui" / "tools" / "desktop_diagnostics_center.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "DesktopDiagnosticsCenter" in diag_src
    assert 'initial_tab="diagnostics"' in diag_src
    assert "DesktopDiagnosticsCenter" in send_src
    assert 'initial_tab="send"' in send_src
    assert "latest_send_bundle_clipboard_status.json" in send_src
    assert "ZIP для отправки в чат готов и уже скопирован в буфер." in send_src
    assert "Anim pointer diagnostics:" in send_src
    assert "load_desktop_diagnostics_bundle_record" in send_src
    assert "ttk.Notebook" in center_src
    assert "write_desktop_diagnostics_center_state" in center_src
    assert "machine-readable" in center_src.lower()
    assert "copy_latest_bundle_to_clipboard(" in center_src
    assert "out_dir=self._active_bundle_out_dir()" in center_src
    assert "def _schedule_poll(self) -> None:" in center_src
    assert "def _poll_external_state(self) -> None:" in center_src
    assert "def _compute_external_state_signature(self) -> tuple[str, ...]:" in center_src
    assert "load_last_desktop_diagnostics_center_state" in center_src
    assert "append_desktop_diagnostics_run_log" in center_src
    assert "load_last_desktop_diagnostics_run_record" in center_src
    assert "load_last_desktop_diagnostics_run_log_text" in center_src
    assert "def _restore_bundle_state_from_last_center_state(self) -> None:" in center_src
    assert "def _restore_diagnostics_request_from_last_center_state(self) -> None:" in center_src
    assert "def _resolve_initial_tab_name(self, initial_tab: str) -> str:" in center_src
    assert "## Last diagnostics run" in center_src
    assert "status=\"running\"" in center_src
    assert "status=\"stopping\"" in center_src
    assert "- status:" in center_src
    assert "latest_desktop_diagnostics_summary.md" in center_src
    assert 'DesktopDiagnosticsCenter(root, initial_tab="restore")' in center_src
    assert "<<NotebookTabChanged>>" in center_src
    assert 'self._poll_after_id = self.root.after(1000, self._poll_external_state)' in center_src
    assert "self.root.after_cancel(self._poll_after_id)" in center_src


def test_test_center_integration_reuses_existing_latest_bundle_when_opening_send_center() -> None:
    src = (ROOT / "pneumo_solver_ui" / "tools" / "test_center_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    send_src = (ROOT / "pneumo_solver_ui" / "tools" / "send_results_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )

    assert "Diagnostics / Send Center" in src
    assert 'env["PNEUMO_SEND_RESULTS_REUSE_LATEST"] = "1"' in src
    assert "launch_send_results_gui(env=env)" in src or "subprocess.Popen([self.py, str(send_gui)], cwd=str(self.repo), env=env)" in src
    assert 'os.environ.get("PNEUMO_SEND_RESULTS_REUSE_LATEST", "0")' in send_src
    assert "auto_build_bundle=(not reuse_latest) or (not bundle_state.latest_zip_path)" in send_src


def test_legacy_wrapper_helpers_remain_available_for_hidden_launcher_contracts() -> None:
    import pneumo_solver_ui.tools.run_full_diagnostics_gui as diag_module
    import pneumo_solver_ui.tools.send_results_gui as send_module

    assert hasattr(diag_module, "ROOT")
    assert hasattr(diag_module, "TOOLS_DIR")
    assert callable(diag_module._guess_python_exe)
    assert callable(diag_module._open_in_explorer)

    assert callable(send_module._repo_root)
    assert callable(send_module._log_dir)
    assert callable(send_module._sha256_file)
    assert callable(send_module._safe_write_text)
    assert callable(send_module._is_full_file_clipboard_success)
    assert hasattr(send_module.SendResultsGUI, "_write_clipboard_status")
    assert hasattr(send_module.SendResultsGUI, "_worker")
    assert hasattr(send_module.SendResultsGUI, "_poll")
    send_src = (ROOT / "pneumo_solver_ui" / "tools" / "send_results_gui.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    assert "send_results_gui_error.log" in send_src
    assert "send_results_gui_crash.log" in send_src
