from __future__ import annotations

from pneumo_solver_ui.r17_source_data_contract import (
    ARMS,
    AXLE_TAGS,
    BRANCHES,
    CYLINDERS,
    CYL_AXES,
    MOUNT_ARM_ENUM,
    TRAPEZOID_BRANCH_ENUM,
    arm_hardpoint_keys,
    cylinder_bottom_mount_keys,
    cylinder_physics_keys,
    cylinder_top_mount_keys,
    group_counts,
    required_full_source_keys,
    required_manual_only_keys,
    semantic_preserving_r16_seed,
    validate_source_data,
)


def _build_complete_sample() -> dict[str, object]:
    data: dict[str, object] = {}
    for key in arm_hardpoint_keys():
        if key.endswith("_x_м"):
            data[key] = 0.10
        elif key.endswith("_y_м"):
            data[key] = 0.20
        else:
            data[key] = 0.30
    for key in cylinder_top_mount_keys() + cylinder_physics_keys():
        data[key] = 0.05
    for cyl in CYLINDERS:
        for axle in CYL_AXES:
            data[f"низ_{cyl}_{axle}_рычаг_крепления"] = MOUNT_ARM_ENUM[0]
            data[f"низ_{cyl}_{axle}_ветвь_трапеции"] = TRAPEZOID_BRANCH_ENUM[0]
            data[f"низ_{cyl}_{axle}_доля_рычага"] = 0.5
    return data


def test_r17_contract_group_counts_are_stable() -> None:
    counts = group_counts()
    assert counts == {
        "arm_hardpoint": 48,
        "cylinder_top_mount": 12,
        "cylinder_bottom_mount": 12,
        "cylinder_physics": 8,
        "required_full": 80,
        "required_manual_only": 52,
    }
    assert len(required_full_source_keys()) == 80
    assert len(required_manual_only_keys()) == 52


def test_r17_complete_sample_passes_validation() -> None:
    data = _build_complete_sample()
    result = validate_source_data(data)
    assert result.ok, result
    assert result.errors == ()
    assert result.warnings == ()


def test_r17_validator_rejects_incomplete_triplet() -> None:
    data = _build_complete_sample()
    bad_key = f"{ARMS[0]}_{AXLE_TAGS[0]}_рама_ветвь_{BRANCHES[0]}_z_м"
    del data[bad_key]
    result = validate_source_data(data, require_complete=False)
    assert not result.ok
    assert any(issue.key.endswith("рама_ветвь_перед") for issue in result.errors)


def test_r17_validator_rejects_bad_mount_values() -> None:
    data = _build_complete_sample()
    data["низ_Ц1_перед_рычаг_крепления"] = "arm1"
    data["низ_Ц1_перед_ветвь_трапеции"] = "left"
    data["низ_Ц1_перед_доля_рычага"] = 1.5
    result = validate_source_data(data)
    assert not result.ok
    messages = {issue.key: issue.message for issue in result.errors}
    assert "низ_Ц1_перед_рычаг_крепления" in messages
    assert "низ_Ц1_перед_ветвь_трапеции" in messages
    assert "низ_Ц1_перед_доля_рычага" in messages


def test_semantic_preserving_r16_seed_is_small_and_explicit() -> None:
    seed = semantic_preserving_r16_seed()
    assert len(seed) == 8
    assert seed["верх_Ц1_перед_x_относительно_оси_ступицы_м"] == 0.0
    assert seed["верх_Ц2_зад_x_относительно_оси_ступицы_м"] == 0.0
    assert seed["низ_Ц1_перед_рычаг_крепления"] == "нижний_рычаг"
    assert seed["низ_Ц2_перед_рычаг_крепления"] == "верхний_рычаг"
