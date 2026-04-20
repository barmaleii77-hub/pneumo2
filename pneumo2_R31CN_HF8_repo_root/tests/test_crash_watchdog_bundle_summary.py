from __future__ import annotations

import sys
import types
from pathlib import Path

from pneumo_solver_ui.diagnostics_entrypoint import DiagnosticsBuildResult
from pneumo_solver_ui import crash_guard
from pneumo_solver_ui.tools import postmortem_watchdog


def test_crash_guard_autosave_emits_shared_bundle_summary_event(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    zip_path = repo_root / "send_bundles" / "latest_send_bundle.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(b"zip")

    captured: list[tuple[str, str, dict]] = []

    def _fake_build_full_diagnostics_bundle(**_kwargs):
        return DiagnosticsBuildResult(
            ok=True,
            zip_path=zip_path,
            message="OK",
            meta={
                "summary_lines": [
                    "Данные производительности анимации: trace_bundle_ready / PASS / готовы_в_архиве=True",
                    "Сравнение производительности анимации: regression_checked / PASS / готово=True",
                    "Шов кольца: замыкание=strict_exact / открыт=True / скачок_м=0.012 / исходный_скачок_м=0.015",
                ],
                "anim_latest_summary": {
                    "scenario_kind": "ring",
                    "ring_closure_policy": "strict_exact",
                    "ring_closure_applied": False,
                    "ring_seam_open": True,
                    "ring_seam_max_jump_m": 0.012,
                    "ring_raw_seam_max_jump_m": 0.015,
                },
                "anim_pointer_diagnostics_path": str(zip_path.parent / "latest_anim_pointer_diagnostics.json"),
            },
        )

    monkeypatch.setenv("PNEUMO_AUTO_SEND_BUNDLE", "1")
    monkeypatch.setenv("PNEUMO_AUTOSAVE_BUNDLE_ON_EXIT", "1")
    monkeypatch.setattr(crash_guard, "_repo_root", lambda: repo_root)
    monkeypatch.setattr(crash_guard, "_load_diag_cfg", lambda: None)
    monkeypatch.setattr(crash_guard, "_event", lambda event, message="", **fields: captured.append((event, message, fields)))
    monkeypatch.setattr("pneumo_solver_ui.diagnostics_entrypoint.build_full_diagnostics_bundle", _fake_build_full_diagnostics_bundle)

    saved = crash_guard.try_autosave_bundle(reason="exit", fatal=False)

    assert saved == zip_path
    assert captured
    event, _message, fields = captured[-1]
    assert event == "autosave_bundle"
    assert fields["where"] == "exit"
    assert fields["bundle_ok"] is True
    assert fields["summary_lines"][0].startswith("Данные производительности анимации:")
    assert fields["scenario_kind"] == "ring"
    assert fields["ring_closure_policy"] == "strict_exact"
    assert fields["ring_seam_open"] is True
    assert fields["ring_seam_max_jump_m"] == 0.012
    assert fields["anim_pointer_diagnostics_path"].endswith("latest_anim_pointer_diagnostics.json")


def test_postmortem_watchdog_logs_and_emits_bundle_summary(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    out_dir = repo_root / "send_bundles"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "latest_send_bundle.zip"
    zip_path.write_bytes(b"zip")
    log_path = out_dir / "_postmortem_watchdog.log"

    captured_events: list[dict] = []

    def _fake_build_full_diagnostics_bundle(**_kwargs):
        return DiagnosticsBuildResult(
            ok=True,
            zip_path=zip_path,
            message="OK",
            meta={
                "summary_lines": [
                    "Данные производительности анимации: trace_bundle_ready / PASS / готовы_в_архиве=True",
                    "Сравнение производительности анимации: regression_checked / PASS / готово=True",
                    "Шов кольца: замыкание=strict_exact / открыт=True / скачок_м=0.012 / исходный_скачок_м=0.015",
                ],
                "anim_latest_summary": {
                    "scenario_kind": "ring",
                    "ring_closure_policy": "strict_exact",
                    "ring_closure_applied": False,
                    "ring_seam_open": True,
                    "ring_seam_max_jump_m": 0.012,
                    "ring_raw_seam_max_jump_m": 0.015,
                },
                "anim_pointer_diagnostics_path": str(out_dir / "latest_anim_pointer_diagnostics.json"),
            },
        )

    monkeypatch.setattr(postmortem_watchdog, "_repo_root", lambda: repo_root)
    monkeypatch.setattr(postmortem_watchdog, "pid_alive", lambda _pid: False)
    monkeypatch.setattr(postmortem_watchdog.time, "sleep", lambda _s: None)
    monkeypatch.setattr(sys, "argv", ["postmortem_watchdog.py", "--target_pid", "123"])
    monkeypatch.setattr("pneumo_solver_ui.diagnostics_entrypoint.load_diagnostics_config", lambda _repo: None)
    monkeypatch.setattr("pneumo_solver_ui.diagnostics_entrypoint.build_full_diagnostics_bundle", _fake_build_full_diagnostics_bundle)
    monkeypatch.setitem(
        sys.modules,
        "pneumo_solver_ui.run_registry",
        types.SimpleNamespace(append_event=lambda payload: captured_events.append(dict(payload))),
    )

    rc = postmortem_watchdog.main()

    assert rc == 0
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    assert "архив проекта сохранён:" in log_text
    assert "Данные производительности анимации: trace_bundle_ready / PASS / готовы_в_архиве=True" in log_text
    assert "Сравнение производительности анимации: regression_checked / PASS / готово=True" in log_text
    assert "Шов кольца: замыкание=strict_exact / открыт=True / скачок_м=0.012 / исходный_скачок_м=0.015" in log_text
    assert "Данные последней анимации:" in log_text
    assert "bundle OK" not in log_text
    assert "Сведения указателя анимации:" not in log_text
    assert "Anim pointer diagnostics:" not in log_text
    assert captured_events
    assert captured_events[-1]["summary_lines"][0].startswith("Данные производительности анимации:")
    assert captured_events[-1]["scenario_kind"] == "ring"
    assert captured_events[-1]["ring_closure_policy"] == "strict_exact"
    assert captured_events[-1]["ring_seam_open"] is True
    assert captured_events[-1]["anim_pointer_diagnostics_path"].endswith("latest_anim_pointer_diagnostics.json")
