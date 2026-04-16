from __future__ import annotations

"""WS-SUITE validated snapshot and HO-005 handoff helpers.

This module owns only the suite matrix contract: rows, runtime overrides,
validation state, preview summary and the suite snapshot hash. Geometry, road
and ring data stay upstream in WS-INPUTS / WS-RING and are referenced here only
by frozen refs and hashes.
"""

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from pneumo_solver_ui.desktop_input_model import describe_desktop_inputs_handoff_for_workspace


VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION = "validated_suite_snapshot_v1"
VALIDATED_SUITE_SNAPSHOT_FILENAME = "validated_suite_snapshot.json"
WS_SUITE_HANDOFF_ID = "HO-005"
WS_SUITE_SOURCE_WORKSPACE = "WS-SUITE"
WS_SUITE_TARGET_WORKSPACE = "WS-BASELINE"
WS_SUITE_INPUTS_HANDOFF_ID = "HO-003"
WS_SUITE_RING_HANDOFF_ID = "HO-004"

SUITE_ROW_REF_KEYS: tuple[str, ...] = ("road_csv", "axay_csv", "scenario_json")
SUITE_REF_TEST_TYPES: frozenset[str] = frozenset(
    {"maneuver_csv", "road_profile_csv", "worldroad"}
)
SUITE_RING_REF_REQUIRED_BY_TYPE: dict[str, tuple[str, ...]] = {
    "maneuver_csv": ("road_csv", "axay_csv", "scenario_json"),
    "road_profile_csv": ("road_csv",),
}

SUITE_ALLOWED_OVERRIDE_KEYS: frozenset[str] = frozenset(
    {
        "включен",
        "enabled",
        "стадия",
        "stage",
        "priority",
        "dt",
        "t_end",
        "t_end_s",
        "t_step",
        "runtime_policy",
        "cache_policy",
        "export_csv",
        "export_npz",
        "record_full",
        "timeseries_strict",
        "auto_t_end_from_len",
        "road_len_m",
        "vx0_м_с",
        "save_csv",
        "save_npz",
    }
)
SUITE_FORBIDDEN_RING_OWNERSHIP_KEYS: frozenset[str] = frozenset(
    {
        "segments",
        "ring_segments",
        "segment_geometry",
        "road_geometry",
        "road_points",
        "ring_source_of_truth",
        "scenario_segments",
        "geometry",
        "hardpoints",
    }
)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _utc_now_label() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _row_name(row: Mapping[str, Any], index: int) -> str:
    for key in ("имя", "name", "id"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return f"row_{int(index) + 1}"


def _row_enabled(row: Mapping[str, Any]) -> bool:
    value = row.get("включен", row.get("enabled", True))
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        try:
            return float(value) != 0.0
        except Exception:
            return True
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"0", "false", "no", "off", "нет"}:
            return False
        if lowered in {"1", "true", "yes", "on", "да"}:
            return True
    return bool(value)


def _row_stage(row: Mapping[str, Any]) -> int:
    raw = row.get("стадия", row.get("stage", 0))
    try:
        return max(0, int(float(raw)))
    except Exception:
        return 0


def _row_type(row: Mapping[str, Any]) -> str:
    return str(row.get("тип", row.get("type", "")) or "").strip()


def _row_identity(row: Mapping[str, Any]) -> str:
    for key in ("id", "имя", "name"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _resolve_ref_path(
    raw_value: Any,
    *,
    suite_source_path: Path | str | None = None,
    repo_root: Path | str | None = None,
) -> Path:
    raw = str(raw_value or "").strip()
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()

    candidates: list[Path] = []
    if suite_source_path is not None:
        candidates.append(Path(suite_source_path).expanduser().resolve().parent / path)
    if repo_root is not None:
        root = Path(repo_root).expanduser().resolve()
        candidates.append(root / path)
        candidates.append(root / "pneumo_solver_ui" / path)
    candidates.append(Path.cwd() / path)

    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return candidates[0].resolve() if candidates else path.resolve()


def _required_ref_keys(row: Mapping[str, Any]) -> tuple[str, ...]:
    typ = _row_type(row).strip().lower()
    required = SUITE_RING_REF_REQUIRED_BY_TYPE.get(typ)
    if required is not None:
        return required
    if any(str(row.get(key) or "").strip() for key in SUITE_ROW_REF_KEYS):
        return SUITE_ROW_REF_KEYS
    return ()


def load_suite_rows(path: Path | str) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Suite JSON must contain a list: {path}")
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def suite_rows_hash(rows: Iterable[Mapping[str, Any]]) -> str:
    normalized = [dict(row) for row in rows if isinstance(row, Mapping)]
    return _sha256(normalized)


def resolve_suite_inputs_handoff(
    *,
    workspace_dir: Path | str | None = None,
    snapshot_path: Path | str | None = None,
    snapshot: dict[str, Any] | None = None,
    current_inputs_snapshot_hash: str = "",
) -> dict[str, Any]:
    """Resolve the WS-INPUTS -> WS-SUITE input ref without owning input data."""

    return describe_desktop_inputs_handoff_for_workspace(
        "WS-SUITE",
        workspace_dir=workspace_dir,
        snapshot_path=snapshot_path,
        snapshot=snapshot,
        current_payload_hash=current_inputs_snapshot_hash,
    )


def _iter_named_overrides(overrides: Mapping[str, Any] | None, row: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    if not isinstance(overrides, Mapping):
        return ()
    identity = _row_identity(row)
    name = str(row.get("имя") or row.get("name") or "").strip()
    by_name = overrides.get("by_name")
    by_id = overrides.get("by_id")
    values: list[Mapping[str, Any]] = []
    if isinstance(by_name, Mapping) and name and isinstance(by_name.get(name), Mapping):
        values.append(by_name[name])
    if isinstance(by_id, Mapping) and identity and isinstance(by_id.get(identity), Mapping):
        values.append(by_id[identity])
    return tuple(values)


def apply_suite_runtime_overrides(
    rows: Iterable[Mapping[str, Any]],
    overrides: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply allowed runtime overrides while rejecting ring/geometry mutation."""

    normalized = [dict(row) for row in rows if isinstance(row, Mapping)]
    rejected: list[dict[str, Any]] = []
    if not isinstance(overrides, Mapping):
        return normalized, rejected

    def _apply_override(row: dict[str, Any], patch: Mapping[str, Any], row_index: int) -> None:
        row_name = _row_name(row, row_index)
        for key, value in dict(patch).items():
            key_text = str(key)
            allowed = (
                key_text in SUITE_ALLOWED_OVERRIDE_KEYS
                or key_text.startswith("target_")
            )
            if (
                key_text in SUITE_ROW_REF_KEYS
                or key_text in SUITE_FORBIDDEN_RING_OWNERSHIP_KEYS
                or not allowed
            ):
                rejected.append(
                    {
                        "row": row_name,
                        "key": key_text,
                        "reason": (
                            "ring_or_geometry_ref_is_owned_by_WS_RING"
                            if key_text in SUITE_ROW_REF_KEYS or key_text in SUITE_FORBIDDEN_RING_OWNERSHIP_KEYS
                            else "unsupported_suite_override_key"
                        ),
                    }
                )
                continue
            row[key_text] = value

    global_patch = overrides.get("global")
    if isinstance(global_patch, Mapping):
        for idx, row in enumerate(normalized):
            _apply_override(row, global_patch, idx)
    for idx, row in enumerate(normalized):
        for patch in _iter_named_overrides(overrides, row):
            _apply_override(row, patch, idx)
    return normalized, rejected


def validate_suite_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    suite_source_path: Path | str | None = None,
    repo_root: Path | str | None = None,
    override_rejections: Iterable[Mapping[str, Any]] = (),
    upstream_ref_errors: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    normalized = [dict(row) for row in rows if isinstance(row, Mapping)]
    missing_refs: list[dict[str, Any]] = []
    ownership_violations: list[dict[str, Any]] = []
    duplicate_names: list[str] = []
    seen_names: set[str] = set()

    for idx, row in enumerate(normalized):
        name = _row_name(row, idx)
        if name in seen_names:
            duplicate_names.append(name)
        seen_names.add(name)

        enabled = _row_enabled(row)
        for key in sorted(SUITE_FORBIDDEN_RING_OWNERSHIP_KEYS & set(str(k) for k in row.keys())):
            ownership_violations.append(
                {
                    "row": name,
                    "key": key,
                    "reason": "WS-SUITE must consume WS-RING refs, not own ring/geometry source data",
                }
            )

        for ref_key in _required_ref_keys(row):
            raw_ref = str(row.get(ref_key) or "").strip()
            if not raw_ref:
                missing_refs.append(
                    {
                        "row": name,
                        "key": ref_key,
                        "path": "",
                        "enabled": enabled,
                        "severity": "error" if enabled else "warning",
                        "reason": "required_ref_is_blank",
                    }
                )
                continue
            resolved = _resolve_ref_path(
                raw_ref,
                suite_source_path=suite_source_path,
                repo_root=repo_root,
            )
            if not resolved.exists():
                missing_refs.append(
                    {
                        "row": name,
                        "key": ref_key,
                        "path": str(resolved),
                        "enabled": enabled,
                        "severity": "error" if enabled else "warning",
                        "reason": "required_ref_file_missing",
                    }
                )

    enabled_count = sum(1 for row in normalized if _row_enabled(row))
    blocking_missing_refs = [item for item in missing_refs if item.get("severity") == "error"]
    rejections = [dict(item) for item in override_rejections if isinstance(item, Mapping)]
    upstream_errors = [dict(item) for item in upstream_ref_errors if isinstance(item, Mapping)]
    ok = (
        enabled_count > 0
        and not blocking_missing_refs
        and not ownership_violations
        and not duplicate_names
        and not rejections
        and not upstream_errors
    )
    warnings: list[str] = []
    if enabled_count <= 0:
        warnings.append("suite_has_no_enabled_rows")
    if any(item.get("severity") == "warning" for item in missing_refs):
        warnings.append("disabled_or_inactive_rows_have_missing_refs")
    return {
        "ok": bool(ok),
        "row_count": int(len(normalized)),
        "enabled_count": int(enabled_count),
        "missing_refs": missing_refs,
        "missing_ref_count": int(len(missing_refs)),
        "blocking_missing_ref_count": int(len(blocking_missing_refs)),
        "ownership_violations": ownership_violations,
        "ownership_violation_count": int(len(ownership_violations)),
        "duplicate_names": duplicate_names,
        "override_rejections": rejections,
        "override_rejection_count": int(len(rejections)),
        "upstream_ref_errors": upstream_errors,
        "upstream_ref_error_count": int(len(upstream_errors)),
        "warnings": warnings,
        "handoff_ready": bool(ok),
    }


def build_suite_matrix_preview(
    rows: Iterable[Mapping[str, Any]],
    *,
    validation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = [dict(row) for row in rows if isinstance(row, Mapping)]
    stage_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    enabled_rows: list[dict[str, Any]] = []
    ref_row_count = 0
    for idx, row in enumerate(normalized):
        stage = str(_row_stage(row))
        typ = _row_type(row) or "unknown"
        stage_counts[stage] = int(stage_counts.get(stage, 0) + 1)
        type_counts[typ] = int(type_counts.get(typ, 0) + 1)
        if _required_ref_keys(row):
            ref_row_count += 1
        if _row_enabled(row):
            enabled_rows.append(
                {
                    "name": _row_name(row, idx),
                    "stage": int(_row_stage(row)),
                    "type": typ,
                    "refs": [key for key in SUITE_ROW_REF_KEYS if str(row.get(key) or "").strip()],
                }
            )
    validation_obj = dict(validation or {})
    summary_text = (
        f"rows={len(normalized)} | enabled={len(enabled_rows)} | "
        f"stages={','.join(f'{k}:{v}' for k, v in sorted(stage_counts.items())) or 'none'} | "
        f"types={len(type_counts)} | ref_rows={ref_row_count} | "
        f"missing_refs={int(validation_obj.get('missing_ref_count', 0) or 0)}"
    )
    return {
        "row_count": int(len(normalized)),
        "enabled_count": int(len(enabled_rows)),
        "stage_counts": {key: int(stage_counts[key]) for key in sorted(stage_counts)},
        "type_counts": {key: int(type_counts[key]) for key in sorted(type_counts)},
        "ref_row_count": int(ref_row_count),
        "enabled_rows": enabled_rows,
        "missing_ref_count": int(validation_obj.get("missing_ref_count", 0) or 0),
        "blocking_missing_ref_count": int(validation_obj.get("blocking_missing_ref_count", 0) or 0),
        "summary_text": summary_text,
    }


def suite_snapshot_hash(snapshot_core: Mapping[str, Any]) -> str:
    return _sha256(dict(snapshot_core))


def build_validated_suite_snapshot(
    suite_rows: Iterable[Mapping[str, Any]],
    *,
    suite_source_path: Path | str | None = None,
    inputs_snapshot_ref: Path | str | None = None,
    inputs_snapshot_hash: str = "",
    ring_source_ref: Mapping[str, Any] | None = None,
    ring_source_hash: str = "",
    overrides: Mapping[str, Any] | None = None,
    upstream_ref_errors: Iterable[Mapping[str, Any]] = (),
    created_at_utc: str | None = None,
    repo_root: Path | str | None = None,
    context_label: str = "",
) -> dict[str, Any]:
    rows, override_rejections = apply_suite_runtime_overrides(suite_rows, overrides)
    validation = validate_suite_rows(
        rows,
        suite_source_path=suite_source_path,
        repo_root=repo_root,
        override_rejections=override_rejections,
        upstream_ref_errors=upstream_ref_errors,
    )
    preview = build_suite_matrix_preview(rows, validation=validation)
    upstream_refs = {
        "inputs": {
            "workspace": "WS-INPUTS",
            "handoff_id": WS_SUITE_INPUTS_HANDOFF_ID,
            "snapshot_ref": str(Path(inputs_snapshot_ref).resolve()) if inputs_snapshot_ref else "",
            "snapshot_hash": str(inputs_snapshot_hash or "").strip(),
        },
        "ring": {
            "workspace": "WS-RING",
            "handoff_id": WS_SUITE_RING_HANDOFF_ID,
            "source_ref": dict(ring_source_ref or {}),
            "source_hash": str(ring_source_hash or "").strip(),
        },
    }
    snapshot_core = {
        "schema_version": VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION,
        "source_workspace": WS_SUITE_SOURCE_WORKSPACE,
        "target_workspace": WS_SUITE_TARGET_WORKSPACE,
        "handoff_id": WS_SUITE_HANDOFF_ID,
        "frozen": True,
        "context_label": str(context_label or "").strip(),
        "suite_source_path": str(Path(suite_source_path).resolve()) if suite_source_path else "",
        "upstream_refs": upstream_refs,
        "overrides": copy.deepcopy(dict(overrides or {})),
        "suite_rows": rows,
        "suite_rows_hash": suite_rows_hash(rows),
        "validation": validation,
        "preview": preview,
    }
    snapshot = {
        **snapshot_core,
        "created_at_utc": str(created_at_utc or _utc_now_label()),
    }
    snapshot["suite_snapshot_hash"] = suite_snapshot_hash(snapshot_core)
    snapshot["validated"] = bool(validation.get("ok", False))
    return snapshot


def describe_suite_snapshot_state(
    snapshot: Mapping[str, Any] | None,
    *,
    current_inputs_snapshot_hash: str = "",
    current_ring_source_hash: str = "",
    current_suite_snapshot_hash: str = "",
) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        return {
            "state": "missing",
            "is_stale": True,
            "handoff_ready": False,
            "stale_reasons": ["missing_validated_suite_snapshot"],
            "banner": "validated_suite_snapshot не найден: WS-SUITE должен создать HO-005 перед baseline.",
        }

    if str(snapshot.get("schema_version") or "") != VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION:
        return {
            "state": "invalid",
            "is_stale": True,
            "handoff_ready": False,
            "stale_reasons": ["unsupported_validated_suite_snapshot_schema"],
            "banner": "validated_suite_snapshot имеет неподдерживаемую схему; baseline не должен молча продолжать.",
        }

    validation = dict(snapshot.get("validation") or {})
    if not bool(validation.get("ok", False)):
        missing = int(validation.get("blocking_missing_ref_count", 0) or 0)
        ownership = int(validation.get("ownership_violation_count", 0) or 0)
        rejections = int(validation.get("override_rejection_count", 0) or 0)
        upstream = int(validation.get("upstream_ref_error_count", 0) or 0)
        enabled = int(validation.get("enabled_count", 0) or 0)
        reasons = []
        if enabled <= 0:
            reasons.append("no_enabled_suite_rows")
        if missing:
            reasons.append("missing_ring_or_input_refs")
        if ownership:
            reasons.append("suite_owns_ring_or_geometry_data")
        if rejections:
            reasons.append("rejected_suite_overrides")
        if upstream:
            reasons.append("missing_upstream_handoff_refs")
        return {
            "state": "invalid",
            "is_stale": True,
            "handoff_ready": False,
            "stale_reasons": reasons or ["suite_validation_failed"],
            "banner": (
                "validated_suite_snapshot не готов для HO-005: "
                f"enabled={enabled}, missing_refs={missing}, "
                f"ownership_violations={ownership}, override_rejections={rejections}, "
                f"upstream_ref_errors={upstream}."
            ),
        }

    stale_reasons: list[str] = []
    upstream_refs = dict(snapshot.get("upstream_refs") or {})
    inputs = dict(upstream_refs.get("inputs") or {})
    ring = dict(upstream_refs.get("ring") or {})
    if current_inputs_snapshot_hash:
        stored_inputs_hash = str(inputs.get("snapshot_hash") or "")
        if stored_inputs_hash != str(current_inputs_snapshot_hash):
            stale_reasons.append("inputs_snapshot_hash_changed")
    if current_ring_source_hash:
        stored_ring_hash = str(ring.get("source_hash") or "")
        if stored_ring_hash != str(current_ring_source_hash):
            stale_reasons.append("ring_source_hash_changed")
    if current_suite_snapshot_hash:
        stored_suite_hash = str(snapshot.get("suite_snapshot_hash") or "")
        if stored_suite_hash != str(current_suite_snapshot_hash):
            stale_reasons.append("suite_snapshot_hash_changed")

    if stale_reasons:
        return {
            "state": "stale",
            "is_stale": True,
            "handoff_ready": False,
            "stale_reasons": stale_reasons,
            "banner": (
                "validated_suite_snapshot устарел для HO-005: "
                + ", ".join(stale_reasons)
                + ". Обновите WS-SUITE snapshot перед baseline."
            ),
        }

    return {
        "state": "current",
        "is_stale": False,
        "handoff_ready": True,
        "stale_reasons": [],
        "banner": (
            "validated_suite_snapshot актуален: WS-BASELINE может потребить HO-005 "
            f"с suite_snapshot_hash={str(snapshot.get('suite_snapshot_hash') or '')[:12]}."
        ),
    }


__all__ = [
    "SUITE_ALLOWED_OVERRIDE_KEYS",
    "SUITE_FORBIDDEN_RING_OWNERSHIP_KEYS",
    "SUITE_REF_TEST_TYPES",
    "SUITE_ROW_REF_KEYS",
    "VALIDATED_SUITE_SNAPSHOT_FILENAME",
    "VALIDATED_SUITE_SNAPSHOT_SCHEMA_VERSION",
    "WS_SUITE_HANDOFF_ID",
    "WS_SUITE_INPUTS_HANDOFF_ID",
    "WS_SUITE_RING_HANDOFF_ID",
    "apply_suite_runtime_overrides",
    "build_suite_matrix_preview",
    "build_validated_suite_snapshot",
    "describe_suite_snapshot_state",
    "load_suite_rows",
    "resolve_suite_inputs_handoff",
    "suite_rows_hash",
    "suite_snapshot_hash",
    "validate_suite_rows",
]
