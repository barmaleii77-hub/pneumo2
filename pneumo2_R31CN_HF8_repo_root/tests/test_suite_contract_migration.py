from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui.opt_worker_v3_margins_energy import build_test_suite
from pneumo_solver_ui.suite_contract_migration import migrate_legacy_suite_columns


def test_migrate_legacy_speed_column_to_canonical_vx0() -> None:
    df = pd.DataFrame(
        [
            {
                "имя": "diag_old",
                "тип": "кочка_диагональ",
                "скорость_м_с": 12.5,
            }
        ]
    )

    migrated, issues = migrate_legacy_suite_columns(df, context="test.speed_only")

    assert "скорость_м_с" not in migrated.columns
    assert "vx0_м_с" in migrated.columns
    assert float(migrated.loc[0, "vx0_м_с"]) == 12.5
    assert issues
    assert any("скорость_м_с" in msg and "vx0_м_с" in msg for msg in issues)


def test_migrate_legacy_speed_fills_missing_canonical_and_preserves_conflicts() -> None:
    df = pd.DataFrame(
        [
            {"имя": "fill", "тип": "кочка_диагональ", "скорость_м_с": 12.5, "vx0_м_с": None},
            {"имя": "conflict", "тип": "кочка_диагональ", "скорость_м_с": 12.5, "vx0_м_с": 15.0},
        ]
    )

    migrated, issues = migrate_legacy_suite_columns(df, context="test.fill_conflict")

    assert "скорость_м_с" not in migrated.columns
    assert float(migrated.loc[0, "vx0_м_с"]) == 12.5
    assert float(migrated.loc[1, "vx0_м_с"]) == 15.0
    assert any("конфликтов=1" in msg for msg in issues)


def test_migrated_suite_speed_reaches_build_test_suite_for_bump_diag() -> None:
    df = pd.DataFrame(
        [
            {
                "имя": "diag_from_legacy_editor",
                "тип": "кочка_диагональ",
                "включен": True,
                "dt": 0.01,
                "t_end": 3.0,
                "A": 0.05,
                "dur": 0.2,
                "t0": 0.4,
                "скорость_м_с": 12.5,
                "угол_град": 35.0,
                "доля_плавной_стыковки": 0.25,
            }
        ]
    )

    migrated, issues = migrate_legacy_suite_columns(df, context="test.build_suite")
    assert issues, "legacy speed migration must be reported loudly"

    built = build_test_suite(
        {
            "suite": migrated.to_dict(orient="records"),
            "скорость_м_с_по_умолчанию": 77.0,
            "колея": 1.2,
            "база": 2.3,
        }
    )

    assert len(built) == 1
    _, test, *_ = built[0]
    assert float(test["v"]) == 12.5


def test_streamlit_suite_editors_use_canonical_speed_key_only() -> None:
    app_src = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "app.py"
    ui_src = Path(__file__).resolve().parents[1] / "pneumo_solver_ui" / "pneumo_ui_app.py"
    app_text = app_src.read_text(encoding="utf-8")
    ui_text = ui_src.read_text(encoding="utf-8")

    assert '"скорость_м_с"' not in app_text
    assert '"скорость_м_с"' not in ui_text
    assert '"vx0_м_с"' in app_text
    assert '"vx0_м_с"' in ui_text
