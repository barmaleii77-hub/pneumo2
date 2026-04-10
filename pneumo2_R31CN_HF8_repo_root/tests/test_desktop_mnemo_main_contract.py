from __future__ import annotations

from pathlib import Path


def test_desktop_mnemo_main_accepts_startup_onboarding_args() -> None:
    src = (
        Path(__file__).resolve().parents[1]
        / "pneumo_solver_ui"
        / "desktop_mnemo"
        / "main.py"
    ).read_text(encoding="utf-8")

    assert "--startup-preset" in src
    assert "--startup-title" in src
    assert "--startup-reason" in src
    assert "--startup-view-mode" in src
    assert "--startup-time-s" in src
    assert "--startup-time-label" in src
    assert "--startup-edge" in src
    assert "--startup-node" in src
    assert "--startup-event-title" in src
    assert "--startup-time-ref-npz" in src
    assert "--startup-check" in src
    assert "startup_preset=str(args.startup_preset or \"\")" in src
    assert "startup_title=str(args.startup_title or \"\")" in src
    assert "startup_reason=str(args.startup_reason or \"\")" in src
    assert "startup_view_mode=str(args.startup_view_mode or \"\")" in src
    assert "startup_time_s=(float(args.startup_time_s) if args.startup_time_s is not None else None)" in src
    assert "startup_time_label=str(args.startup_time_label or \"\")" in src
    assert "startup_edge=str(args.startup_edge or \"\")" in src
    assert "startup_node=str(args.startup_node or \"\")" in src
    assert "startup_event_title=str(args.startup_event_title or \"\")" in src
    assert "startup_time_ref_npz=str(args.startup_time_ref_npz or \"\")" in src
    assert "startup_checklist=list(args.startup_check or [])" in src
