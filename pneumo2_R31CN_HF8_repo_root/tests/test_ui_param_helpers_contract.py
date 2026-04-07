from pathlib import Path

import numpy as np

from pneumo_solver_ui.ui_param_helpers import (
    is_numeric_scalar,
    is_pressure_param,
    is_small_volume_param,
    is_volume_param,
    param_desc,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ENTRYPOINTS = [
    REPO_ROOT / "pneumo_solver_ui" / "app.py",
    REPO_ROOT / "pneumo_solver_ui" / "pneumo_ui_app.py",
]


def test_param_predicates_and_description_lookup() -> None:
    assert is_pressure_param("давление_Pmin_сброс")
    assert is_pressure_param("начальное_давление_аккумулятора")
    assert not is_pressure_param("объём_линии")

    assert is_volume_param("объём_линии")
    assert is_volume_param("мёртвый_объём_камеры")
    assert not is_volume_param("давление_Pmid_сброс")

    assert is_small_volume_param("объём_линии")
    assert is_small_volume_param("мёртвый_объём_камеры")
    assert not is_small_volume_param("объём_ресивера")

    assert "дросселя/ограничителя" in param_desc("открытие_дросселя_выхлоп_Pmid")
    assert param_desc("unknown_param") == ""


def test_is_numeric_scalar_supports_numpy_scalars_but_not_flags() -> None:
    assert is_numeric_scalar(np.int64(7))
    assert is_numeric_scalar(np.float64(1.25))
    assert is_numeric_scalar(3)
    assert is_numeric_scalar(2.5)
    assert not is_numeric_scalar(True)
    assert not is_numeric_scalar(None)
    assert not is_numeric_scalar("3.14")


def test_large_ui_entrypoints_import_shared_param_helpers() -> None:
    for path in UI_ENTRYPOINTS:
        src = path.read_text(encoding="utf-8")
        assert "from pneumo_solver_ui.ui_param_helpers import (" in src
        assert "is_numeric_scalar as _is_numeric_scalar" in src
        assert "def is_pressure_param(" not in src
        assert "def is_volume_param(" not in src
        assert "def is_small_volume_param(" not in src
        assert "def param_desc(" not in src
        assert "def _is_numeric_scalar(" not in src
        assert "PARAM_DESC:" not in src
