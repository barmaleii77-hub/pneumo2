from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from pneumo_solver_ui.packaging_surface_ui import (
    apply_packaging_surface_filters,
    load_packaging_params_from_base_json,
    packaging_surface_result_columns,
)


class _FakeColumn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def metric(self, *args, **kwargs):
        return None


class _FakeSt:
    def __init__(self, checkbox_values: dict[str, bool] | None = None):
        self.session_state = {}
        self._checkbox_values = dict(checkbox_values or {})

    def checkbox(self, label, value=False, key=""):
        return bool(self._checkbox_values.get(key, value))

    def caption(self, *args, **kwargs):
        return None

    def columns(self, n):
        return [_FakeColumn() for _ in range(int(n))]


def test_load_packaging_params_from_base_json_reads_file(tmp_path: Path) -> None:
    path = tmp_path / "base.json"
    path.write_text(json.dumps({"autoverif_midstroke_t0_max_error_m": 0.05}, ensure_ascii=False), encoding="utf-8")

    out = load_packaging_params_from_base_json(path)

    assert float(out["autoverif_midstroke_t0_max_error_m"]) == 0.05


def test_packaging_surface_result_columns_keeps_leading_and_metrics() -> None:
    df = pd.DataFrame(
        [
            {
                "trial_id": "t1",
                "pass_packaging": 1,
                "packaging_truth_ready": 1,
                "мин_зазор_пружина_цилиндр_м": 0.01,
            }
        ]
    )

    cols = packaging_surface_result_columns(df, leading=["trial_id"])

    assert cols[0] == "trial_id"
    assert "pass_packaging" in cols
    assert "packaging_truth_ready" in cols
    assert "мин_зазор_пружина_цилиндр_м" in cols


def test_apply_packaging_surface_filters_respects_key_prefix() -> None:
    df = pd.DataFrame(
        [
            {
                "id": 1,
                "pass_packaging": 1,
                "packaging_truth_ready": 1,
                "число_runtime_fallback_пружины": 0,
                "число_пересечений_пружина_цилиндр": 0,
                "число_пересечений_пружина_пружина": 0,
            },
            {
                "id": 2,
                "pass_packaging": 0,
                "packaging_truth_ready": 0,
                "число_runtime_fallback_пружины": 1,
                "число_пересечений_пружина_цилиндр": 1,
                "число_пересечений_пружина_пружина": 1,
            },
        ]
    )
    st = _FakeSt(
        {
            "demo_packaging_pass_filter": True,
            "demo_packaging_truth_ready": True,
            "demo_packaging_no_fallback": True,
            "demo_packaging_no_interference": True,
        }
    )

    out = apply_packaging_surface_filters(st, df, key_prefix="demo")

    assert list(out["id"]) == [1]
