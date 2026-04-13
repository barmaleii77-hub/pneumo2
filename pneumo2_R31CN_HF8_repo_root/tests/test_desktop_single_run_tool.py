from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui.tools.desktop_single_run import build_desktop_run_summary


def test_build_desktop_run_summary_extracts_operator_metrics() -> None:
    cache_dir = Path("workspace/cache/desktop_run_setup/single_run/demo")
    parsed = {
        "df_main": pd.DataFrame(
            {
                "время_с": [0.0, 0.5, 1.0],
                "крен_phi_рад": [0.0, 0.2, -0.1],
                "тангаж_theta_рад": [0.0, -0.05, 0.1],
            }
        ),
        "df_atm": pd.DataFrame(
            {
                "mech_selfcheck_ok": [1],
                "mech_selfcheck_msg": ["OK"],
            }
        ),
        "df_p": pd.DataFrame({"время_с": [0.0, 1.0]}),
        "df_mdot": pd.DataFrame({"время_с": [0.0, 1.0]}),
        "df_open": pd.DataFrame({"время_с": [0.0, 1.0]}),
    }

    summary = build_desktop_run_summary(
        parsed,
        {"имя": "desktop_run_roll", "тип": "инерция_крен"},
        dt=0.01,
        t_end=1.0,
        record_full=True,
        outdir=Path("workspace/desktop_runs/demo"),
        cache_dir=cache_dir,
        cache_policy="reuse",
    )

    assert summary["ok"] is True
    assert summary["scenario_name"] == "desktop_run_roll"
    assert summary["scenario_type"] == "инерция_крен"
    assert summary["cache_policy"] == "reuse"
    assert summary["cache_dir"] == str(cache_dir)
    assert summary["df_main_rows"] == 3
    assert summary["df_p_rows"] == 2
    assert summary["df_mdot_rows"] == 2
    assert summary["df_open_rows"] == 2
    assert summary["time_start_s"] == 0.0
    assert summary["time_end_s"] == 1.0
    assert abs(float(summary["roll_peak_deg"]) - 11.4591559) < 1e-3
    assert abs(float(summary["pitch_peak_deg"]) - 5.7295779) < 1e-3
    assert summary["mech_selfcheck_ok"] is True
    assert summary["mech_selfcheck_msg"] == "OK"


def test_build_desktop_run_summary_marks_missing_main_table_as_problem() -> None:
    summary = build_desktop_run_summary(
        {"df_main": pd.DataFrame(), "df_atm": pd.DataFrame()},
        {"имя": "empty_case", "тип": "worldroad"},
        dt=0.02,
        t_end=2.0,
        record_full=False,
        outdir=Path("workspace/desktop_runs/empty"),
    )

    assert summary["ok"] is False
    assert summary["df_main_rows"] == 0
    assert summary["mech_selfcheck_ok"] is None
