from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.compare_ui import load_npz_bundle
from pneumo_solver_ui.geometry_acceptance_contract import (
    collect_geometry_acceptance_from_frame,
    collect_geometry_acceptance_from_npz,
    format_geometry_acceptance_summary_lines,
)
from pneumo_solver_ui.tools.health_report import build_health_report
from pneumo_solver_ui.tools.inspect_send_bundle import inspect_send_bundle, render_inspection_md


ROOT = Path(__file__).resolve().parents[1]
CORNERS = ("ЛП", "ПП", "ЛЗ", "ПЗ")


def _make_df() -> pd.DataFrame:
    t = np.array([0.0, 0.1, 0.2], dtype=float)
    data: dict[str, np.ndarray] = {"время_с": t}
    xy_map = {
        "ЛП": (0.75, 0.50),
        "ПП": (0.75, -0.50),
        "ЛЗ": (-0.75, 0.50),
        "ПЗ": (-0.75, -0.50),
    }
    frame_z = np.array([0.50, 0.51, 0.49], dtype=float)
    wheel_z = np.array([0.30, 0.31, 0.29], dtype=float)
    road_z = np.array([0.00, 0.00, 0.00], dtype=float)
    for c in CORNERS:
        x, y = xy_map[c]
        data[f"рама_относительно_дороги_{c}_м"] = frame_z - road_z
        data[f"колесо_относительно_дороги_{c}_м"] = wheel_z - road_z
        data[f"колесо_относительно_рамы_{c}_м"] = wheel_z - frame_z
        data[f"frame_corner_{c}_x_м"] = np.array([x, x, x], dtype=float)
        data[f"frame_corner_{c}_y_м"] = np.array([y, y, y], dtype=float)
        data[f"frame_corner_{c}_z_м"] = frame_z.copy()
        data[f"wheel_center_{c}_x_м"] = np.array([x, x, x], dtype=float)
        data[f"wheel_center_{c}_y_м"] = np.array([y, y, y], dtype=float)
        data[f"wheel_center_{c}_z_м"] = wheel_z.copy()
        data[f"road_contact_{c}_x_м"] = np.array([x, x, x], dtype=float)
        data[f"road_contact_{c}_y_м"] = np.array([y, y, y], dtype=float)
        data[f"road_contact_{c}_z_м"] = road_z.copy()
    return pd.DataFrame(data)


def _write_npz(path: Path) -> Path:
    df = _make_df()
    np.savez_compressed(
        path,
        main_cols=np.array(list(df.columns), dtype=object),
        main_values=df.to_numpy(dtype=float),
        meta_json=json.dumps({"geometry": {"wheelbase_m": 1.5, "track_m": 1.0}}, ensure_ascii=False),
    )
    return path


def test_geometry_acceptance_contract_from_frame_and_npz(tmp_path: Path) -> None:
    df = _make_df()
    summary = collect_geometry_acceptance_from_frame(df)
    assert summary["available"] is True
    assert summary["ok"] is True
    assert summary["level"] == "ok"
    assert abs(float(summary["frame_road_min_m"]) - 0.49) <= 1e-12
    assert abs(float(summary["wheel_road_min_m"]) - 0.29) <= 1e-12
    lines = format_geometry_acceptance_summary_lines(summary)
    assert any("рама‑дорога min" in x for x in lines)
    assert any("WF/WR/FR" in x for x in lines)

    npz_path = _write_npz(tmp_path / "ga_ok.npz")
    npz_summary = collect_geometry_acceptance_from_npz(npz_path)
    assert npz_summary["ok"] is True


def test_compare_ui_load_bundle_exposes_geometry_acceptance(tmp_path: Path) -> None:
    npz_path = _write_npz(tmp_path / "bundle.npz")
    bundle = load_npz_bundle(npz_path)
    ga = dict(bundle.get("geometry_acceptance") or {})
    meta = dict(bundle.get("meta") or {})
    assert ga["ok"] is True
    assert meta["_geometry_acceptance_ok"] is True
    assert meta["_geometry_acceptance_level"] == "ok"


def test_health_report_and_inspector_surface_geometry_acceptance(tmp_path: Path) -> None:
    npz_path = _write_npz(tmp_path / "anim_latest.npz")
    raw_npz = npz_path.read_bytes()
    zip_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("bundle/meta.json", json.dumps({"release": "pytest-ga"}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/manifest.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/summary.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("bundle/skips.json", json.dumps([], ensure_ascii=False, indent=2))
        zf.writestr("bundle/README_SEND_BUNDLE.txt", "README")
        zf.writestr("MANIFEST.json", json.dumps({}, ensure_ascii=False, indent=2))
        zf.writestr("workspace/exports/anim_latest.npz", raw_npz)

    json_path, md_path = build_health_report(zip_path, out_dir=tmp_path)
    assert json_path is not None and json_path.exists()
    rep = json.loads(json_path.read_text(encoding="utf-8"))
    geom = dict(rep.get("signals", {}).get("geometry_acceptance") or {})
    assert geom["ok"] is True
    assert geom["level"] == "ok"
    assert md_path is not None and "Geometry acceptance" in md_path.read_text(encoding="utf-8")

    summary = inspect_send_bundle(zip_path)
    assert summary["has_geometry_acceptance"] is True
    assert summary["geometry_acceptance"]["ok"] is True
    md = render_inspection_md(summary)
    assert "## Geometry acceptance" in md
    assert "рама‑дорога min" in md


def test_sources_wire_geometry_acceptance_into_compare_validation_qt_and_bundle_summaries() -> None:
    compare_text = (ROOT / "pneumo_solver_ui" / "compare_npz_web.py").read_text(encoding="utf-8")
    val_text = (ROOT / "pneumo_solver_ui" / "validation_cockpit_web.py").read_text(encoding="utf-8")
    qt_text = (ROOT / "pneumo_solver_ui" / "qt_compare_viewer.py").read_text(encoding="utf-8")
    compare_ui_text = (ROOT / "pneumo_solver_ui" / "compare_ui.py").read_text(encoding="utf-8")
    health_text = (ROOT / "pneumo_solver_ui" / "tools" / "health_report.py").read_text(encoding="utf-8")
    inspect_text = (ROOT / "pneumo_solver_ui" / "tools" / "inspect_send_bundle.py").read_text(encoding="utf-8")

    assert '_render_geometry_acceptance_report' in compare_text
    assert 'Геометрический acceptance (рама / колесо / дорога)' in compare_text
    assert 'geometry_acceptance = bun.get("geometry_acceptance")' in val_text
    assert 'format_geometry_acceptance_summary_lines' in qt_text
    assert 'geometry_acceptance=dict(b.get(' in qt_text
    assert '"geometry_acceptance": geometry_acceptance' in compare_ui_text
    assert 'signals["geometry_acceptance"] = geom_acc' in health_text
    assert 'has_geometry_acceptance' in inspect_text
