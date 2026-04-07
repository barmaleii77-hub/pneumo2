from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.compare_ui import load_npz_bundle
from pneumo_solver_ui.desktop_animator.data_bundle import load_npz as load_animator_npz
from pneumo_solver_ui.visual_contract import (
    ROAD_CONTRACT_DESKTOP_JSON_NAME,
    ROAD_CONTRACT_WEB_JSON_NAME,
    build_road_contract_report,
    collect_visual_cache_dependencies,
    collect_visual_contract_status,
    load_visual_road_sidecar,
    visual_cache_dependencies_token,
    write_road_contract_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]


def _write_npz_with_road_sidecar(tmp_path: Path) -> tuple[Path, dict]:
    road_csv = tmp_path / "road.csv"
    road_df = pd.DataFrame(
        {
            "t": [0.0, 0.2, 0.4],
            "z0": [0.00, 0.01, 0.02],
            "z1": [0.00, 0.02, 0.04],
            "z2": [0.00, -0.01, -0.02],
            "z3": [0.00, -0.02, -0.04],
        }
    )
    road_df.to_csv(road_csv, index=False)

    meta = {
        "geometry": {
            "wheelbase_m": 2.7,
            "track_m": 1.64,
        },
        "road_csv": "road.csv",
    }

    npz_path = tmp_path / "bundle.npz"
    cols = np.array(["время_с", "скорость_vx_м_с", "yaw_рад"], dtype=object)
    values = np.column_stack(
        [
            np.array([0.0, 0.1, 0.2, 0.3, 0.4], dtype=float),
            np.ones(5, dtype=float),
            np.zeros(5, dtype=float),
        ]
    )
    np.savez(
        npz_path,
        main_cols=cols,
        main_values=values,
        meta_json=np.array(json.dumps(meta, ensure_ascii=False), dtype=object),
    )
    return npz_path, meta


def test_load_visual_road_sidecar_aligns_to_npz_time_vector(tmp_path: Path) -> None:
    npz_path, meta = _write_npz_with_road_sidecar(tmp_path)
    t = np.array([0.0, 0.1, 0.2, 0.3, 0.4], dtype=float)

    sidecar = load_visual_road_sidecar(npz_path, meta, time_vector=t, context="pytest")

    assert sidecar["ok"] is True
    assert sidecar["available_corners"] == ["ЛП", "ПП", "ЛЗ", "ПЗ"]
    wheels = dict(sidecar["wheels"])
    assert len(wheels["ЛП"]) == 5
    assert abs(float(wheels["ПП"][1]) - 0.01) < 1e-12
    assert abs(float(wheels["ПЗ"][3]) + 0.03) < 1e-12


def test_collect_visual_contract_status_accepts_road_csv_sidecar(tmp_path: Path) -> None:
    npz_path, meta = _write_npz_with_road_sidecar(tmp_path)
    df_main = pd.DataFrame({"время_с": [0.0, 0.1, 0.2, 0.3, 0.4]})

    status = collect_visual_contract_status(
        df_main,
        meta=meta,
        npz_path=npz_path,
        context="pytest visual bundle",
    )

    assert status["geometry_contract_ok"] is True
    assert status["road_complete"] is True
    assert status["road_source"] == "road_csv"
    assert status["road_available_corners"] == ["ЛП", "ПП", "ЛЗ", "ПЗ"]
    assert status["road_overlay_text"] == ""
    assert status["solver_points_complete"] is False
    assert str(status["solver_points_overlay_text"]).startswith("NO SOLVER POINTS")


def test_compare_ui_load_npz_bundle_exposes_visual_contract_and_sidecar(tmp_path: Path) -> None:
    npz_path, _meta = _write_npz_with_road_sidecar(tmp_path)

    bundle = load_npz_bundle(npz_path)

    assert bundle["visual_contract"]["road_complete"] is True
    assert bundle["visual_contract"]["road_source"] == "road_csv"
    assert bundle["meta"]["_visual_contract"]["road_complete"] is True
    assert bundle["meta"]["_geometry_contract_ok"] is True

    road_sidecar_wheels = bundle["road_sidecar_wheels"]
    assert sorted(road_sidecar_wheels.keys()) == ["ЛЗ", "ЛП", "ПЗ", "ПП"]
    assert abs(float(road_sidecar_wheels["ЛП"][2]) - 0.01) < 1e-12
    assert abs(float(road_sidecar_wheels["ПЗ"][4]) + 0.04) < 1e-12


def test_desktop_animator_load_npz_keeps_same_visual_contract(tmp_path: Path) -> None:
    npz_path, _meta = _write_npz_with_road_sidecar(tmp_path)

    bundle = load_animator_npz(npz_path)
    visual_contract = dict(bundle.meta.get("_visual_contract") or {})

    assert visual_contract["road_complete"] is True
    assert visual_contract["road_source"] == "road_csv"
    assert visual_contract["geometry_contract_ok"] is True
    assert visual_contract["road_sidecar_available_corners"] == ["ЛП", "ПП", "ЛЗ", "ПЗ"]


def test_web_sources_use_bundle_visual_contract_and_road_sidecar() -> None:
    validation_text = (ROOT / "pneumo_solver_ui" / "validation_cockpit_web.py").read_text(encoding="utf-8")
    animation_text = (ROOT / "pneumo_solver_ui" / "animation_cockpit_web.py").read_text(encoding="utf-8")

    assert 'road_override=road_sidecar_wheels' in validation_text
    assert 'bun.get("visual_contract")' in validation_text
    assert 'bun.get("road_sidecar_wheels")' in validation_text

    assert 'bun.get("visual_contract")' in animation_text
    assert 'bun.get("road_sidecar_wheels")' in animation_text
    assert 'road_override=road_sidecar_wheels' in animation_text


def test_collect_visual_cache_dependencies_change_when_sidecar_changes(tmp_path: Path) -> None:
    npz_path, meta = _write_npz_with_road_sidecar(tmp_path)
    deps1 = collect_visual_cache_dependencies(npz_path, meta, context="pytest cache deps")

    road_csv = tmp_path / "road.csv"
    road_df = pd.read_csv(road_csv)
    road_df.loc[len(road_df)] = [0.6, 0.03, 0.06, -0.03, -0.06]
    road_df.to_csv(road_csv, index=False)

    deps2 = collect_visual_cache_dependencies(npz_path, meta, context="pytest cache deps")

    assert deps1["npz"] == deps2["npz"]
    assert deps1["road_csv_path"] == deps2["road_csv_path"]
    assert deps1["road_csv"] != deps2["road_csv"]
    assert int(dict(deps2["road_csv"]).get("size") or 0) > int(dict(deps1["road_csv"]).get("size") or 0)


def test_compare_ui_load_npz_bundle_exposes_cache_dependencies(tmp_path: Path) -> None:
    npz_path, _meta = _write_npz_with_road_sidecar(tmp_path)

    bundle = load_npz_bundle(npz_path)
    cache_deps = dict(bundle.get("cache_deps") or {})

    assert cache_deps["npz"]["path"] == str(npz_path.resolve())
    assert cache_deps["road_csv_path"] == str((tmp_path / "road.csv").resolve())
    assert bundle["meta"]["_visual_cache_dependencies"]["road_csv_path"] == cache_deps["road_csv_path"]
    assert cache_deps["road_csv"]["exists"] is True


def test_web_sources_use_visual_cache_dependencies_for_npz_and_sidecar() -> None:
    validation_text = (ROOT / "pneumo_solver_ui" / "validation_cockpit_web.py").read_text(encoding="utf-8")
    animation_text = (ROOT / "pneumo_solver_ui" / "animation_cockpit_web.py").read_text(encoding="utf-8")
    compare_web_text = (ROOT / "pneumo_solver_ui" / "compare_npz_web.py").read_text(encoding="utf-8")

    assert 'collect_visual_cache_dependencies' in validation_text
    assert '_load_npz(pick, cache_deps)' in validation_text
    assert 'bundle_cache_deps = bun.get("cache_deps")' in validation_text
    assert 'fp = dict(bundle_cache_deps)' in validation_text

    assert 'collect_visual_cache_dependencies' in animation_text
    assert '_load_npz(pick, cache_deps)' in animation_text
    assert 'bundle_cache_deps = bun.get("cache_deps")' in animation_text
    assert 'fp = dict(bundle_cache_deps)' in animation_text

    assert 'collect_visual_cache_dependencies' in compare_web_text
    assert '_load_npz(p, cache_deps)' in compare_web_text


def test_visual_cache_dependencies_token_changes_when_sidecar_changes(tmp_path: Path) -> None:
    npz_path, meta = _write_npz_with_road_sidecar(tmp_path)

    deps1 = collect_visual_cache_dependencies(npz_path, meta, context="pytest token")
    token1 = visual_cache_dependencies_token(deps1)
    assert token1

    road_csv = tmp_path / "road.csv"
    road_df = pd.read_csv(road_csv)
    road_df.loc[len(road_df)] = [0.6, 0.03, 0.06, -0.03, -0.06]
    road_df.to_csv(road_csv, index=False)

    deps2 = collect_visual_cache_dependencies(npz_path, meta, context="pytest token")
    token2 = visual_cache_dependencies_token(deps2)

    assert token2
    assert token1 != token2


def test_desktop_animator_load_npz_exposes_visual_cache_dependencies(tmp_path: Path) -> None:
    npz_path, _meta = _write_npz_with_road_sidecar(tmp_path)

    bundle = load_animator_npz(npz_path)
    deps = dict(bundle.meta.get("_visual_cache_dependencies") or {})

    assert deps["npz"]["path"] == str(npz_path.resolve())
    assert deps["road_csv_path"] == str((tmp_path / "road.csv").resolve())
    assert bundle.meta["_visual_cache_token"] == visual_cache_dependencies_token(deps)


def test_desktop_animator_follow_uses_visual_dependency_token_source_check() -> None:
    app_text = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")
    data_bundle_text = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "data_bundle.py").read_text(encoding="utf-8")

    assert 'collect_visual_cache_dependencies(' in app_text
    assert 'visual_cache_dependencies_token(deps)' in app_text
    assert '_last_deps_token' in app_text
    assert 'Reload (' in app_text

    assert 'meta["_visual_cache_dependencies"]' in data_bundle_text
    assert 'meta["_visual_cache_token"]' in data_bundle_text


def test_build_road_contract_report_is_consumer_specific_and_marks_derived_width(tmp_path: Path) -> None:
    npz_path, meta = _write_npz_with_road_sidecar(tmp_path)
    df_main = pd.DataFrame({"время_с": [0.0, 0.1, 0.2, 0.3, 0.4]})
    t = np.asarray(df_main["время_с"], dtype=float)

    web = build_road_contract_report(
        df_main,
        meta=meta,
        npz_path=npz_path,
        time_vector=t,
        consumer="web",
        updated_utc="2026-03-31T00:00:00Z",
    )
    desktop = build_road_contract_report(
        df_main,
        meta=meta,
        npz_path=npz_path,
        time_vector=t,
        consumer="desktop",
        updated_utc="2026-03-31T00:00:00Z",
    )

    assert web["consumer"] == "web"
    assert desktop["consumer"] == "desktop"
    assert web["road_complete"] is True
    assert desktop["road_complete"] is True
    assert web["road_source"] == "road_csv"
    assert desktop["road_source"] == "road_csv"
    assert web["road_width_status"] == "derived_from_track_and_wheel_width"
    assert desktop["road_width_status"] == "derived_from_track_and_wheel_width"
    assert abs(float(web["effective_road_width_m"]) - 1.64) < 1e-12
    assert abs(float(desktop["effective_road_width_m"]) - 1.64) < 1e-12
    assert web["level"] == "WARN"
    assert desktop["level"] == "WARN"


def test_write_road_contract_artifacts_exports_web_and_desktop_json(tmp_path: Path) -> None:
    npz_path, meta = _write_npz_with_road_sidecar(tmp_path)
    df_main = pd.DataFrame({"время_с": [0.0, 0.1, 0.2, 0.3, 0.4]})
    t = np.asarray(df_main["время_с"], dtype=float)

    exports = write_road_contract_artifacts(
        tmp_path,
        df_main_or_columns=df_main,
        meta=meta,
        npz_path=npz_path,
        pointer_path=tmp_path / "anim_latest.json",
        updated_utc="2026-03-31T00:00:00Z",
        time_vector=t,
    )

    web_path = tmp_path / ROAD_CONTRACT_WEB_JSON_NAME
    desktop_path = tmp_path / ROAD_CONTRACT_DESKTOP_JSON_NAME
    assert web_path.exists() is True
    assert desktop_path.exists() is True
    assert exports["road_contract_web_path"] == str(web_path)
    assert exports["road_contract_desktop_path"] == str(desktop_path)

    web_obj = json.loads(web_path.read_text(encoding="utf-8"))
    desktop_obj = json.loads(desktop_path.read_text(encoding="utf-8"))
    assert web_obj["consumer"] == "web"
    assert desktop_obj["consumer"] == "desktop"
    assert web_obj["road_source"] == "road_csv"
    assert desktop_obj["road_source"] == "road_csv"
