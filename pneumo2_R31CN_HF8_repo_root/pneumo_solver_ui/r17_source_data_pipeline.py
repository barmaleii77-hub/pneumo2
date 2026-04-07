# -*- coding: utf-8 -*-
"""Stage-2 intake/build helpers for canonical R17 source-data.

This layer intentionally does not infer missing hardpoints from legacy ``dw_*``
parameters. It only:
- emits a fillable canonical template;
- merges semantic-preserving partial JSON with explicitly entered manual values;
- validates the merged JSON with the strict R17 contract.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .r17_source_data_contract import (
    CYLINDERS,
    CYL_AXES,
    ValidationIssue,
    ValidationResult,
    arm_hardpoint_keys,
    cylinder_bottom_mount_keys,
    cylinder_physics_keys,
    cylinder_top_mount_keys,
    required_full_source_keys,
    semantic_preserving_r16_seed,
    validate_source_data,
)

TRUE_VALUES = {"1", "true", "yes", "y", "да"}
FALSE_VALUES = {"0", "false", "no", "n", "нет"}

TEMPLATE_COLUMNS: tuple[str, ...] = (
    "key",
    "group",
    "type",
    "unit_or_enum",
    "required_for_full_R17",
    "can_prefill_from_R16",
    "prefill_value_from_R16_if_any",
    "input_mode",
    "manual_value",
    "manual_source",
    "manual_status",
    "note",
)


@dataclass(frozen=True)
class MergeNote:
    severity: str
    key: str
    kind: str
    message: str
    value: str = ""


def _field_group(key: str) -> str:
    if key in arm_hardpoint_keys():
        return "arm_hardpoint"
    if key in cylinder_top_mount_keys():
        return "cylinder_top_mount"
    if key in cylinder_bottom_mount_keys():
        return "cylinder_bottom_mount"
    if key in cylinder_physics_keys():
        return "cylinder_physics"
    return "unknown"


def _field_type(key: str) -> str:
    if key.endswith("_рычаг_крепления") or key.endswith("_ветвь_трапеции"):
        return "enum"
    return "float"


def _field_unit_or_enum(key: str) -> str:
    if key.endswith("_рычаг_крепления"):
        return "верхний_рычаг|нижний_рычаг"
    if key.endswith("_ветвь_трапеции"):
        return "перед|зад"
    if key.endswith("_доля_рычага"):
        return "0..1"
    if key.endswith("_м"):
        return "m"
    if "диаметр" in key:
        return "m"
    return "number"


def _field_note(key: str) -> str:
    if key in arm_hardpoint_keys():
        return "Обязательный raw/source-data hardpoint spatial double-wishbone трапеции."
    if key.endswith("_ветвь_трапеции"):
        return "Без ветви трапеции доля по рычагу недоопределена для плоской трапеции."
    if key.endswith("_рычаг_крепления"):
        return "Выбор рычага крепления штока должен быть явным, а не следовать из номера цилиндра."
    if key.endswith("_доля_рычага"):
        return "Сохраняет канон wishlist: нижний шарнир штока задаётся как доля длины рычага."
    if "верх_" in key and "x_относительно_оси_ступицы" in key:
        return "В R16 можно перенести semantic-preserving значение 0.0 только как фиксацию текущей reduced-семантики."
    return "Канонический R17 source-data параметр."


def build_fillable_template_rows() -> list[dict[str, str]]:
    seed = semantic_preserving_r16_seed()
    rows: list[dict[str, str]] = []
    for key in required_full_source_keys():
        prefill = seed.get(key, "")
        rows.append(
            {
                "key": key,
                "group": _field_group(key),
                "type": _field_type(key),
                "unit_or_enum": _field_unit_or_enum(key),
                "required_for_full_R17": "yes",
                "can_prefill_from_R16": "yes" if key in seed else "no",
                "prefill_value_from_R16_if_any": "" if prefill == "" else str(prefill),
                "input_mode": "manual_optional_override" if key in seed else "manual_required",
                "manual_value": "",
                "manual_source": "",
                "manual_status": "",
                "note": _field_note(key),
            }
        )
    return rows


def dump_template_csv(path: Path) -> None:
    rows = build_fillable_template_rows()
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TEMPLATE_COLUMNS)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path}: expected JSON object")
    return data


def dump_json(path: Path, data: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(data), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_manual_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _parse_value(raw: str, typ: str) -> Any:
    s = str(raw).strip()
    t = str(typ or "").strip().lower()
    if t in ("", "str", "enum"):
        return s
    if t == "float":
        return float(s)
    if t == "int":
        return int(float(s))
    if t == "bool":
        low = s.lower()
        if low in TRUE_VALUES:
            return True
        if low in FALSE_VALUES:
            return False
        raise ValueError(f"cannot parse bool from {raw!r}")
    raise ValueError(f"unsupported type {typ!r}")


def merge_partial_with_manual_rows(
    partial: Mapping[str, Any], rows: Iterable[Mapping[str, str]]
) -> tuple[dict[str, Any], tuple[MergeNote, ...]]:
    out: dict[str, Any] = dict(partial)
    notes: list[MergeNote] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        if key in seen:
            notes.append(MergeNote("warning", key, "duplicate_manual_row", "Duplicate key row in manual CSV; last non-empty manual_value wins."))
        seen.add(key)
        raw_value = row.get("manual_value")
        if raw_value is None or str(raw_value).strip() == "":
            continue
        typ = str(row.get("type") or "")
        try:
            parsed = _parse_value(str(raw_value), typ)
        except Exception as ex:
            notes.append(MergeNote("error", key, "manual_parse_error", f"Manual value could not be parsed as {typ or 'string'}: {ex}", str(raw_value)))
            continue
        old = out.get(key, None)
        out[key] = parsed
        notes.append(MergeNote("info", key, "manual_set", f"Manual value applied. old={old!r}", repr(parsed)))
    return out, tuple(notes)


def validate_merged_source_data(
    data: Mapping[str, Any], *, allow_partial: bool = False, warn_unknown_keys: bool = True
) -> tuple[ValidationIssue, ...]:
    result: ValidationResult = validate_source_data(
        data,
        require_complete=not allow_partial,
        warn_unknown_keys=warn_unknown_keys,
    )
    return tuple(result.errors + result.warnings)


def issues_to_rows(issues: Sequence[ValidationIssue], *, default_kind: str = "validation") -> list[dict[str, str]]:
    return [
        {
            "key": issue.key,
            "severity": issue.level,
            "kind": default_kind,
            "message": issue.message,
            "value": "",
        }
        for issue in issues
    ]


def merge_notes_to_rows(notes: Sequence[MergeNote]) -> list[dict[str, str]]:
    return [
        {
            "key": note.key,
            "severity": note.severity,
            "kind": note.kind,
            "message": note.message,
            "value": note.value,
        }
        for note in notes
    ]


def dump_report_csv(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    fields = ("key", "severity", "kind", "message", "value")
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def dump_report_md(path: Path, *, template_csv: Path | None, partial_json: Path | None, manual_csv: Path | None, output_json: Path | None, notes: Sequence[MergeNote], issues: Sequence[ValidationIssue]) -> None:
    lines: list[str] = []
    lines.append("# R17 source-data pipeline report")
    lines.append("")
    if template_csv is not None:
        lines.append(f"- Template CSV: `{template_csv.name}`")
    if partial_json is not None:
        lines.append(f"- Partial JSON: `{partial_json.name}`")
    if manual_csv is not None:
        lines.append(f"- Manual CSV: `{manual_csv.name}`")
    if output_json is not None:
        lines.append(f"- Output JSON: `{output_json.name}`")
    lines.append("")
    lines.append(f"- Merge notes: **{len(notes)}**")
    lines.append(f"- Validation issues: **{len(issues)}**")
    lines.append("")
    if notes:
        lines.append("## Merge notes")
        lines.append("")
        lines.append("| severity | kind | key | message | value |")
        lines.append("|---|---|---|---|---|")
        for n in notes:
            lines.append(f"| {n.severity} | {n.kind} | `{n.key}` | {n.message} | `{n.value}` |")
        lines.append("")
    if issues:
        lines.append("## Validation issues")
        lines.append("")
        lines.append("| severity | key | message |")
        lines.append("|---|---|---|")
        for i in issues:
            lines.append(f"| {i.level} | `{i.key}` | {i.message} |")
        lines.append("")
    else:
        lines.append("✅ Validation passed with no issues.")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
