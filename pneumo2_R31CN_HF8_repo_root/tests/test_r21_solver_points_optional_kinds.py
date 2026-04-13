from __future__ import annotations

from pathlib import Path

import pandas as pd

from pneumo_solver_ui.desktop_animator.data_bundle import DataBundle, NpzTable
from pneumo_solver_ui.solver_points_contract import OPTIONAL_POINT_KINDS, POINT_KINDS, collect_solver_points_contract_issues, point_cols


def _bundle_with_columns(cols: list[str]) -> DataBundle:
    import numpy as np
    values = np.asarray([[0.0] * len(cols)], dtype=float)
    return DataBundle(npz_path=Path('/tmp/fake_anim_latest.npz'), main=NpzTable(cols=cols, values=values), p=None, q=None, open=None, meta={})


def test_point_cols_accepts_optional_trapezoid_kinds() -> None:
    for kind in OPTIONAL_POINT_KINDS:
        cols = point_cols(kind, 'ЛП')
        assert cols == tuple(f'{kind}_ЛП_{axis}_м' for axis in ('x', 'y', 'z'))


def test_collect_contract_does_not_require_optional_triplets_when_absent() -> None:
    cols = ['время_с']
    for kind in POINT_KINDS:
        for corner in ('ЛП', 'ПП', 'ЛЗ', 'ПЗ'):
            cols.extend(point_cols(kind, corner))
    status = collect_solver_points_contract_issues(pd.Index(cols), context='pytest')
    assert status['ok'] is True
    assert status['missing_triplets'] == []
    assert status['partial_triplets'] == []


def test_data_bundle_point_xyz_reads_optional_kind_triplet() -> None:
    cols = list(point_cols('lower_arm_frame_front', 'ЛП'))
    bundle = _bundle_with_columns(cols)
    arr = bundle.point_xyz('lower_arm_frame_front', 'ЛП')
    assert arr is not None
    assert arr.shape == (1, 3)


def test_data_bundle_point_xyz_caches_solver_triplets() -> None:
    cols = list(point_cols('lower_arm_frame_front', 'ЛП'))
    bundle = _bundle_with_columns(cols)
    arr1 = bundle.point_xyz('lower_arm_frame_front', 'ЛП')
    arr2 = bundle.point_xyz('lower_arm_frame_front', 'ЛП')
    assert arr1 is not None
    assert arr1 is arr2


def test_data_bundle_point_xyz_returns_none_for_unknown_kind_without_crash() -> None:
    bundle = _bundle_with_columns(['время_с'])
    assert bundle.point_xyz('totally_unknown_kind', 'ЛП') is None
