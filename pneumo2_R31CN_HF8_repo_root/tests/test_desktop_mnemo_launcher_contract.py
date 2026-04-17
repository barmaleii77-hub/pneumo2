from __future__ import annotations

from pathlib import Path


def test_desktop_mnemo_is_launchable_from_streamlit_shells() -> None:
    repo = Path(__file__).resolve().parents[1]
    home_src = (repo / "pneumo_solver_ui" / "pneumo_ui_app.py").read_text(encoding="utf-8")
    legacy_src = (repo / "pneumo_solver_ui" / "app.py").read_text(encoding="utf-8")

    assert "launch_desktop_mnemo_follow" in home_src
    assert "pneumo_solver_ui.desktop_mnemo.main" in home_src
    assert "pneumo_solver_ui.desktop_mnemo.main" in legacy_src
    assert "launch_desktop_mnemo" in legacy_src


def test_desktop_mnemo_launcher_contract_keeps_specialized_window_scope(tmp_path: Path) -> None:
    from pneumo_solver_ui.desktop_mnemo.main import build_desktop_mnemo_launch_contract

    npz_path = tmp_path / "case.npz"
    pointer_path = tmp_path / "anim_latest.json"
    contract = build_desktop_mnemo_launch_contract(
        [
            "--npz",
            str(npz_path),
            "--follow",
            "--pointer",
            str(pointer_path),
            "--startup-view-mode",
            "overview",
            "--startup-edge",
            "регулятор_до_себя_Pmid_сброс",
            "--startup-check",
            "Проверить source markers.",
        ]
    )

    assert contract["schema_version"] == "desktop_mnemo_launch_contract_v1"
    assert contract["window_kind"] == "desktop_mnemo_specialized_window"
    assert contract["separate_specialized_window"] is True
    assert contract["launch_mode"] == "follow"
    assert contract["follow_enabled"] is True
    assert contract["npz_path"].endswith("case.npz")
    assert contract["pointer_path"].endswith("anim_latest.json")
    assert contract["startup_view_mode"] == "overview"
    assert contract["startup_edge"] == "регулятор_до_себя_Pmid_сброс"
    assert contract["does_not_duplicate"] == {
        "animator_3d_scene": True,
        "compare_viewer": True,
        "input_editor": True,
    }

    npz_contract = build_desktop_mnemo_launch_contract(["--npz", str(npz_path), "--startup-node", "Ресивер3"])
    assert npz_contract["launch_mode"] == "npz"
    assert npz_contract["follow_enabled"] is False
    assert npz_contract["npz_path"].endswith("case.npz")
    assert npz_contract["startup_node"] == "Ресивер3"
    assert npz_contract["does_not_duplicate"]["animator_3d_scene"] is True

    blank_contract = build_desktop_mnemo_launch_contract(["--pointer", str(pointer_path)])
    assert blank_contract["launch_mode"] == "blank"
    assert blank_contract["npz_path"] == ""
    assert blank_contract["pointer_path"].endswith("anim_latest.json")
    assert blank_contract["does_not_duplicate"]["compare_viewer"] is True
