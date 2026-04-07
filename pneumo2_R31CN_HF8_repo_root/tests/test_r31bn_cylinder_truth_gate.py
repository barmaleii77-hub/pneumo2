from __future__ import annotations

from pathlib import Path

from pneumo_solver_ui.desktop_animator.cylinder_truth_gate import (
    evaluate_all_cylinder_truth_gates,
    evaluate_cylinder_truth_gate,
    render_cylinder_truth_gate_message,
)

ROOT = Path(__file__).resolve().parents[1]


def _complete_packaging_meta() -> dict:
    return {
        "packaging": {
            "status": "complete",
            "cylinders": {
                "cyl1": {
                    "contract_complete": True,
                    "length_status_by_corner": {
                        "ЛП": "already_finite",
                        "ПП": "filled_from_endpoint_distance",
                        "ЛЗ": "patched_nonfinite_from_endpoint_distance",
                        "ПЗ": "already_finite",
                    },
                    "advanced_fields_missing": [],
                    "mount_families": {"top": "cyl1_top", "bottom": "cyl1_bot"},
                },
                "cyl2": {
                    "contract_complete": True,
                    "length_status_by_corner": {
                        "ЛП": "already_finite",
                        "ПП": "already_finite",
                        "ЛЗ": "already_finite",
                        "ПЗ": "already_finite",
                    },
                    "advanced_fields_missing": [],
                    "mount_families": {"top": "cyl2_top", "bottom": "cyl2_bot"},
                },
            },
        }
    }



def test_missing_packaging_forces_axis_only_honesty_mode() -> None:
    gate = evaluate_cylinder_truth_gate({}, "cyl1")
    assert gate["enabled"] is False
    assert gate["mode"] == "axis_only"
    assert gate["reason"] == "missing_meta_packaging"
    assert "axis-only honesty mode" in render_cylinder_truth_gate_message(gate)



def test_partial_packaging_with_missing_advanced_fields_stays_axis_only() -> None:
    meta = {
        "packaging": {
            "status": "partial",
            "cylinders": {
                "cyl1": {
                    "contract_complete": False,
                    "length_status_by_corner": {"ЛП": "filled_from_endpoint_distance"},
                    "advanced_fields_missing": ["gland_or_sleeve_position_m", "rod_eye_length_m"],
                    "mount_families": {"top": "cyl1_top", "bottom": "cyl1_bot"},
                }
            },
        }
    }
    gate = evaluate_cylinder_truth_gate(meta, "cyl1")
    assert gate["enabled"] is False
    assert gate["mode"] == "axis_only"
    assert gate["reason"] == "cyl1_advanced_packaging_missing"
    msg = render_cylinder_truth_gate_message(gate)
    assert "gland_or_sleeve_position_m" in msg
    assert "rod_eye_length_m" in msg



def test_complete_packaging_enables_truth_mode_for_both_cylinders() -> None:
    gates = evaluate_all_cylinder_truth_gates(_complete_packaging_meta())
    assert gates["cyl1"]["enabled"] is True
    assert gates["cyl1"]["mode"] == "body_rod_piston"
    assert gates["cyl2"]["enabled"] is True
    assert gates["cyl2"]["mode"] == "body_rod_piston"



def test_animator_source_uses_truth_gate_to_disable_packaging_meshes_until_contract_complete() -> None:
    src = (ROOT / "pneumo_solver_ui" / "desktop_animator" / "app.py").read_text(encoding="utf-8")
    assert "from .cylinder_truth_gate import" in src
    assert "self._cylinder_truth_gates = _evaluate_all_cylinder_truth_gates" in src
    assert "truth_gate = self._cylinder_truth_gate(cyl_index)" in src
    assert 'if bool(truth_gate.get("enabled")):' in src
    assert "_axis_only_honesty_mode" in src
