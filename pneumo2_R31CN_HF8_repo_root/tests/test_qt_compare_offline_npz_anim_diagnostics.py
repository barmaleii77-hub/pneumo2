from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.compare_ui import load_npz_bundle
from pneumo_solver_ui.npz_bundle import export_anim_latest_bundle
from pneumo_solver_ui.run_artifacts import collect_anim_latest_diagnostics_summary, save_latest_animation_ptr
from pneumo_solver_ui.solver_points_contract import CORNERS, POINT_KINDS, point_cols
from pneumo_solver_ui.tools.inspect_npz_bundle import inspect_npz_bundle, render_inspect_npz_bundle_md
from pneumo_solver_ui.visual_contract import collect_visual_cache_dependencies, visual_cache_dependencies_token


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




def test_visual_cache_token_ignores_context_labels(tmp_path: Path) -> None:
    npz_path = tmp_path / "bundle.npz"
    npz_path.write_bytes(b"npz placeholder")
    road_csv = tmp_path / "road.csv"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n", encoding="utf-8")
    meta = {"road_csv": "road.csv"}

    deps_a = collect_visual_cache_dependencies(npz_path, meta=meta, context="context A")
    deps_b = collect_visual_cache_dependencies(npz_path, meta=meta, context="context B")

    assert deps_a["context"] != deps_b["context"]
    assert visual_cache_dependencies_token(deps_a) == visual_cache_dependencies_token(deps_b)

def _build_workspace_bundle(tmp_path: Path, monkeypatch) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    exports_dir = workspace / "exports"
    triage_dir = tmp_path / "triage"
    road_csv = tmp_path / "road.csv"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n", encoding="utf-8")
    road_csv = tmp_path / "road.csv"
    road_csv.write_text("t,z0,z1,z2,z3\n0,0,0,0,0\n0.1,0.01,0.02,-0.01,-0.02\n", encoding="utf-8")

    npz_path, ptr_path = export_anim_latest_bundle(
        exports_dir=exports_dir,
        df_main=_solver_df(),
        meta={
            "source": "pytest",
            "geometry": {"wheelbase_m": 2.8, "track_m": 1.6},
            "road_csv": str(road_csv),
        },
    )

    monkeypatch.setenv("PNEUMO_WORKSPACE_DIR", str(workspace))
    info = save_latest_animation_ptr(npz_path=npz_path, pointer_json=ptr_path, meta={"source": "pytest"})
    triage_dir.mkdir(parents=True, exist_ok=True)
    triage_json = triage_dir / "latest_anim_pointer_diagnostics.json"
    triage_json.write_text(
        json.dumps(collect_anim_latest_diagnostics_summary(info, include_meta=True), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return npz_path, ptr_path, triage_json


def test_compare_ui_load_npz_bundle_exposes_anim_diagnostics(tmp_path: Path, monkeypatch) -> None:
    npz_path, ptr_path, triage_json = _build_workspace_bundle(tmp_path, monkeypatch)

    bundle = load_npz_bundle(npz_path)
    anim = dict(bundle.get("anim_diagnostics") or {})

    assert anim["bundle_visual_cache_token"]
    assert anim["pointer_visual_cache_token"] == anim["bundle_visual_cache_token"]
    assert anim["bundle_vs_pointer_token_match"] is True
    assert anim["bundle_vs_pointer_reload_inputs_match"] is True
    assert anim["bundle_vs_pointer_npz_path_match"] is True
    assert set(anim["pointer_sources_present"]) == {"local_pointer", "global_pointer", "triage_diagnostics"}
    assert anim["local_pointer_json"] == str(ptr_path.resolve())
    assert anim["triage_diagnostics_json"] == str(triage_json.resolve())
    assert bundle["meta"]["_anim_diagnostics"]["bundle_visual_cache_token"] == anim["bundle_visual_cache_token"]
    assert bundle["meta"]["_visual_cache_token"] == anim["bundle_visual_cache_token"]


def test_npz_anim_diagnostics_detect_path_mismatch_after_copy(tmp_path: Path, monkeypatch) -> None:
    npz_path, _ptr_path, _triage_json = _build_workspace_bundle(tmp_path, monkeypatch)

    moved_root = tmp_path / "extracted"
    moved_exports = moved_root / "workspace" / "exports"
    moved_pointers = moved_root / "workspace" / "_pointers"
    moved_triage = moved_root / "triage"
    moved_exports.mkdir(parents=True, exist_ok=True)
    moved_pointers.mkdir(parents=True, exist_ok=True)
    moved_triage.mkdir(parents=True, exist_ok=True)

    shutil.copy2(npz_path, moved_exports / "anim_latest.npz")
    shutil.copy2(npz_path.with_name("anim_latest.json"), moved_exports / "anim_latest.json")
    shutil.copy2(npz_path.with_name("anim_latest_road_csv.csv"), moved_exports / "anim_latest_road_csv.csv")
    shutil.copy2(tmp_path / "workspace" / "_pointers" / "anim_latest.json", moved_pointers / "anim_latest.json")
    shutil.copy2(tmp_path / "triage" / "latest_anim_pointer_diagnostics.json", moved_triage / "latest_anim_pointer_diagnostics.json")

    bundle = load_npz_bundle(moved_exports / "anim_latest.npz")
    anim = dict(bundle.get("anim_diagnostics") or {})

    assert anim["bundle_visual_cache_token"]
    assert anim["pointer_visual_cache_token"]
    assert anim["bundle_vs_pointer_token_match"] is False
    assert anim["bundle_vs_pointer_npz_path_match"] is False
    assert any("adjacent" not in msg for msg in anim["issues"])  # real mismatch issues survive


def test_inspect_npz_bundle_reports_anim_diagnostics(tmp_path: Path, monkeypatch) -> None:
    npz_path, _ptr_path, _triage_json = _build_workspace_bundle(tmp_path, monkeypatch)

    rep = inspect_npz_bundle(npz_path)
    md = render_inspect_npz_bundle_md(rep)

    assert rep["visual_contract"]["geometry_contract_ok"] is True
    assert rep["anim_diagnostics"]["bundle_visual_cache_token"]
    assert rep["anim_diagnostics"]["pointer_visual_cache_token"]
    assert rep["anim_diagnostics"]["bundle_vs_pointer_token_match"] is True
    assert "## Anim diagnostics" in md
    assert "current token" in md


def test_qt_compare_viewer_sources_reference_anim_diagnostics_panel() -> None:
    text = (ROOT / "pneumo_solver_ui" / "qt_compare_viewer.py").read_text(encoding="utf-8")

    assert "format_anim_diagnostics_lines" in text
    assert "self.txt_anim_diag" in text
    assert "anim_diagnostics: Dict" in text
    assert "anim_diagnostics=dict(b.get('anim_diagnostics') or {})" in text
    assert "Road source:" in text
