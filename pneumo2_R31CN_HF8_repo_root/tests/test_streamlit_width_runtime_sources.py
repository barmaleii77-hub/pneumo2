from __future__ import annotations

from pathlib import Path


def test_active_runtime_sources_do_not_use_deprecated_use_container_width_directly() -> None:
    root = Path(__file__).resolve().parents[1]
    files = [
        root / 'app.py',
        root / 'pneumo_solver_ui' / 'pages' / '03_DistributedOptimizationDB.py',
        root / 'pneumo_solver_ui' / 'pages' / '04_Uncertainty.py',
        root / 'pneumo_solver_ui' / 'pages' / '08_DesktopAnimator.py',
        root / 'pneumo_solver_ui' / 'pages' / '15_PneumoScheme_Mnemo.py',
        root / 'pneumo_solver_ui' / 'pages' / '16_PneumoScheme_Graph.py',
        root / 'pneumo_solver_ui' / 'pages' / '98_SelfCheck.py',
        root / 'pneumo_solver_ui' / 'ui_preflight.py',
        root / 'pneumo_solver_ui' / 'ui_scenario_ring.py',
        root / 'pneumo_solver_ui' / 'camozzi_catalog_ui.py',
        root / 'pneumo_solver_ui' / 'suspension_geometry_ui.py',
    ]
    for path in files:
        src = path.read_text(encoding='utf-8')
        assert 'use_container_width=' not in src, path.as_posix()
