from __future__ import annotations

import os
from pathlib import Path

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets

from pneumo_solver_ui.desktop_animator.data_bundle import DataBundle, NpzTable
from pneumo_solver_ui.desktop_animator.engineering_analysis import rank_global_focus_metrics
from pneumo_solver_ui.desktop_animator.engineering_analysis_panel import MultiFactorAnalysisPanel


def _build_bundle() -> DataBundle:
    t = np.linspace(0.0, 4.0 * np.pi, 121)
    roll = 0.025 * np.sin(t)
    pitch = 0.018 * np.cos(t)
    heave = 0.010 * np.sin(0.5 * t)
    az_body = 1.8 * np.sin(t)
    az_wheel = 2.2 * np.sin(t + 0.05)
    road = 0.003 * np.sin(1.7 * t)
    travel = 0.040 * np.sin(t)
    stroke = 0.034 * np.sin(t)

    corners = {
        "ЛП": heave + roll + pitch,
        "ПП": heave - roll + pitch,
        "ЛЗ": heave + roll - pitch,
        "ПЗ": heave - roll - pitch,
    }

    cols = ["время_с"]
    values = [t]
    for corner, body_z in corners.items():
        cols.extend(
            [
                f"рама_угол_{corner}_z_м",
                f"рама_угол_{corner}_v_м_с",
                f"рама_угол_{corner}_a_м_с2",
                f"перемещение_колеса_{corner}_м",
                f"скорость_колеса_{corner}_м_с",
                f"ускорение_колеса_{corner}_м_с2",
                f"дорога_{corner}_м",
                f"положение_штока_{corner}_м",
                f"нормальная_сила_шины_{corner}_Н",
                f"колесо_в_воздухе_{corner}",
            ]
        )
        wheel_z = body_z + travel
        tire_force = 4200.0 + (700.0 * np.sin(t)) + (320.0 if "Л" in corner else -320.0)
        wheel_air = np.where((corner == "ЛП") & (np.sin(t) > 0.85), 1.0, 0.0)
        values.extend(
            [
                body_z,
                np.gradient(body_z, t),
                az_body + (0.20 if "Л" in corner else -0.20),
                wheel_z,
                np.gradient(wheel_z, t),
                az_wheel + (0.15 if "П" in corner else -0.15),
                road,
                stroke + (0.004 if "П" in corner else -0.004),
                tire_force,
                wheel_air,
            ]
        )

    cols.extend(
        [
            "давление_ресивер1_Па",
            "давление_ресивер2_Па",
            "давление_ресивер3_Па",
            "давление_аккумулятор_Па",
        ]
    )
    values.extend(
        [
            540000.0 + (28000.0 * np.sin(t)),
            500000.0 + (16000.0 * np.sin(t + 0.4)),
            470000.0 + (9000.0 * np.cos(t)),
            520000.0 + (12000.0 * np.sin(t - 0.2)),
        ]
    )
    main = NpzTable(cols=cols, values=np.vstack(values).T.astype(float))
    return DataBundle(npz_path=Path("synthetic.npz"), main=main, meta={"geometry": {"wheelbase_m": 2.8}})


def test_multifactor_panel_runtime_autofocus_updates_focus_combo_and_summary() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    bundle = _build_bundle()
    panel = MultiFactorAnalysisPanel()
    panel.set_bundle(bundle)

    panel._apply_preset("ride")
    assert panel.cb_auto_focus.isChecked() is True

    ranked = rank_global_focus_metrics(panel._catalog, idx=16, window_s=3.0)  # type: ignore[arg-type]
    panel.update_frame(bundle, 16)
    app.processEvents()

    assert ranked
    assert str(panel.cb_focus.currentData()) == str(ranked[0]["metric"])
    assert "Heuristic Assistant" in panel.summary.toHtml()
    assert "Smart focus" in panel.summary.toHtml()
    assert "smart:" in panel.lbl_focus_hint.text()
