from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pneumo_solver_ui import ui_timeline_event_helpers


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = REPO_ROOT / "pneumo_solver_ui" / "app.py"
HEAVY_PATH = REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py"


def _run_starts(mask) -> list[int]:
    arr = np.asarray(mask, dtype=bool)
    if arr.size == 0:
        return []
    starts = np.zeros(arr.shape[0], dtype=bool)
    starts[0] = bool(arr[0])
    starts[1:] = arr[1:] & ~arr[:-1]
    return np.flatnonzero(starts).astype(int).tolist()


def test_align_frame_to_time_vector_uses_nearest_rows() -> None:
    df = pd.DataFrame(
        {
            "время_с": [0.0, 0.49, 1.51, 2.01],
            "value": [10, 20, 30, 40],
        }
    )

    aligned = ui_timeline_event_helpers.align_frame_to_time_vector(
        df,
        np.array([0.0, 0.5, 1.5, 2.0], dtype=float),
    )

    assert aligned["value"].tolist() == [10, 20, 30, 40]


def test_compute_events_alignment_and_sanity_hook_are_opt_in() -> None:
    df_main = pd.DataFrame(
        {
            "время_с": [0.0, 1.0, 2.0, 3.0],
            "дорога_ЛП_м": [0.0, 0.01, 0.01, 0.01],
            "дорога_ПП_м": [0.0, 0.0, 0.0, 0.0],
            "дорога_ЛЗ_м": [0.0, 0.0, 0.0, 0.0],
            "дорога_ПЗ_м": [0.0, 0.0, 0.0, 0.0],
            "перемещение_колеса_ЛП_м": [0.0, 0.0, 0.0, 0.0],
            "перемещение_колеса_ПП_м": [0.0, 0.0, 0.0, 0.0],
            "перемещение_колеса_ЛЗ_м": [0.0, 0.0, 0.0, 0.0],
            "перемещение_колеса_ПЗ_м": [0.0, 0.0, 0.0, 0.0],
        }
    )
    df_p = pd.DataFrame(
        {
            "время_с": [0.1, 2.1],
            "node_a": [101325.0, 1_300_000.0],
            "node_b": [101325.0, 1_250_000.0],
        }
    )

    heavy_like = ui_timeline_event_helpers.compute_events(
        df_main=df_main,
        df_p=df_p,
        df_open=None,
        params_abs={"_P_ATM": 101325.0},
        test={},
        pmax_margin_gauge=0.10,
        gauge_pressure_scale_pa=100000.0,
        vacuum_unit_label="бар(изб)",
        run_starts_fn=_run_starts,
        shorten_name_fn=lambda name, limit: name[:limit],
        align_pressure_df_to_main=True,
        extra_event_hook_fn=ui_timeline_event_helpers.add_wheels_identical_sanity_event,
        use_nan_pressure_reducers=True,
    )
    legacy_like = ui_timeline_event_helpers.compute_events(
        df_main=df_main,
        df_p=df_p,
        df_open=None,
        params_abs={"_P_ATM": 101325.0},
        test={},
        pmax_margin_gauge=0.10,
        gauge_pressure_scale_pa=101325.0,
        vacuum_unit_label="атм(изб)",
        run_starts_fn=_run_starts,
        shorten_name_fn=lambda name, limit: name[:limit],
    )

    heavy_kinds = {event["kind"] for event in heavy_like}
    legacy_kinds = {event["kind"] for event in legacy_like}

    assert "overpressure" in heavy_kinds
    assert "sanity" in heavy_kinds
    assert "overpressure" not in legacy_kinds
    assert "sanity" not in legacy_kinds


def test_profile_helpers_match_entrypoint_unit_profiles() -> None:
    df_main = pd.DataFrame(
        {
            "время_с": [0.0, 1.0, 2.0, 3.0],
            "дорога_ЛП_м": [0.0, 0.01, 0.01, 0.01],
            "дорога_ПП_м": [0.0, 0.0, 0.0, 0.0],
            "дорога_ЛЗ_м": [0.0, 0.0, 0.0, 0.0],
            "дорога_ПЗ_м": [0.0, 0.0, 0.0, 0.0],
            "перемещение_колеса_ЛП_м": [0.0, 0.0, 0.0, 0.0],
            "перемещение_колеса_ПП_м": [0.0, 0.0, 0.0, 0.0],
            "перемещение_колеса_ЛЗ_м": [0.0, 0.0, 0.0, 0.0],
            "перемещение_колеса_ПЗ_м": [0.0, 0.0, 0.0, 0.0],
        }
    )
    df_p = pd.DataFrame(
        {
            "время_с": [0.1, 2.1],
            "node_a": [101325.0, 1_300_000.0],
            "node_b": [101325.0, 1_250_000.0],
        }
    )

    atm_like = ui_timeline_event_helpers.compute_events_atm_profile(
        df_main=df_main,
        df_p=df_p,
        df_open=None,
        params_abs={"_P_ATM": 101325.0},
        test={},
        run_starts_fn=_run_starts,
        shorten_name_fn=lambda name, limit: name[:limit],
    )
    bar_like = ui_timeline_event_helpers.compute_events_bar_profile(
        df_main=df_main,
        df_p=df_p,
        df_open=None,
        params_abs={"_P_ATM": 101325.0},
        test={},
        run_starts_fn=_run_starts,
        shorten_name_fn=lambda name, limit: name[:limit],
    )

    assert not atm_like
    assert {event["kind"] for event in bar_like} == {"overpressure", "sanity"}


def test_entrypoints_delegate_compute_events_to_shared_core() -> None:
    app_text = APP_PATH.read_text(encoding="utf-8")
    heavy_text = HEAVY_PATH.read_text(encoding="utf-8")

    assert "from pneumo_solver_ui.ui_timeline_event_helpers import (" in app_text
    assert "from pneumo_solver_ui.ui_timeline_event_helpers import (" in heavy_text
    assert "def _legacy_compute_events_dead(" in app_text
    assert "def _legacy_compute_events_dead(" in heavy_text
    assert "compute_events_atm_profile as compute_events" in app_text
    assert "compute_events_bar_profile as compute_events" in heavy_text
    assert "def compute_events(" not in app_text
    assert "def compute_events(" not in heavy_text
