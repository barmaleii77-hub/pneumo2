from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from pneumo_solver_ui.solver_points_contract import point_cols


ROOT = Path(__file__).resolve().parents[1]
CORNERS = ("ЛП", "ПП", "ЛЗ", "ПЗ")


def _set_point(data: dict[str, np.ndarray], kind: str, corner: str, xyz: tuple[float, float, float], n: int) -> None:
    cx, cy, cz = point_cols(kind, corner)
    x, y, z = xyz
    data[cx] = np.full(n, float(x), dtype=float)
    data[cy] = np.full(n, float(y), dtype=float)
    data[cz] = np.full(n, float(z), dtype=float)


def _write_geometry_bundle(tmp_path: Path) -> Path:
    n = 2
    data: dict[str, np.ndarray] = {
        "время_с": np.array([0.0, 0.1], dtype=float),
    }
    xy_map = {
        "ЛП": (0.75, 0.50),
        "ПП": (0.75, -0.50),
        "ЛЗ": (-0.75, 0.50),
        "ПЗ": (-0.75, -0.50),
    }

    for corner in CORNERS:
        x, y = xy_map[corner]
        _set_point(data, "frame_corner", corner, (x, y, 0.50), n)
        _set_point(data, "wheel_center", corner, (x, y, 0.22), n)

        _set_point(data, "arm_pivot", corner, (x, y, 0.45), n)
        _set_point(data, "arm_joint", corner, (x, y, 0.25), n)
        _set_point(data, "arm2_pivot", corner, (x, y, 0.55), n)
        _set_point(data, "arm2_joint", corner, (x, y, 0.32), n)

        _set_point(data, "lower_arm_frame_front", corner, (x, y, 0.45), n)
        _set_point(data, "lower_arm_frame_rear", corner, (x - 0.05, y, 0.45), n)
        _set_point(data, "lower_arm_hub_front", corner, (x, y, 0.20), n)
        _set_point(data, "lower_arm_hub_rear", corner, (x - 0.05, y, 0.20), n)

        _set_point(data, "upper_arm_frame_front", corner, (x, y, 0.55), n)
        _set_point(data, "upper_arm_frame_rear", corner, (x - 0.05, y, 0.55), n)
        _set_point(data, "upper_arm_hub_front", corner, (x, y, 0.30), n)
        _set_point(data, "upper_arm_hub_rear", corner, (x - 0.05, y, 0.30), n)

        _set_point(data, "cyl1_top", corner, (x - 0.02, y, 0.52), n)
        _set_point(data, "cyl1_bot", corner, (x, y, 0.30), n)
        _set_point(data, "cyl2_top", corner, (x - 0.07, y, 0.60), n)
        _set_point(data, "cyl2_bot", corner, (x, y, 0.40), n)

    cols = list(data.keys())
    values = np.column_stack([data[c] for c in cols]).astype(float)
    npz_path = tmp_path / "suspension_geometry_bundle.npz"
    np.savez_compressed(
        npz_path,
        main_cols=np.array(cols, dtype=object),
        main_values=values,
        meta_json=json.dumps({"geometry": {"wheelbase_m": 1.5, "track_m": 1.0}}, ensure_ascii=False),
    )
    return npz_path


def _assert_cli_result(proc: subprocess.CompletedProcess[str], json_out: Path) -> None:
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "# Suspension geometry diagnostics" in proc.stdout
    assert "ok: True" in proc.stdout
    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert len(payload["rows"]) == 4


def test_inspect_suspension_geometry_runs_as_module(tmp_path: Path) -> None:
    npz_path = _write_geometry_bundle(tmp_path)
    json_out = tmp_path / "module_report.json"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pneumo_solver_ui.tools.inspect_suspension_geometry",
            str(npz_path),
            "--json",
            str(json_out),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    _assert_cli_result(proc, json_out)


def test_inspect_suspension_geometry_runs_as_script(tmp_path: Path) -> None:
    npz_path = _write_geometry_bundle(tmp_path)
    json_out = tmp_path / "script_report.json"
    script = ROOT / "pneumo_solver_ui" / "tools" / "inspect_suspension_geometry.py"
    proc = subprocess.run(
        [sys.executable, str(script), str(npz_path), "--json", str(json_out)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    _assert_cli_result(proc, json_out)
