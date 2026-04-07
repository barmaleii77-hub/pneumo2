# -*- coding: utf-8 -*-
"""R17 canonical source-data contract for spatial double-wishbone geometry.

Stage-1 scaffold goals:
- define one canonical family of raw/source-data keys for the future R17 hardpoint
  intake without introducing runtime aliases;
- validate merged/manual source-data strictly and loudly;
- allow only semantic-preserving seeding from R16 where the old solver already had
  explicit meaning (for example, top X offset = 0.0 in the reduced one-x-local model).

Important: this module intentionally does *not* reconstruct missing hardpoints from
legacy ``dw_*`` parameters. That reconstruction would be a silent geometry invention
and therefore violates ABSOLUTE LAW.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


AXLE_TAGS: tuple[str, str] = ("ось_перед", "ось_зад")
ARMS: tuple[str, str] = ("верхний_рычаг", "нижний_рычаг")
ANCHORS: tuple[str, str] = ("рама", "ступица")
BRANCHES: tuple[str, str] = ("перед", "зад")
AXES_XYZ: tuple[str, str, str] = ("x", "y", "z")
CYLINDERS: tuple[str, str] = ("Ц1", "Ц2")
CYL_AXES: tuple[str, str] = ("перед", "зад")
TOP_SPAN_SUFFIX_BY_AXLE: dict[str, str] = {
    "перед": "между_ЛП_ПП_м",
    "зад": "между_ЛЗ_ПЗ_м",
}

MOUNT_ARM_ENUM: tuple[str, str] = ("верхний_рычаг", "нижний_рычаг")
TRAPEZOID_BRANCH_ENUM: tuple[str, str] = ("перед", "зад")


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    key: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    errors: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def arm_hardpoint_keys() -> tuple[str, ...]:
    keys: list[str] = []
    for arm in ARMS:
        for axle_tag in AXLE_TAGS:
            for anchor in ANCHORS:
                for branch in BRANCHES:
                    for axis in AXES_XYZ:
                        keys.append(f"{arm}_{axle_tag}_{anchor}_ветвь_{branch}_{axis}_м")
    return tuple(keys)


def arm_triplet_stems() -> tuple[str, ...]:
    stems: list[str] = []
    for arm in ARMS:
        for axle_tag in AXLE_TAGS:
            for anchor in ANCHORS:
                for branch in BRANCHES:
                    stems.append(f"{arm}_{axle_tag}_{anchor}_ветвь_{branch}")
    return tuple(stems)


def cylinder_top_mount_keys() -> tuple[str, ...]:
    keys: list[str] = []
    for cyl in CYLINDERS:
        for axle in CYL_AXES:
            keys.append(f"верх_{cyl}_{axle}_x_относительно_оси_ступицы_м")
            keys.append(f"верх_{cyl}_{axle}_z_относительно_рамы_м")
            keys.append(f"верх_{cyl}_{axle}_{TOP_SPAN_SUFFIX_BY_AXLE[axle]}")
    return tuple(keys)


def cylinder_bottom_mount_keys() -> tuple[str, ...]:
    keys: list[str] = []
    for cyl in CYLINDERS:
        for axle in CYL_AXES:
            base = f"низ_{cyl}_{axle}"
            keys.extend(
                (
                    f"{base}_рычаг_крепления",
                    f"{base}_ветвь_трапеции",
                    f"{base}_доля_рычага",
                )
            )
    return tuple(keys)


def cylinder_physics_keys() -> tuple[str, ...]:
    keys: list[str] = []
    for cyl in CYLINDERS:
        keys.append(f"диаметр_поршня_{cyl}")
        keys.append(f"диаметр_штока_{cyl}")
    for cyl in CYLINDERS:
        for axle in CYL_AXES:
            keys.append(f"ход_штока_{cyl}_{axle}_м")
    return tuple(keys)


def required_full_source_keys() -> tuple[str, ...]:
    return (
        arm_hardpoint_keys()
        + cylinder_top_mount_keys()
        + cylinder_bottom_mount_keys()
        + cylinder_physics_keys()
    )


def required_manual_only_keys() -> tuple[str, ...]:
    keys = list(arm_hardpoint_keys())
    for cyl in CYLINDERS:
        for axle in CYL_AXES:
            keys.append(f"низ_{cyl}_{axle}_ветвь_трапеции")
    return tuple(keys)


def semantic_preserving_r16_seed() -> dict[str, Any]:
    """Return only R16->R17 values that preserve *current* R16 semantics.

    This is not a future engineering default. It is only an explicit bridge for offline
    migration of already-existing reduced-worldroad meaning.
    """
    data: dict[str, Any] = {}
    for cyl in CYLINDERS:
        for axle in CYL_AXES:
            data[f"верх_{cyl}_{axle}_x_относительно_оси_ступицы_м"] = 0.0
    for axle in CYL_AXES:
        data[f"низ_Ц1_{axle}_рычаг_крепления"] = "нижний_рычаг"
        data[f"низ_Ц2_{axle}_рычаг_крепления"] = "верхний_рычаг"
    return data


def allowed_source_keys() -> frozenset[str]:
    return frozenset(required_full_source_keys())


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _append_error(errors: list[ValidationIssue], key: str, message: str) -> None:
    errors.append(ValidationIssue(level="error", key=key, message=message))


def _append_warning(warnings: list[ValidationIssue], key: str, message: str) -> None:
    warnings.append(ValidationIssue(level="warning", key=key, message=message))


def validate_source_data(
    data: Mapping[str, Any],
    *,
    require_complete: bool = True,
    warn_unknown_keys: bool = True,
) -> ValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    required = required_full_source_keys()
    allowed = allowed_source_keys()

    if require_complete:
        for key in required:
            if key not in data:
                _append_error(errors, key, "Отсутствует обязательный канонический source-data ключ R17.")

    if warn_unknown_keys:
        for key in sorted(set(data.keys()) - allowed):
            _append_warning(
                warnings,
                key,
                "Ключ отсутствует в каноническом R17 source-data контракте. Это не runtime-канон.",
            )

    for stem in arm_triplet_stems():
        xyz_keys = tuple(f"{stem}_{axis}_м" for axis in AXES_XYZ)
        present = [key in data for key in xyz_keys]
        if any(present) and not all(present):
            _append_error(
                errors,
                stem,
                "Неполный triplet hardpoint: должны быть одновременно x/y/z.",
            )
        for key in xyz_keys:
            if key in data and not _is_number(data[key]):
                _append_error(errors, key, "Координата hardpoint должна быть числом.")

    for key in cylinder_top_mount_keys() + cylinder_physics_keys():
        if key in data and not _is_number(data[key]):
            _append_error(errors, key, "Числовой source-data параметр должен быть числом.")

    for key in cylinder_bottom_mount_keys():
        if key.endswith("_доля_рычага"):
            if key in data:
                if not _is_number(data[key]):
                    _append_error(errors, key, "Параметр доли по рычагу должен быть числом в диапазоне [0,1].")
                else:
                    value = float(data[key])
                    if not (0.0 <= value <= 1.0):
                        _append_error(errors, key, "Параметр доли по рычагу должен лежать в диапазоне [0,1].")
        elif key.endswith("_рычаг_крепления"):
            if key in data and data[key] not in MOUNT_ARM_ENUM:
                _append_error(
                    errors,
                    key,
                    f"Ключ должен принимать одно из значений {MOUNT_ARM_ENUM!r}.",
                )
        elif key.endswith("_ветвь_трапеции"):
            if key in data and data[key] not in TRAPEZOID_BRANCH_ENUM:
                _append_error(
                    errors,
                    key,
                    f"Ключ должен принимать одно из значений {TRAPEZOID_BRANCH_ENUM!r}.",
                )

    return ValidationResult(errors=tuple(errors), warnings=tuple(warnings))


def build_machine_schema() -> dict[str, Any]:
    return {
        "schema": "r17_source_data_contract_v1",
        "required_full_source_keys": list(required_full_source_keys()),
        "required_manual_only_keys": list(required_manual_only_keys()),
        "semantic_preserving_r16_seed": semantic_preserving_r16_seed(),
        "enum": {
            "рычаг_крепления": list(MOUNT_ARM_ENUM),
            "ветвь_трапеции": list(TRAPEZOID_BRANCH_ENUM),
        },
    }


def group_counts() -> dict[str, int]:
    return {
        "arm_hardpoint": len(arm_hardpoint_keys()),
        "cylinder_top_mount": len(cylinder_top_mount_keys()),
        "cylinder_bottom_mount": len(cylinder_bottom_mount_keys()),
        "cylinder_physics": len(cylinder_physics_keys()),
        "required_full": len(required_full_source_keys()),
        "required_manual_only": len(required_manual_only_keys()),
    }
