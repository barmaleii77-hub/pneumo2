from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui.opt_worker_v3_margins_energy import build_test_suite
from pneumo_solver_ui.optimization_auto_ring_suite import (
    AUTO_RING_META_FILENAME,
    materialize_optimization_auto_ring_suite_json,
)


ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = ROOT / "pneumo_solver_ui"


def _make_synthetic_ring_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    t = np.arange(0.0, 12.0 + 1e-12, 0.1)
    road = pd.DataFrame(
        {
            "t": t,
            "z0": 0.010 * np.exp(-((t - 1.0) / 0.35) ** 2) - 0.006 * np.exp(-((t - 4.0) / 0.25) ** 2),
            "z1": 0.011 * np.exp(-((t - 1.0) / 0.35) ** 2) + 0.006 * np.exp(-((t - 4.0) / 0.25) ** 2),
            "z2": 0.009 * np.exp(-((t - 1.0) / 0.35) ** 2) + 0.006 * np.exp(-((t - 4.0) / 0.25) ** 2),
            "z3": 0.010 * np.exp(-((t - 1.0) / 0.35) ** 2) - 0.006 * np.exp(-((t - 4.0) / 0.25) ** 2),
        }
    )
    axay = pd.DataFrame(
        {
            "t": t,
            "ax": 1.6 * np.exp(-((t - 9.0) / 0.5) ** 2),
            "ay": 2.4 * np.exp(-((t - 7.0) / 0.5) ** 2),
        }
    )
    spec = {
        "schema_version": "ring_v2",
        "v0_kph": 36.0,
        "dt_s": 0.1,
        "wheelbase_m": 1.6,
        "track_m": 1.1,
        "segments": [
            {
                "name": "S1_rough",
                "duration_s": 3.0,
                "turn_direction": "STRAIGHT",
                "road": {"mode": "ISO8608"},
                "events": [{"kind": "яма"}],
            },
            {
                "name": "S2_turn",
                "duration_s": 4.0,
                "turn_direction": "LEFT",
                "road": {"mode": "SINE"},
                "events": [],
            },
            {
                "name": "S3_exit",
                "duration_s": 5.0,
                "turn_direction": "STRAIGHT",
                "road": {"mode": "ISO8608"},
                "events": [{"kind": "препятствие"}],
            },
        ],
        "_generated_meta": {
            "dt_s": 0.1,
            "lap_time_s": 12.0,
            "ring_length_m": 120.0,
            "wheelbase_m": 1.6,
            "track_m": 1.1,
        },
    }
    road_csv = tmp_path / "ring_road.csv"
    axay_csv = tmp_path / "ring_axay.csv"
    scenario_json = tmp_path / "ring_spec.json"
    road.to_csv(road_csv, index=False)
    axay.to_csv(axay_csv, index=False)
    scenario_json.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return road_csv, axay_csv, scenario_json


def test_materialize_auto_ring_suite_builds_staged_rows_and_fragments(tmp_path: Path) -> None:
    road_csv, axay_csv, scenario_json = _make_synthetic_ring_inputs(tmp_path)
    suite_path = materialize_optimization_auto_ring_suite_json(
        tmp_path / "workspace",
        suite_source_path=UI_ROOT / "default_suite.json",
        road_csv=road_csv,
        axay_csv=axay_csv,
        scenario_json=scenario_json,
        window_s=4.0,
    )

    rows = json.loads(suite_path.read_text(encoding="utf-8"))
    assert isinstance(rows, list)
    enabled = {
        str((row or {}).get("имя") or "").strip(): row
        for row in rows
        if isinstance(row, dict) and bool(row.get("включен"))
    }
    for name in ("инерция_крен_ay3", "инерция_тангаж_ax3", "микро_синфаза", "микро_pitch", "микро_diagonal"):
        assert name in enabled
        assert int(enabled[name]["стадия"]) == 0
    assert "ring_auto_full" in enabled
    assert int(enabled["ring_auto_full"]["стадия"]) == 2
    assert Path(enabled["ring_auto_full"]["road_csv"]).resolve() == road_csv.resolve()
    assert Path(enabled["ring_auto_full"]["axay_csv"]).resolve() == axay_csv.resolve()
    assert Path(enabled["ring_auto_full"]["scenario_json"]).resolve() == scenario_json.resolve()

    fragment_rows = [row for row in rows if str((row or {}).get("имя") or "").startswith("ringfrag_")]
    assert len(fragment_rows) >= 2
    assert all(int(row["стадия"]) == 1 for row in fragment_rows)
    assert all(Path(row["road_csv"]).is_absolute() and Path(row["road_csv"]).exists() for row in fragment_rows)
    assert all(Path(row["axay_csv"]).is_absolute() and Path(row["axay_csv"]).exists() for row in fragment_rows)
    assert all(Path(row["scenario_json"]).is_absolute() and Path(row["scenario_json"]).exists() for row in fragment_rows)
    assert all(float(row["t_end"]) > 0.0 for row in fragment_rows)

    meta = json.loads(suite_path.with_name(AUTO_RING_META_FILENAME).read_text(encoding="utf-8"))
    assert meta["cylinder_freedom"]["allow_c1_c2_split"] is True
    assert meta["cylinder_freedom"]["allow_front_rear_split"] is True
    assert meta["cylinder_freedom"]["allow_left_right_asymmetry"] is False
    assert meta["design_symmetry"] == "left_right_only"
    assert len(meta["recommended_stage_param_hints"]) == 3


def test_build_optimization_auto_ring_suite_tool_runs(tmp_path: Path) -> None:
    road_csv, axay_csv, scenario_json = _make_synthetic_ring_inputs(tmp_path)
    script = ROOT / "pneumo_solver_ui" / "tools" / "build_optimization_auto_ring_suite.py"
    workspace_dir = tmp_path / "workspace"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--workspace-dir",
            str(workspace_dir),
            "--suite-source-json",
            str(UI_ROOT / "default_suite.json"),
            "--road-csv",
            str(road_csv),
            "--axay-csv",
            str(axay_csv),
            "--scenario-json",
            str(scenario_json),
            "--window-s",
            "4.0",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "suite_json=" in proc.stdout


def test_auto_ring_suite_rows_parse_via_worker_build_test_suite(tmp_path: Path) -> None:
    road_csv, axay_csv, scenario_json = _make_synthetic_ring_inputs(tmp_path)
    suite_path = materialize_optimization_auto_ring_suite_json(
        tmp_path / "workspace",
        suite_source_path=UI_ROOT / "default_suite.json",
        road_csv=road_csv,
        axay_csv=axay_csv,
        scenario_json=scenario_json,
        window_s=4.0,
    )
    rows = json.loads(suite_path.read_text(encoding="utf-8"))
    tests = build_test_suite(
        {
            "suite": rows,
            "__suite_explicit__": True,
            "__suite_json_path__": str(suite_path),
        }
    )
    names = [str(name) for name, *_ in tests]
    assert "ring_auto_full" in names
    assert any(name.startswith("ringfrag_") for name in names)
