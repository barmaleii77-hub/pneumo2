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
    assert "--startup-check" in src
    assert "startup_preset=str(args.startup_preset or \"\")" in src
    assert "startup_title=str(args.startup_title or \"\")" in src
    assert "startup_reason=str(args.startup_reason or \"\")" in src
    assert "startup_view_mode=str(args.startup_view_mode or \"\")" in src
    assert "startup_checklist=list(args.startup_check or [])" in src
