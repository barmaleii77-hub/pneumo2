from __future__ import annotations

import pandas as pd

from pneumo_solver_ui.packaging_surface_helpers import (
    collect_packaging_surface_metrics,
    enrich_packaging_surface_df,
    format_packaging_markdown_lines,
    packaging_error_surface_metrics,
)


def test_collect_packaging_surface_metrics_splits_target_and_autoverif_failures() -> None:
    metrics = {
        "мин_зазор_пружина_цилиндр_м": 0.004,
        "мин_зазор_пружина_пружина_м": -0.002,
        "мин_зазор_пружина_до_крышки_м": -0.001,
        "макс_ошибка_midstroke_t0_м": 0.040,
        "мин_запас_до_coil_bind_пружины_м": 0.002,
        "anim_export_packaging_status": "complete",
        "anim_export_packaging_truth_ready": True,
        "anim_export_packaging_metrics_ok": 1,
        "верификация_флаги": "spring_pair_clearance;spring_cap_gap;coil_bind_risk",
    }
    targets = {
        "мин_зазор_пружина_цилиндр_м": 0.001,
        "мин_зазор_пружина_пружина_м": 0.001,
        "макс_ошибка_midstroke_t0_м": 0.050,
        "мин_запас_до_coil_bind_пружины_м": 0.003,
    }

    out = collect_packaging_surface_metrics(metrics, targets=targets, params={})

    assert int(out["packaging_truth_ready"]) == 1
    assert int(out["packaging_metrics_ok"]) == 1
    assert int(out["pass_packaging_цели"]) == 0
    assert int(out["pass_packaging_верификация"]) == 0
    assert int(out["pass_packaging"]) == 0
    assert "Пружина↔пружина" in str(out["packaging_цели_нарушения"])
    assert "Coil-bind" in str(out["packaging_цели_нарушения"])
    assert "Пружина↔пружина" in str(out["packaging_верификация_нарушения"])
    assert "Пружина↔крышка" in str(out["packaging_верификация_нарушения"])
    assert "Coil-bind" in str(out["packaging_верификация_нарушения"])


def test_collect_packaging_surface_metrics_marks_unknown_target_metrics_without_false_fail() -> None:
    out = collect_packaging_surface_metrics(
        {"anim_export_packaging_status": "partial"},
        targets={"мин_зазор_пружина_цилиндр_м": 0.001},
        params={},
    )

    assert int(out["pass_packaging_цели"]) == 1
    assert "Пружина↔цилиндр" in str(out["packaging_цели_неоценено"])
    assert "частично без данных" in str(out["packaging_цели_статус"])


def test_format_packaging_markdown_lines_surfaces_thresholds_and_counts() -> None:
    metrics = {
        "мин_зазор_пружина_цилиндр_м": 0.002,
        "мин_зазор_пружина_пружина_м": 0.003,
        "мин_зазор_пружина_до_крышки_м": 0.004,
        "макс_ошибка_midstroke_t0_м": 0.020,
        "мин_запас_до_coil_bind_пружины_м": 0.006,
        "число_пересечений_пружина_цилиндр": 0,
        "число_пересечений_пружина_пружина": 2,
        "число_runtime_fallback_пружины": 1,
        "anim_export_packaging_status": "complete",
        "anim_export_packaging_truth_ready": True,
        "anim_export_packaging_metrics_ok": 1,
    }
    targets = {
        "мин_зазор_пружина_цилиндр_м": 0.001,
        "мин_зазор_пружина_пружина_м": 0.001,
        "макс_ошибка_midstroke_t0_м": 0.030,
        "мин_запас_до_coil_bind_пружины_м": 0.003,
    }
    params = {
        "autoverif_spring_host_min_clearance_m": 0.0,
        "autoverif_spring_pair_min_clearance_m": 0.0,
        "autoverif_spring_cap_min_margin_m": 0.0,
        "autoverif_midstroke_t0_max_error_m": 0.050,
        "autoverif_coilbind_min_margin_m": 0.0,
    }

    lines = format_packaging_markdown_lines(metrics, targets=targets, params=params)
    joined = "".join(lines)

    assert "exporter packaging" in joined
    assert "packaging цели" in joined
    assert "packaging autoverif" in joined
    assert "Пружина↔цилиндр" in joined
    assert "Midstroke t0" in joined
    assert "spring↔spring=2" in joined
    assert "runtime_fallback_families=1" in joined


def test_packaging_error_surface_metrics_is_explicit_failure() -> None:
    out = packaging_error_surface_metrics()

    assert int(out["pass_packaging"]) == 0
    assert int(out["pass_packaging_цели"]) == 0
    assert int(out["pass_packaging_верификация"]) == 0
    assert str(out["packaging_статус"]) == "error"


def test_enrich_packaging_surface_df_adds_shared_columns() -> None:
    df = pd.DataFrame(
        [
            {
                "id": 1,
                "мин_зазор_пружина_пружина_м": -0.001,
                "верификация_флаги": "spring_pair_clearance",
                "anim_export_packaging_status": "complete",
                "anim_export_packaging_truth_ready": True,
                "anim_export_packaging_metrics_ok": 1,
            }
        ]
    )

    out = enrich_packaging_surface_df(df)

    assert "pass_packaging" in out.columns
    assert "packaging_верификация_статус" in out.columns
    assert int(out.loc[0, "pass_packaging"]) == 0
    assert "Пружина↔пружина" in str(out.loc[0, "packaging_верификация_нарушения"])
